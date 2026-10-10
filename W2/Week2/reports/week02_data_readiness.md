# Week 2 Data Readiness Report: Customer Support Assistant

| Item | Value |
|---|---|
| Student | Nguyen Tien Viet Hung |
| Course | QuanSkill AI Engineering and Deployment, Chapter 4 (pp. 287–402) |
| Track | Customer Support Assistant (same as Week 1) |
| Pipeline version | `week2-v1.0`, config SHA-256 `4c7e2228497ced92…` (full value in `data/processed/run_manifest.json`) |
| Data | **Synthetic.** Fictional retailer "ShopNova"; no real personal or company data |
| Decision | **READY WITH CONDITIONS** (section 12) |

Evidence labels used in this report: **Observed** (measured in this dataset), **Estimated**, **Assumed**, **Unknown**.
Every number marked *Observed* was computed by the pipeline or the notebook. Because the dataset is synthetic, an
*Observed* value describes this dataset only. It is not evidence about a real support team.

---

## 1. Project and intended AI task

**Week 1 problem (unchanged).** Tier-1 support agents re-answer repeated policy questions by searching scattered sources
by hand, which is slow and inconsistent.

**Intended AI task (Week 1 MVP).** Given an agent's English-language question about return, refund, delivery, warranty,
order-change, account or payment policy, retrieve the relevant **approved** knowledge passages and draft a short cited
answer, or abstain, for the agent to review.

**What Week 2 must deliver for that task**

| Dataset | Role in the next stage | Output |
|---|---|---|
| Knowledge | The **only** evidence source the assistant may cite | `data/processed/knowledge/knowledge_articles.jsonl` |
| Interactions | Realistic customer questions for **evaluation** (never used as evidence) | `data/processed/interactions/{train,validation,test}.jsonl` |
| Ticket outcomes | Business baseline B₀ (handle time) only. Post-outcome fields, never features. | `data/processed/interactions/ticket_outcomes.csv` |

**Out of scope for Week 2:** modelling, embeddings, chunking, vector index, RAG, prompts, UI and deployment.

## 2. Raw-data inventory and provenance

Full inventory with SHA-256 hashes: `data/raw/SOURCE_INVENTORY.csv` (15 sources). All raw files are preserved unchanged.
Gate **G1** re-hashes them on every run and stops the pipeline if any hash differs.

| Source ID | Type | Location | Origin / owner | Collection | Obtained | Volume | Refresh | Role | Sensitivity | Known limitation |
|---|---|---|---|---|---|---|---|---|---|---|
| SRC-KB-001 … SRC-KB-014 | Markdown + front matter | `data/raw/knowledge_base/KB-*.md` | ShopNova help-center CMS (synthetic); owner per article | CMS export, 1 file per article | 2026-09-30 | 14 articles | on policy change; owner review yearly | knowledge evidence | internal, no personal data | approval and review dates are self-reported |
| SRC-TICKETS-2026-09-30 | CSV | `data/raw/tickets/tickets_export_2026-09-30.csv` | ShopNova helpdesk (synthetic) | full export, tickets created 1 Jun – 29 Sep 2026 | 2026-09-30 | 706 rows, 12 columns | weekly (planned) | evaluation questions and reference replies | confidential if real (free text may hold personal and payment data) | mixed timestamp formats; labels optional; duplicated rows |

**How the data was produced.** `src/data/generate_synthetic_data.py` (seed 2026) was run once. It injects realistic
defects on purpose so that the readiness controls can be tested. The ticket CSV SHA-256 is `b9dae651…cb60b7`.

**Stable identifiers.** Sources: `SRC-…`. Articles: `kb_id` (KB-001…). Messages: `message_id` (MSG-000001…).
Threads: `ticket_id` (TCK-10001…). Every record also carries `record_sha256`, the hash of its raw bytes or raw field
values.

**Lineage.**

```
data/raw/tickets/tickets_export_2026-09-30.csv  (sha256 b9dae651…, row 223)
  └─ build_dataset.py week2-v1.0: parse → hash row → critical rules → whitespace/UTC/channel/label normalisation
       → PII redaction → thread rules → split (temporal, by ticket) → length fence (fitted on train) → outcome
        ├─ data/processed/manifest.csv            source_id=MSG-000223, record_sha256=79cbda68…, outcome=publish
        └─ data/processed/interactions/validation.jsonl  message_id=MSG-000223, source_row=223, source_sha256=79cbda68…
```

