"""Integration tests: run the pipeline into a temporary folder and check the data contract."""
import csv
import json
from pathlib import Path

import pytest

from src.data import build_dataset as B
from src.data import rules as R

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("run1")
    result = B.run(root=ROOT, out_root=out, quiet=True)
    return out, result


def read_csv(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_jsonl(p):
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]


def test_all_critical_gates_pass(run_dir):
    _, result = run_dir
    assert result["status"] == "PASSED"
    assert all(g["passed"] for g in result["gates"] if g["severity"] == "critical")


def test_every_source_record_has_exactly_one_outcome(run_dir):
    out, result = run_dir
    manifest = read_csv(out / "data/processed/manifest.csv")
    with open(ROOT / "data/raw/tickets/tickets_export_2026-09-30.csv", encoding="utf-8", newline="") as f:
        n_msgs = sum(1 for _ in csv.DictReader(f))
    n_kb = len(list((ROOT / "data/raw/knowledge_base").glob("KB-*.md")))
    assert len(manifest) == n_msgs + n_kb
    assert {r["outcome"] for r in manifest} <= {"publish", "review", "quarantine"}
    keys = [(r["source_file"], r["source_record"]) for r in manifest]
    assert len(keys) == len(set(keys))


def test_accounting_reconciles(run_dir):
    _, result = run_dir
    for c in result["counts"].values():
        assert c["raw"] == c["publish"] + c["review"] + c["quarantine"]


def test_non_published_records_have_reasons(run_dir):
    out, _ = run_dir
    for r in read_csv(out / "data/processed/manifest.csv"):
        assert (r["outcome"] == "publish") == (r["reason_codes"] == "")


def test_published_counts_match_files(run_dir):
    out, result = run_dir
    n = sum(len(read_jsonl(out / f"data/processed/interactions/{s}.jsonl")) for s in ("train", "validation", "test"))
    assert n == result["counts"]["ticket_messages"]["publish"]
    kb = read_jsonl(out / "data/processed/knowledge/knowledge_articles.jsonl")
    assert len(kb) == result["counts"]["knowledge_articles"]["publish"]


def test_no_ticket_in_two_splits(run_dir):
    out, _ = run_dir
    seen = {}
    for s in ("train", "validation", "test"):
        for r in read_jsonl(out / f"data/processed/interactions/{s}.jsonl"):
            assert seen.setdefault(r["ticket_id"], s) == s


def test_no_post_outcome_fields_in_interactions(run_dir):
    out, _ = run_dir
    banned = {"resolution_status", "csat_score", "resolved_at", "handle_time_min"}
    for s in ("train", "validation", "test"):
        for r in read_jsonl(out / f"data/processed/interactions/{s}.jsonl"):
            assert not banned & set(r)


def test_no_residual_pii_or_out_of_scope_text(run_dir):
    out, _ = run_dir
    for s in ("train", "validation", "test"):
        for r in read_jsonl(out / f"data/processed/interactions/{s}.jsonl"):
            assert R.residual_pii(r["text"]) == []
            assert R.detect_language(r["text"]) == "en"
            assert r["text"].strip()


def test_quarantine_log_contains_no_raw_text(run_dir):
    out, _ = run_dir
    rows = read_csv(out / "data/quarantine/quarantine_log.csv")
    assert rows and "message_text" not in rows[0] and "redacted_text" not in rows[0]
    assert not any("4111" in v for r in rows for v in r.values())


def test_published_kb_is_approved_and_unique(run_dir):
    out, _ = run_dir
    kb = read_jsonl(out / "data/processed/knowledge/knowledge_articles.jsonl")
    assert all(a["approved"] for a in kb)
    assert len({a["content_sha256"] for a in kb}) == len(kb)


def test_pipeline_is_deterministic(run_dir, tmp_path):
    out1, _ = run_dir
    B.run(root=ROOT, out_root=tmp_path, quiet=True)
    for rel in ["data/processed/manifest.csv", "data/processed/knowledge/knowledge_articles.jsonl",
                "data/processed/interactions/train.jsonl", "data/processed/interactions/validation.jsonl",
                "data/processed/interactions/test.jsonl", "data/quarantine/quarantine_log.csv",
                "data/quarantine/review_queue.csv"]:
        assert (out1 / rel).read_bytes() == (tmp_path / rel).read_bytes(), rel


def test_raw_data_untouched():
    inv = read_csv(ROOT / "data/raw/SOURCE_INVENTORY.csv")
    for r in inv:
        assert R.sha256_bytes((ROOT / r["location"]).read_bytes()) == r["sha256"]
