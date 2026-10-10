"""Week 2 reproducible data-readiness pipeline (Customer Support Assistant track).

raw (never modified)                         processed / quarantine
  data/raw/knowledge_base/KB-*.md   ──►  data/processed/knowledge/knowledge_articles.jsonl
  data/raw/tickets/*.csv            ──►  data/processed/interactions/{train,validation,test}.jsonl
                                         data/processed/interactions/ticket_outcomes.csv  (baseline only)
                                         data/processed/manifest.csv      (1 row per source record)
                                         data/processed/run_manifest.json (version, config, counts, gates)
                                         data/quarantine/quarantine_log.csv
                                         data/quarantine/review_queue.csv

Every source record receives exactly one outcome: publish, review or quarantine.
Critical rules -> quarantine. Warning rules -> review. No rule fired -> publish.

Usage (from the Week2 folder):
    python -m src.data.build_dataset
    python -m src.data.build_dataset --out-root /tmp/check   # write outputs somewhere else
Exit code 0 = all critical dataset gates passed, 1 = at least one failed.
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from . import rules as R

ROOT = Path(__file__).resolve().parents[2]

CRITICAL = {
    # knowledge
    "KB_EMPTY_BODY": "body shorter than minimum after extraction",
    "KB_NOT_APPROVED": "article is not approved for customer use",
    "KB_DUPLICATE_CONTENT": "same normalised body as an earlier article",
    "KB_MISSING_METADATA": "required metadata field missing",
    "KB_ID_MISMATCH": "kb_id in front matter differs from filename",
    # tickets
    "MSG_DUPLICATE_EXACT": "identical raw row already seen (export duplicate)",
    "MSG_DUPLICATE_ID": "message_id reused with different content",
    "MSG_MISSING_TICKET_ID": "no ticket_id: thread and split cannot be protected",
    "MSG_EMPTY_TEXT": "message text empty after whitespace normalisation",
    "MSG_INVALID_TIMESTAMP": "created_at cannot be parsed into a real date-time",
    "MSG_FUTURE_TIMESTAMP": "created_at is after the export snapshot",
    "MSG_PAYMENT_DATA": "text contains a payment-card number (Luhn-valid)",
    "MSG_OUT_OF_SCOPE_LANGUAGE": "message not in the MVP language (English)",
    "MSG_INVALID_ROLE": "sender_role is not customer or agent",
}
WARNING = {
    "KB_STALE": "last_reviewed older than allowed age",
    "KB_MISSING_OWNER": "no accountable owner recorded",
    "KB_UNKNOWN_CATEGORY": "category not in the in-scope intent list",
    "MSG_NEAR_DUPLICATE": "same normalised text re-sent in the same ticket within window",
    "MSG_LABEL_MISSING": "ticket question has no intent label",
    "MSG_LABEL_UNMAPPED": "intent label not in the approved mapping",
    "MSG_LENGTH_OUTLIER": "text length above IQR fence fitted on TRAIN split",
    "MSG_CHANNEL_UNMAPPED": "channel value not in mapping",
    "THREAD_NO_QUESTION": "ticket has no usable customer question",
    "THREAD_PENDING_REVIEW": "the ticket question is in review, so the thread is held",
}

TICKET_FIELDS = ["message_id", "ticket_id", "created_at", "channel", "customer_ref", "sender_role",
                 "message_text", "intent_label", "resolution_status", "csat_score", "resolved_at",
                 "handle_time_min"]


def outcome_of(codes: list[str]) -> str:
    if any(c in CRITICAL for c in codes):
        return "quarantine"
    if codes:
        return "review"
    return "publish"


def load_config(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw), R.sha256_bytes(raw)


# --------------------------------------------------------------------------- gate G1
def verify_inventory(root: Path, cfg: dict) -> dict:
    inv_path = root / cfg["inputs"]["inventory_csv"]
    inv = {r["location"]: r for r in csv.DictReader(inv_path.open(encoding="utf-8"))}
    discovered = sorted(p.relative_to(root).as_posix() for p in root.glob(cfg["inputs"]["knowledge_glob"]))
    discovered.append(cfg["inputs"]["tickets_csv"])
    problems = []
    for loc in discovered:
        if loc not in inv:
            problems.append(f"not in inventory: {loc}")
            continue
        actual = R.sha256_bytes((root / loc).read_bytes())
        if actual != inv[loc]["sha256"]:
            problems.append(f"hash mismatch: {loc}")
    for loc in inv:
        if loc not in discovered:
            problems.append(f"inventory file missing on disk: {loc}")
    return {"gate": "G1_INPUT_INTEGRITY", "severity": "critical", "passed": not problems,
            "detail": problems or f"{len(discovered)} files match inventory hashes",
            "files": {loc: inv[loc]["sha256"] for loc in discovered if loc in inv}}


# --------------------------------------------------------------------------- knowledge
def process_knowledge(root: Path, cfg: dict, snapshot: datetime):
    kcfg = cfg["knowledge"]
    in_scope = set(cfg["in_scope_intents"])
    seen_content: dict[str, str] = {}
    records, published = [], []
    for p in sorted(root.glob(cfg["inputs"]["knowledge_glob"])):
        raw_bytes = p.read_bytes()
        meta, body = R.parse_front_matter(raw_bytes.decode("utf-8"))
        paragraphs = [R.normalise_whitespace(x) for x in body.split("\n\n")]
        paragraphs = [x for x in paragraphs if x]
        clean_body = "\n\n".join(paragraphs)
        content_hash = R.sha256_text(clean_body.casefold())
        codes, details = [], []

        missing = [f for f in kcfg["required_fields"] if f != "owner" and not meta.get(f)]
        if missing:
            codes.append("KB_MISSING_METADATA"); details.append("missing=" + "|".join(missing))
        if meta.get("kb_id") and meta["kb_id"] != p.stem:
            codes.append("KB_ID_MISMATCH")
        if len(clean_body) < kcfg["min_body_chars"]:
            codes.append("KB_EMPTY_BODY"); details.append(f"body_chars={len(clean_body)}")
        if meta.get("approved", "").lower() != "true":
            codes.append("KB_NOT_APPROVED"); details.append(f"approved={meta.get('approved')}")
        if len(clean_body) >= kcfg["min_body_chars"]:
            if content_hash in seen_content:
                codes.append("KB_DUPLICATE_CONTENT"); details.append(f"duplicate_of={seen_content[content_hash]}")
            else:
                seen_content[content_hash] = p.stem
        if not meta.get("owner"):
            codes.append("KB_MISSING_OWNER")
        age_days = None
        try:
            age_days = (snapshot.astimezone(R.parse_offset(cfg["split"]["local_offset"])).date() - date.fromisoformat(meta.get("last_reviewed", ""))).days
            if age_days > kcfg["stale_after_days"]:
                codes.append("KB_STALE"); details.append(f"age_days={age_days}")
        except ValueError:
            if "KB_MISSING_METADATA" not in codes:
                codes.append("KB_MISSING_METADATA"); details.append("last_reviewed unparseable")
        if meta.get("category") and meta["category"] not in in_scope:
            codes.append("KB_UNKNOWN_CATEGORY")

        out = outcome_of(codes)
        rec = dict(record_type="kb_article", source_id=p.stem,
                   source_file=p.relative_to(root).as_posix(), source_record="1",
                   record_sha256=R.sha256_bytes(raw_bytes), outcome=out,
                   reason_codes="|".join(codes), details="; ".join(details), split="",
                   output_path="")
        if out == "publish":
            rec["output_path"] = "data/processed/knowledge/knowledge_articles.jsonl"
            published.append(dict(
                kb_id=meta["kb_id"], title=meta["title"], category=meta["category"],
                owner=meta["owner"], approved=True, last_reviewed=meta["last_reviewed"],
                review_age_days=age_days, version=meta["version"], body=clean_body,
                n_paragraphs=len(paragraphs), word_count=len(clean_body.split()),
                content_sha256=content_hash, source_file=rec["source_file"],
                source_sha256=rec["record_sha256"], pipeline_version=cfg["pipeline_version"]))
        elif out == "review":
            rec["output_path"] = "data/quarantine/review_queue.csv"
        else:
            rec["output_path"] = "data/quarantine/quarantine_log.csv"
        records.append(rec)
    return records, published


# --------------------------------------------------------------------------- tickets
def split_of(first_utc: datetime, cfg: dict) -> str:
    s = cfg["split"]
    local_day = first_utc.astimezone(R.parse_offset(s["local_offset"])).date()
    if local_day < date.fromisoformat(s["train_before_local"]):
        return "train"
    if local_day < date.fromisoformat(s["validation_before_local"]):
        return "validation"
    return "test"


def process_tickets(root: Path, cfg: dict, snapshot: datetime):
    tcfg = cfg["tickets"]
    src = cfg["inputs"]["tickets_csv"]
    with (root / src).open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    msgs = []
    seen_hash: dict[str, str] = {}
    seen_id: dict[str, str] = {}
    for i, row in enumerate(rows, start=1):
        values = [row.get(k, "") for k in TICKET_FIELDS]
        h = R.record_hash(values)
        m = dict(row=row, idx=i, sha=h, codes=[], details=[])
        mid = row["message_id"]
        if h in seen_hash:
            m["codes"].append("MSG_DUPLICATE_EXACT"); m["details"].append(f"duplicate_of_row={seen_hash[h]}")
        else:
            seen_hash[h] = str(i)
            if mid in seen_id:
                m["codes"].append("MSG_DUPLICATE_ID")
            seen_id[mid] = h
        if not row["ticket_id"].strip():
            m["codes"].append("MSG_MISSING_TICKET_ID")
        text = R.normalise_whitespace(row["message_text"])
        if not text:
            m["codes"].append("MSG_EMPTY_TEXT")
        ts, fmt = R.parse_timestamp(row["created_at"], cfg["naive_timestamp_offset"])
        m["ts"], m["ts_format"] = ts, fmt
        if ts is None:
            m["codes"].append("MSG_INVALID_TIMESTAMP"); m["details"].append(f"created_at={row['created_at']!r}")
        elif ts > snapshot:
            m["codes"].append("MSG_FUTURE_TIMESTAMP"); m["details"].append(f"created_at={row['created_at']}")
        if R.contains_payment_card(text):
            m["codes"].append("MSG_PAYMENT_DATA")
        if text and R.detect_language(text, tcfg["vietnamese_diacritics_min"]) != tcfg["in_scope_language"]:
            m["codes"].append("MSG_OUT_OF_SCOPE_LANGUAGE")
        if row["sender_role"] not in ("customer", "agent"):
            m["codes"].append("MSG_INVALID_ROLE")
        channel = cfg["channel_map"].get(R.label_key(row["channel"]))
        if channel is None:
            m["codes"].append("MSG_CHANNEL_UNMAPPED")
        m["channel"] = channel
        red, n_pii = R.redact_pii(text) if text else ("", 0)
        m["text"], m["n_pii"] = red, n_pii
        msgs.append(m)

    # ---- identify each ticket's question from ALL raw rows (not only survivors), so that a
    #      follow-up such as "Thanks!" is never promoted to question when the real one was removed.
    #      message_id is assigned sequentially by the helpdesk, so it orders rows even when
    #      created_at is invalid.
    question_id: dict[str, str] = {}
    for m in msgs:
        r = m["row"]
        if r["ticket_id"] and r["sender_role"] == "customer" and "MSG_DUPLICATE_EXACT" not in m["codes"]:
            if r["ticket_id"] not in question_id or r["message_id"] < question_id[r["ticket_id"]]:
                question_id[r["ticket_id"]] = r["message_id"]

    # ---- thread-level rules on records that survived the critical checks
    survivors = [m for m in msgs if outcome_of(m["codes"]) != "quarantine"]
    by_ticket: dict[str, list[dict]] = defaultdict(list)
    for m in survivors:
        by_ticket[m["row"]["ticket_id"]].append(m)

    ticket_info = {}
    for tid, items in by_ticket.items():
        items.sort(key=lambda m: (m["ts"], m["row"]["message_id"]))
        seen_text: dict[str, datetime] = {}
        for turn, m in enumerate(items, start=1):
            m["turn"] = turn
            k = R.dedup_key(m["text"])
            prev = seen_text.get(k)
            if prev is not None and (m["ts"] - prev).total_seconds() <= tcfg["near_duplicate_window_seconds"]:
                m["codes"].append("MSG_NEAR_DUPLICATE")
            else:
                seen_text[k] = m["ts"]
        question = next((m for m in items if m["row"]["message_id"] == question_id.get(tid)), None)
        intent = None
        if question is not None:
            question["is_question"] = True
            lab = question["row"]["intent_label"]
            if not lab.strip():
                question["codes"].append("MSG_LABEL_MISSING")
            else:
                intent = cfg["intent_map"].get(R.label_key(lab))
                if intent is None:
                    question["codes"].append("MSG_LABEL_UNMAPPED"); question["details"].append(f"label={lab!r}")
        first = items[0]["ts"]
        ticket_info[tid] = dict(first_utc=first, split=split_of(first, cfg), intent=intent,
                                question=question)

    # ---- preprocessing fitted on TRAIN only (length fence), then applied to all splits
    train_lengths = [len(m["text"]) for m in survivors if ticket_info[m["row"]["ticket_id"]]["split"] == "train"]
    fence = R.iqr_upper_fence(train_lengths, tcfg["length_outlier_iqr_multiplier"])
    for m in survivors:
        if len(m["text"]) > fence:
            m["codes"].append("MSG_LENGTH_OUTLIER"); m["details"].append(f"chars={len(m['text'])}>fence={fence:.0f}")

    # ---- thread integrity: hold a whole thread when its question is not publishable
    for tid, info in ticket_info.items():
        q = info["question"]
        for m in by_ticket[tid]:
            if m is q:
                continue
            if q is None:
                m["codes"].append("THREAD_NO_QUESTION")
            elif outcome_of(q["codes"]) != "publish":
                m["codes"].append("THREAD_PENDING_REVIEW")

    # ---- outputs
    records, published, review_rows, quarantine_rows = [], [], [], []
    for m in msgs:
        row = m["row"]
        out = outcome_of(m["codes"])
        tid = row["ticket_id"]
        info = ticket_info.get(tid) if out != "quarantine" else None
        split = info["split"] if info else ""
        rec = dict(record_type="ticket_message", source_id=row["message_id"], source_file=src,
                   source_record=str(m["idx"]), record_sha256=m["sha"], outcome=out,
                   reason_codes="|".join(m["codes"]), details="; ".join(m["details"]), split=split,
                   output_path="")
        if out == "publish":
            rec["output_path"] = f"data/processed/interactions/{split}.jsonl"
            published.append(dict(
                message_id=row["message_id"], ticket_id=tid, split=split,
                created_at_utc=m["ts"].strftime("%Y-%m-%dT%H:%M:%SZ"), timestamp_source_format=m["ts_format"],
                channel=m["channel"], customer_ref=row["customer_ref"], sender_role=row["sender_role"],
                turn_index=m["turn"], is_ticket_question=bool(m.get("is_question")),
                ticket_intent=info["intent"], text=m["text"], char_len=len(m["text"]),
                pii_redactions=m["n_pii"], source_row=m["idx"], source_sha256=m["sha"],
                pipeline_version=cfg["pipeline_version"]))
        elif out == "review":
            rec["output_path"] = "data/quarantine/review_queue.csv"
            review_rows.append(dict(source_id=row["message_id"], ticket_id=tid, split=split,
                                    sender_role=row["sender_role"], reason_codes=rec["reason_codes"],
                                    details=rec["details"], redacted_text=m["text"][:300],
                                    raw_intent_label=row["intent_label"], source_row=m["idx"]))
        else:
            rec["output_path"] = "data/quarantine/quarantine_log.csv"
        records.append(rec)

    # ---- post-outcome fields: kept OUT of interactions, ticket level, baseline use only
    outcomes = {}
    hmax = tcfg["handle_time_extreme_min"]
    for m in msgs:
        tid = m["row"]["ticket_id"]
        if not tid or tid in outcomes or "MSG_DUPLICATE_EXACT" in m["codes"]:
            continue
        raw_h = m["row"]["handle_time_min"].strip()
        try:
            hv = float(raw_h)
            flag = "invalid_negative" if hv < 0 else "invalid_zero" if hv == 0 else \
                f"extreme_gt_{hmax}" if hv > hmax else "ok"
        except ValueError:
            hv, flag = None, "missing"
        outcomes[tid] = dict(ticket_id=tid, split=ticket_info[tid]["split"] if tid in ticket_info else "",
                             resolution_status=m["row"]["resolution_status"],
                             csat_score=m["row"]["csat_score"], resolved_at=m["row"]["resolved_at"],
                             handle_time_min=raw_h, handle_time_flag=flag)
    return records, published, review_rows, ticket_info, sorted(outcomes.values(), key=lambda r: r["ticket_id"]), fence, msgs


# --------------------------------------------------------------------------- writers
def write_jsonl(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path: Path, items: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(items)


def run(root: Path = ROOT, config_path: Path | None = None, out_root: Path | None = None,
        quiet: bool = False) -> dict:
    config_path = config_path or root / "configs" / "pipeline_config.json"
    cfg, cfg_sha = load_config(config_path)
    out_root = out_root or root
    proc = out_root / cfg["outputs"]["processed_dir"]
    quar = out_root / cfg["outputs"]["quarantine_dir"]
    snapshot = datetime.strptime(cfg["snapshot_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    started = datetime.now(timezone.utc)

    g1 = verify_inventory(root, cfg)
    gates = [g1]
    if not g1["passed"]:
        print("G1 failed: raw inputs changed or unknown files present", g1["detail"], file=sys.stderr)
        return {"status": "FAILED", "gates": gates}

    kb_records, kb_pub = process_knowledge(root, cfg, snapshot)
    msg_records, msg_pub, review_rows, ticket_info, outcomes, fence, msgs = process_tickets(root, cfg, snapshot)

    # ---- write outputs
    write_jsonl(proc / "knowledge" / "knowledge_articles.jsonl", sorted(kb_pub, key=lambda r: r["kb_id"]))
    for split in ("train", "validation", "test"):
        items = sorted((r for r in msg_pub if r["split"] == split), key=lambda r: (r["ticket_id"], r["turn_index"]))
        write_jsonl(proc / "interactions" / f"{split}.jsonl", items)
    write_csv(proc / "interactions" / "ticket_outcomes.csv", outcomes,
              ["ticket_id", "split", "resolution_status", "csat_score", "resolved_at", "handle_time_min", "handle_time_flag"])
    manifest = kb_records + msg_records
    mf = ["record_type", "source_id", "source_file", "source_record", "record_sha256", "outcome",
          "reason_codes", "details", "split", "output_path"]
    write_csv(proc / "manifest.csv", manifest, mf)
    q_rows = [{k: r[k] for k in ["record_type", "source_id", "source_file", "source_record", "record_sha256",
                                 "reason_codes", "details"]} for r in manifest if r["outcome"] == "quarantine"]
    write_csv(quar / "quarantine_log.csv", q_rows,
              ["record_type", "source_id", "source_file", "source_record", "record_sha256", "reason_codes", "details"])
    kb_review = [dict(source_id=r["source_id"], ticket_id="", split="", sender_role="kb_article",
                      reason_codes=r["reason_codes"], details=r["details"], redacted_text="",
                      raw_intent_label="", source_row=1) for r in kb_records if r["outcome"] == "review"]
    write_csv(quar / "review_queue.csv", kb_review + review_rows,
              ["source_id", "ticket_id", "split", "sender_role", "reason_codes", "details", "redacted_text",
               "raw_intent_label", "source_row"])

    # ---- counts
    def counts(recs):
        c = Counter(r["outcome"] for r in recs)
        return {"raw": len(recs), "publish": c["publish"], "review": c["review"], "quarantine": c["quarantine"]}
    kb_c, msg_c = counts(kb_records), counts(msg_records)
    reason_counts = Counter(code for r in manifest for code in r["reason_codes"].split("|") if code)

    # ---- dataset-level gates on the PROCESSED output
    pii_hits = []
    for r in msg_pub:
        if R.residual_pii(r["text"]):
            pii_hits.append(r["message_id"])
    for r in kb_pub:
        if R.contains_payment_card(r["body"]):
            pii_hits.append(r["kb_id"])
    gates.append({"gate": "G2_NO_RESIDUAL_PII", "severity": "critical", "passed": not pii_hits,
                  "detail": f"{len(pii_hits)} processed records with e-mail/phone/card patterns"})

    split_sets = defaultdict(set)
    for r in msg_pub:
        split_sets[r["ticket_id"]].add(r["split"])
    for r in review_rows:
        if r["ticket_id"]:
            split_sets[r["ticket_id"]].add(r["split"])
    overlap = [t for t, s in split_sets.items() if len(s) > 1]
    gates.append({"gate": "G3_NO_TICKET_ACROSS_SPLITS", "severity": "critical", "passed": not overlap,
                  "detail": f"{len(overlap)} tickets appear in more than one split"})

    raw_tickets_rows = len(msgs)
    acc_ok = (kb_c["raw"] == kb_c["publish"] + kb_c["review"] + kb_c["quarantine"]
              and msg_c["raw"] == msg_c["publish"] + msg_c["review"] + msg_c["quarantine"]
              and msg_c["raw"] == raw_tickets_rows and len(manifest) == len({(r["record_type"], r["source_record"], r["source_file"]) for r in manifest}))
    gates.append({"gate": "G4_ACCOUNTING_RECONCILES", "severity": "critical", "passed": acc_ok,
                  "detail": f"kb {kb_c['raw']}={kb_c['publish']}+{kb_c['review']}+{kb_c['quarantine']}; "
                            f"messages {msg_c['raw']}={msg_c['publish']}+{msg_c['review']}+{msg_c['quarantine']}"})

    covered = {r["category"] for r in kb_pub}
    missing_cov = sorted(set(cfg["in_scope_intents"]) - covered)
    gates.append({"gate": "G5_KB_INTENT_COVERAGE", "severity": "critical", "passed": not missing_cov,
                  "detail": f"intents without a published article: {missing_cov or 'none'}"})

    # ---- readiness metrics
    pub_by_ticket = defaultdict(list)
    for r in msg_pub:
        pub_by_ticket[r["ticket_id"]].append(r)
    all_tickets = sorted({m["row"]["ticket_id"] for m in msgs if m["row"]["ticket_id"]})
    complete = [t for t in all_tickets if any(x["is_ticket_question"] for x in pub_by_ticket.get(t, []))
                and any(x["sender_role"] == "agent" for x in pub_by_ticket.get(t, []))]
    publish_rate = msg_c["publish"] / msg_c["raw"]
    complete_rate = len(complete) / len(all_tickets)
    tg = cfg["targets"]
    gates.append({"gate": "T1_MESSAGE_PUBLISH_RATE", "severity": "target",
                  "passed": publish_rate >= tg["message_publish_rate_min"],
                  "detail": f"{publish_rate:.4f} vs target >= {tg['message_publish_rate_min']}"})
    gates.append({"gate": "T2_COMPLETE_THREAD_RATE", "severity": "target",
                  "passed": complete_rate >= tg["complete_thread_rate_min"],
                  "detail": f"{complete_rate:.4f} vs target >= {tg['complete_thread_rate_min']}"})

    split_counts = {s: {"messages": sum(1 for r in msg_pub if r["split"] == s),
                        "tickets": len({r["ticket_id"] for r in msg_pub if r["split"] == s})}
                    for s in ("train", "validation", "test")}
    cust_split = defaultdict(set)
    for r in msg_pub:
        cust_split[r["customer_ref"]].add(r["split"])
    critical_ok = all(g["passed"] for g in gates if g["severity"] == "critical")
    run_manifest = {
        "pipeline_version": cfg["pipeline_version"],
        "status": "PASSED" if critical_ok else "FAILED",
        "run_started_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_finished_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python": platform.python_version(),
        "config_path": config_path.relative_to(root).as_posix() if config_path.is_relative_to(root) else str(config_path),
        "config_sha256": cfg_sha,
        "inputs": g1["files"],
        "counts": {"knowledge_articles": kb_c, "ticket_messages": msg_c,
                   "total_records": {k: kb_c[k] + msg_c[k] for k in kb_c}},
        "reason_code_counts": dict(sorted(reason_counts.items())),
        "split": {"strategy": cfg["split"]["strategy"], "boundaries_local": [cfg["split"]["train_before_local"],
                  cfg["split"]["validation_before_local"]], "counts": split_counts,
                  "customers_in_multiple_splits": sum(1 for s in cust_split.values() if len(s) > 1),
                  "customers_total": len(cust_split)},
        "fitted_on_train": {"length_outlier_fence_chars": round(fence, 1)},
        "readiness_metrics": {
            "message_publish_rate": round(publish_rate, 4),
            "message_review_rate": round(msg_c["review"] / msg_c["raw"], 4),
            "message_quarantine_rate": round(msg_c["quarantine"] / msg_c["raw"], 4),
            "kb_publish_rate": round(kb_c["publish"] / kb_c["raw"], 4),
            "tickets_total": len(all_tickets), "tickets_complete_published": len(complete),
            "complete_thread_rate": round(complete_rate, 4),
            "pii_redactions_in_published_messages": sum(r["pii_redactions"] for r in msg_pub),
            "handle_time_flags": dict(Counter(o["handle_time_flag"] for o in outcomes)),
        },
        "gates": [{k: v for k, v in g.items() if k != "files"} for g in gates],
        "outputs": {
            "knowledge": "data/processed/knowledge/knowledge_articles.jsonl",
            "interactions": [f"data/processed/interactions/{s}.jsonl" for s in ("train", "validation", "test")],
            "ticket_outcomes": "data/processed/interactions/ticket_outcomes.csv",
            "manifest": "data/processed/manifest.csv",
            "quarantine_log": "data/quarantine/quarantine_log.csv",
            "review_queue": "data/quarantine/review_queue.csv",
        },
    }
    (proc / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    if not quiet:
        print(f"[{run_manifest['status']}] {cfg['pipeline_version']}")
        print(f"  knowledge: {kb_c}")
        print(f"  messages : {msg_c}")
        for g in run_manifest["gates"]:
            print(f"  {'PASS' if g['passed'] else 'FAIL'}  {g['gate']:<28} {g['detail']}")
    return run_manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--out-root", type=Path, default=None, help="write processed/quarantine under this folder")
    a = ap.parse_args()
    result = run(config_path=a.config, out_root=a.out_root)
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())