**Trace example (Observed).** The published record `MSG-000223` in `validation.jsonl` has `source_row = 223` and
`source_sha256 = 79cbda68c34a…ff542`. The manifest row for MSG-000223 shows the same hash, file and row, with
outcome `publish`. Re-hashing raw row 223 reproduces this value (README, "Trace one record"). The raw file hash
matches the inventory (G1). The raw value `2026-08-05 15:56:00` (naive local time) became `2026-08-05T08:56:00Z`,
and `delivery time` became `delivery_time`.

## 3. Raw profiling baseline (before any transformation)

Source: `notebooks/02_data_profiling.ipynb`, Part 1 (HTML export alongside the notebook).

| Measure | Value (Observed) |
|---|---|
| Ticket export size | 706 rows × 12 columns, all loaded as text |
| Distinct `message_id` | 694 of 706, so 12 duplicate rows |
| Distinct tickets | 230, plus 4 rows with blank `ticket_id` |
| Blank `message_text` (after whitespace trim) | 6 (0.8%) |
| `created_at` formats | ISO-UTC 428 (60.6%), +07:00 offset 177 (25.1%), **naive** 96 (13.6%), **invalid 5 (0.7%)**; **2 future** |
| `channel` spellings | 11 spellings for 3 channels |
| `intent_label` spellings (non-blank) | 29, of which 4 cannot be mapped |
| Ticket questions without label | 25 / 229 (10.9%): **Monday 30.0% (9/30)** vs other days 8.0% (16/199) |
| Message length (chars) | median 85, Q3 137.5, max 9,011 (4 pasted e-mail chains) |
| Personal-data patterns in raw text | e-mail 17 rows, phone 11 rows, payment card 3 rows |
| Non-English rows | 6 (Vietnamese) |
| Handle time (ticket level) | 222 plausible: median **13.1 min**, mean 14.17, p90 22.37; 3 zero, 2 negative, 3 > 480 min |
| CSAT missing | resolved 47.4%, pending 91.3%, escalated 100% |
| Knowledge base | 14 articles: 1 empty body, 1 exact duplicate, 1 draft (not approved), 1 stale (694 days), 1 without owner |

Figures: `reports/figures/chart1_label_missing_by_weekday.png`, `chart2_message_length.png`, `chart3_handle_time.png`,
`chart4_tickets_per_week.png`. Each one has a written interpretation in the notebook.

## 4. Metadata and schema quality

- **Ticket schema.** 12 columns are present and named as documented (`docs/data_dictionary.md`). Types are loaded as text
  first, then validated per field: timestamps are parsed explicitly, and `handle_time_min` is converted to a number only
  in the outcome table. **4 schema violations:** blank `ticket_id`. **5:** unparseable timestamps. `sender_role` is
  valid in all 706 rows.
- **Category domains.** `channel` maps to `{email, chat, web_form}` (11 → 3, all mapped). `intent_label` maps to 8
  approved intents. 4 values (`urgent`, `see notes`, `misc??`, `TBD`) remain unmapped and go to **review**.
- **Knowledge metadata.** All 7 required front-matter fields are present in 14/14 articles. One article has an empty
  `owner` value (KB-014). `kb_id` matches the filename in 14/14 articles.
- **Processed schema.** Defined and documented in `docs/data_dictionary.md`. Every published record carries
  `pipeline_version`, `source_*` lineage fields and, for messages, `split`.

## 5. Extraction and loading quality

- **Knowledge.** 13/14 articles extracted to non-trivial text. **KB-009 extracted to 0 characters** (extraction failure)
  and is quarantined, not published as an empty source. Paragraph structure is preserved (published articles have
  `n_paragraphs` ≥ 1).
- **Tickets.** All 706 rows were parsed by the CSV reader, including multi-line quoted text. No row was dropped by the
  loader: the manifest has exactly 706 message rows.
- **Fidelity check.** In the 15-record manual sample, the processed text equals the whitespace-normalised, redacted raw
  text in **5/5** published rows, and the UTC timestamp is correct in **5/5** (section 9).

