# Week 2: Data Readiness (Customer Support Assistant)

QuanSkill AI Engineering and Deployment, Chapter 4 (pp. 287–402). Student: **Nguyen Tien Viet Hung**.

This folder turns raw support data into **traceable, validated datasets** for the Week 1 MVP: a cited-answer assistant
for Tier-1 support agents. It does **not** build a model, embeddings, a RAG application or a UI.

> **All data is synthetic.** "ShopNova" is a fictional retailer. E-mail addresses use `example.com`, phone numbers are
> fake, and the only card number is the public test number `4111 1111 1111 1111`. No real personal data is included.

**Decision: READY WITH CONDITIONS.** See [`reports/week02_data_readiness.md`](reports/week02_data_readiness.md).
**Version label:** `week2-v1.0` (pipeline version and git tag).

## Folder structure

```
Week2/
  README.md
  requirements.txt
  QuanSkill_Chapter4_Week2_Homework_Hung.docx   homework answers (Part A–C)
  configs/pipeline_config.json                  every threshold, mapping and split boundary
  data/
    raw/                     original files, never modified
      SOURCE_INVENTORY.csv   one row per source, with SHA-256
      knowledge_base/        14 KB articles (Markdown + front matter)
      tickets/               helpdesk export, 706 message rows
    processed/               validated outputs + manifest.csv + run_manifest.json
    quarantine/              quarantine_log.csv (excluded) + review_queue.csv (needs a human)
  notebooks/
    02_data_profiling.ipynb  executed; HTML export next to it
  reports/
    week02_data_readiness.md (+ .pdf)
    figures/                 charts used in the notebook and report
  src/data/
    rules.py                 pure validation / normalisation functions
    build_dataset.py         the reproducible pipeline
    make_inventory.py        creates SOURCE_INVENTORY.csv (run once when data is obtained)
    generate_synthetic_data.py   created data/raw (seed 2026, run once)
  tests/                     21 pytest tests (rules + data contract)
  docs/data_dictionary.md    raw and processed schemas, reason codes
```

## Rerun the work

Requirements: **Python ≥ 3.10**. The pipeline itself uses only the standard library. The tests and the notebook need
the packages in `requirements.txt`. Run every command from **inside the `Week2` folder**; no absolute paths are used.

```bash
cd Week2

# 1. environment
python -m venv .venv
source .venv/bin/activate          # Windows Git Bash: source .venv/Scripts/activate
                                   # Windows cmd / PowerShell: .venv\Scripts\activate
pip install -r requirements.txt

# 2. pipeline  (input: data/raw/ ; outputs: data/processed/ and data/quarantine/)
python -m src.data.build_dataset
#   exit code 0 = all critical gates passed, 1 = a critical gate failed

# 3. tests
python -m pytest -q                # expected: 21 passed

# 4. notebook (reads the pipeline outputs; does not transform data)
jupyter nbconvert --to notebook --execute --inplace notebooks/02_data_profiling.ipynb
jupyter nbconvert --to html notebooks/02_data_profiling.ipynb
```

Optional: `python -m src.data.build_dataset --out-root /tmp/check` writes all outputs into another folder.
This is useful to compare two runs.

### Expected output (week2-v1.0)

```
[PASSED] week2-v1.0
  knowledge: {'raw': 14, 'publish': 9, 'review': 2, 'quarantine': 3}
  messages : {'raw': 706, 'publish': 547, 'review': 122, 'quarantine': 37}
  PASS  G1_INPUT_INTEGRITY           15 files match inventory hashes
  PASS  G2_NO_RESIDUAL_PII           0 processed records with e-mail/phone/card patterns
  PASS  G3_NO_TICKET_ACROSS_SPLITS   0 tickets appear in more than one split
  PASS  G4_ACCOUNTING_RECONCILES     kb 14=9+2+3; messages 706=547+122+37
  PASS  G5_KB_INTENT_COVERAGE        intents without a published article: none
  FAIL  T1_MESSAGE_PUBLISH_RATE      0.7748 vs target >= 0.9
  FAIL  T2_COMPLETE_THREAD_RATE      0.8130 vs target >= 0.85
```

The two **target** metrics are expected to fail in v1.0. They are conditions of the readiness decision; they are not
pipeline errors.

### Expected files after a run

| Path | Content |
|---|---|
| `data/processed/knowledge/knowledge_articles.jsonl` | 9 approved, unique articles |
| `data/processed/interactions/train.jsonl` / `validation.jsonl` / `test.jsonl` | 263 / 147 / 137 messages |
| `data/processed/interactions/ticket_outcomes.csv` | 230 tickets, post-outcome fields (baseline only) |
| `data/processed/manifest.csv` | 720 rows: one outcome and reason per source record |
| `data/processed/run_manifest.json` | version, config hash, input hashes, counts, gates, timestamps |
| `data/quarantine/quarantine_log.csv` | 40 records (no message text) |
| `data/quarantine/review_queue.csv` | 124 records |

All files except `run_manifest.json` (which holds run timestamps) are **byte-identical** between runs on the same
machine (test `test_pipeline_is_deterministic`).

## Trace one record back to its source

```bash
python - <<'PY'
import csv, json
from src.data.rules import record_hash
FIELDS = ["message_id","ticket_id","created_at","channel","customer_ref","sender_role","message_text",
          "intent_label","resolution_status","csat_score","resolved_at","handle_time_min"]
rec = next(json.loads(l) for l in open("data/processed/interactions/validation.jsonl", encoding="utf-8")
           if '"MSG-000223"' in l)
rows = list(csv.DictReader(open("data/raw/tickets/tickets_export_2026-09-30.csv", encoding="utf-8", newline="")))
raw = rows[rec["source_row"] - 1]
print(raw["created_at"], "->", rec["created_at_utc"])
print("hash matches:", record_hash([raw[f] for f in FIELDS]) == rec["source_sha256"])
PY
```

## Notes for Windows users

`.gitattributes` disables line-ending conversion for `data/raw/`. Without it, Git could change line endings on
checkout, and gate G1 (input hashes) would correctly stop the pipeline.

## Week 1 link

Week 1 problem framing: <https://github.com/Halleyaaa/QuanSkill_C3_W1_Homework_Hung>