## 6. Quality issues found (issue register)

| # | Issue | Evidence (Observed) | Severity | Treatment | Validation after treatment |
|---|---|---|---|---|---|
| Q1 | Exact duplicate rows | 12 rows identical in all fields | Critical | keep first, quarantine copies (`MSG_DUPLICATE_EXACT`) | 0 duplicate `message_id` in processed output |
| Q2 | Customer re-sends | 6 same-text messages in the same ticket within 30 s | Warning | review (`MSG_NEAR_DUPLICATE`) | not in processed output; listed in review queue |
| Q3 | Blank group key | 4 rows without `ticket_id` | Critical | quarantine; thread and split cannot be protected | G3: 0 tickets across splits |
| Q4 | Empty text | 6 rows | Critical | quarantine | 0 empty texts published |
| Q5 | Mixed or invalid timestamps | 96 naive, 5 invalid, 2 future | Critical (invalid/future); transform (naive) | convert to UTC (naive treated as UTC+07, *Assumed*); quarantine invalid and future | all published `created_at_utc` in ISO-Z; 5/5 manual check |
| Q6 | Category spellings | 11 channel and 29 label spellings | Transform / Warning | map via config; unmapped label → review | processed channel ∈ 3 values; intents ∈ 8 values |
| Q7 | Missing question labels (MAR, Monday-heavy) | 25 / 229 questions | Warning | review for human labelling; **no** deletion and **no** imputation | 0 published questions without intent |
| Q8 | Extreme length | 4 messages > fence of 371 chars (max 9,011) | Warning | review (trim pasted chains); fence fitted on **train only** | 0 published messages > 371 chars |
| Q9 | Personal data | 17 e-mail, 11 phone rows | Transform | redact to `[EMAIL]` / `[PHONE]` (18 replacements in published rows) | G2: 0 residual patterns |
| Q10 | Payment-card numbers | 3 rows | Critical | quarantine; never redact-and-keep; the text is not copied to the log | G2 = 0; quarantine log holds no text |
| Q11 | Out-of-scope language | 6 Vietnamese rows | Critical (scope) | quarantine (`MSG_OUT_OF_SCOPE_LANGUAGE`) | 0 non-English published |
| Q12 | Post-outcome fields | `resolution_status`, `csat_score`, `resolved_at`, `handle_time_min` | Leakage | removed from interactions; ticket-level table for baseline only | test: 0 such fields in interactions |
| Q13 | Impossible or extreme handle time | 3 zero, 2 negative, 3 > 480 min | Flag | `handle_time_flag`; excluded from B₀; extremes **kept and flagged** | flags 222 ok / 3 zero / 2 negative / 3 extreme |
| Q14 | Weak labels and reference truth | wrong label on a quarantined row; generic agent reply to a specific question | Warning | agent replies not used as gold answers; label audit | audit 20/20 correct (Wilson 95% lower bound ≈ 84%) |
| Q15 | KB: empty, duplicate, draft | KB-009, KB-011, KB-013 | Critical | quarantine | 9 published, all approved and unique |
| Q16 | KB: stale or ownerless | KB-012 (694 days), KB-014 (no owner) | Warning | review; owner sign-off required | not published |
| Q17 | CSAT missingness (MNAR/MAR) | 47.4% vs 91.3% vs 100% by status | Note | not used in Week 2; any later use must report response bias | — |

## 7. Transformations applied

All transformations are in `src/data/build_dataset.py`, with rule functions in `src/data/rules.py` and settings in
`configs/pipeline_config.json`. They are conservative: every transformation is reversible through `source_row` and
`source_sha256`, and none invents a value.

1. Unicode NFC normalisation and whitespace collapse of text and article paragraphs.
2. Timestamp conversion to UTC (ISO-Z); naive values interpreted as UTC+07 (**Assumed**, to be confirmed by the source owner).
3. Channel and intent normalisation through explicit mapping tables. Unmapped values are **not** guessed.
4. Redaction of e-mail and phone numbers. Payment cards are never redacted-and-kept: they are quarantined.
5. Ticket-level intent propagated from the question to the rest of the thread (`ticket_intent`).
6. Post-outcome fields moved out of the interaction records.
7. Length-outlier fence = Q3 + 3·IQR, **fitted on the train split only** (371 chars) and applied to all splits.

Not applied on purpose: no label imputation, no deletion of extreme values, no translation, no chunking or embedding.

## 8. Published, reviewed, quarantined and excluded records

| Dataset | Raw | Published | Review | Quarantine | Check |
|---|---|---|---|---|---|
| Knowledge articles | 14 | 9 | 2 | 3 | 14 = 9 + 2 + 3 ✔ |
| Ticket messages | 706 | 547 | 122 | 37 | 706 = 547 + 122 + 37 ✔ |
| **Total records** | **720** | **556** | **124** | **40** | **720 = 556 + 124 + 40 ✔** |

- **Quarantine (37 messages):** exact duplicates 12 (one is also Vietnamese), empty text 6, Vietnamese 5, invalid
  timestamp 5, missing ticket_id 4, payment data 3, future timestamp 2. **Knowledge (3):** KB-009 empty, KB-011
  duplicate of KB-003, KB-013 draft.
- **Review (122 messages):** label missing 25, label unmapped 4, length outlier 4, near duplicate 6 (one also
  thread-held), thread held because its question is in review 61, thread without a usable question 22. **Knowledge (2):**
  KB-012 stale, KB-014 no owner. Review rows are in `data/quarantine/review_queue.csv` with their split already assigned,
  so released records go to the correct split.
- **Excluded by design (fields, not records):** the four post-outcome fields are excluded from interactions. Vietnamese
  messages are excluded because they are out of MVP scope, not because they are bad data.
- **Published interactions:** 547 messages (276 customer, 271 agent), 188 tickets, 188 labelled questions.
  Splits: train 92 tickets / 263 messages, validation 49 / 147, test 47 / 137.

**Readiness metrics (Observed).** Message publish rate 77.48% (**target ≥ 90%, missed**). Complete-thread rate
187/230 = 81.30% (**target ≥ 85%, missed**). Knowledge publish rate 9/14 = 64.29%. The KB covers 8/8 intents.
Residual personal data: 0.

## 9. Manual validation performed

- **Sample 1, fidelity.** Stratified random sample, `random_state=42`: **15 ticket messages**, 5 per outcome.
  Results: published text faithful 5/5; UTC conversion correct 5/5; channel and label mapping correct; the quarantine
  reason was correct for 5/5 and the review reason was correct for 5/5.
- **Sample 2, label accuracy.** `random_state=7`: **20 published ticket questions**. 20/20 labels match the question
  (100%; Wilson 95% lower bound ≈ 84%).
- **Findings that changed the plan:** (a) a quarantined row carries a wrong label (`Warranty` on a double-charge
  message), so labels are weak; (b) agent replies can be generic and not answer the specific question, so agent replies
  are **not** a gold reference; (c) published questions reduce to only **26 distinct wordings** after masking order
  numbers, so the dataset is not representative of real phrasing.

## 10. Leakage risks and evaluation split

- **Future unseen data** means customer questions that arrive **after** the knowledge base and any tuning examples were
  frozen.
- **Split:** temporal, with **ticket** as the group unit. Train is before 1 Aug 2026 (local), validation is August, and
  test runs from 1 Sep to the export snapshot. A ticket is assigned by its first message, so a whole thread stays in one
  split. G3: **0 tickets across splits**.
- **Target leakage:** `resolution_status`, `csat_score`, `resolved_at` and `handle_time_min` are only known after the
  outcome, so they are excluded from interactions (test-enforced). The agent reply in the same thread is the outcome of
  the question, so it must never be retrievable evidence; evidence comes **only** from the knowledge base.
- **Temporal leakage:** 2 future-dated messages are quarantined. Knowledge used to answer a test question must have
  existed at question time. This is a condition for Week 3, because `last_reviewed` is not an effective-from date.
- **Group leakage:** 0 tickets cross splits. **1 of 186 customers** appears in two splits. This is acceptable for KB-only
  retrieval and must be re-checked if any stage learns from customer history.
- **Preprocessing leakage:** the only learned parameter, the length fence, is fitted on train only (371 chars). The
  mapping tables are fixed by domain rules, not learned from data.
- **Audit question for every candidate feature or evidence source:** *Would this information genuinely exist and be
  accessible at the exact moment the system must make its decision or answer?*

## 11. Remaining risks and limitations

1. **Synthetic data.** The results prove the controls, not real-world quality. Question diversity is low (26 wordings),
   so retrieval scores measured on it would be optimistic. *Unknown* for real data.
2. **Targets missed.** Publish rate 77.5% (target 90%) and complete-thread rate 81.3% (target 85%). The cause is the
   review queue (33 questions held), not data loss.
3. **Timezone assumption.** Naive timestamps (96 rows) are assumed to be UTC+07. If they are wrong, tickets near
   1 Aug and 1 Sep could change split.
4. **Label quality** is audited on 20 items only. Labels in the source can be wrong (finding 9a).
5. **Small evaluation splits.** 47–49 tickets each. Per-intent metrics are unstable (e.g. `payment_issue` has
   2 questions in validation).
6. **Heuristic detectors.** The PII and language detectors are regular-expression heuristics. They pass all tests, but
   they could miss unusual formats such as names or addresses, which are not detected at all.
7. **Knowledge freshness** relies on self-reported `last_reviewed` dates.

## 12. Final readiness decision and conditions before the next stage

All critical gates pass (G1 input integrity, G2 no residual personal data, G3 split integrity, G4 accounting,
G5 knowledge coverage). The published knowledge (9 approved, unique articles covering 8/8 intents) and the 547
published interactions are traceable, reproducible and safe for a Week 3 **retrieval experiment**. The data is not
fully ready, because both target metrics are missed and several assumptions are still open.

**Conditions before the next stage**

| # | Condition | Owner | Evidence of completion |
|---|---|---|---|
| C1 | Label the 33 held questions (25 missing, 4 unmapped, 4 over-length) and release their threads; rerun and reach publish rate ≥ 90% and complete-thread rate ≥ 85% | Support lead + student | new `run_manifest.json` with T1 and T2 passed |
| C2 | Owner sign-off for KB-012 (stale) and an owner for KB-014; KB-013 stays excluded until approved; re-extract KB-009 | Policy Team / Logistics | KB review recorded; rerun shows them published or still excluded with reason |
| C3 | Confirm the timezone of naive timestamps with the helpdesk owner | Source owner | config note changed from *Assumed* to *Confirmed* |
| C4 | Build the reviewed golden question–answer set from published **validation/test** questions; do not use agent replies as gold | Student + senior agent | golden set file with reviewer IDs |
| C5 | Before any claim about real performance, rerun the same pipeline on a real, de-identified export | Data owner | new inventory and run manifest |

**Final status: READY WITH CONDITIONS**

## 13. Evidence paths

| Evidence | Path |
|---|---|
| Raw source inventory (hashes) | `data/raw/SOURCE_INVENTORY.csv` |
| Raw data (synthetic, unchanged) | `data/raw/knowledge_base/`, `data/raw/tickets/tickets_export_2026-09-30.csv` |
| Manifest (1 row per source record) | `data/processed/manifest.csv` |
| Run manifest (version, config hash, counts, gates) | `data/processed/run_manifest.json` |
| Processed knowledge | `data/processed/knowledge/knowledge_articles.jsonl` |
| Processed interactions | `data/processed/interactions/train.jsonl`, `validation.jsonl`, `test.jsonl` |
| Ticket outcomes (baseline only) | `data/processed/interactions/ticket_outcomes.csv` |
| Quarantine log | `data/quarantine/quarantine_log.csv` |
| Review queue | `data/quarantine/review_queue.csv` |
| Profiling notebook + HTML export | `notebooks/02_data_profiling.ipynb`, `notebooks/02_data_profiling.html` |
| Figures | `reports/figures/chart1…chart6*.png` |
| Pipeline and rules | `src/data/build_dataset.py`, `src/data/rules.py`, `configs/pipeline_config.json` |
| Inventory and data generator | `src/data/make_inventory.py`, `src/data/generate_synthetic_data.py` |
| Tests (21) | `tests/test_rules.py`, `tests/test_pipeline.py` |
| Data dictionary | `docs/data_dictionary.md` |

**READY WITH CONDITIONS**
