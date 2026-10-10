# Data dictionary: Week 2 (Customer Support Assistant)

All data is synthetic. Pipeline version `week2-v1.0`.

## Raw: `data/raw/tickets/tickets_export_2026-09-30.csv` (one row per message)

| Field | Raw type | Meaning | Known issues |
|---|---|---|---|
| message_id | text | helpdesk message ID, assigned sequentially | 12 duplicated (export glitch) |
| ticket_id | text | thread ID; **group unit** for splitting | 4 blank |
| created_at | text | message time | 3 formats (ISO-Z, +07:00, naive local) + 5 invalid + 2 future |
| channel | text | email / chat / web form | 11 spellings |
| customer_ref | text | pseudonymous customer key | — |
| sender_role | text | `customer` or `agent` | — |
| message_text | free text | message body | personal data, payment data, Vietnamese, pasted e-mail chains, blanks |
| intent_label | text | agent-assigned intent, normally on the first customer message only | 29 spellings, 4 unmappable, 25 questions blank |
| resolution_status | text | **post-outcome** | — |
| csat_score | text | **post-outcome**, 1–5 survey | 55% blank (not random) |
| resolved_at | text | **post-outcome** | blank when unresolved |
| handle_time_min | text | **post-outcome**, minutes of agent time | 0, negative and > 480 values |

## Raw: `data/raw/knowledge_base/KB-*.md`
Front matter: `kb_id, title, category, owner, approved, last_reviewed, version`; the body follows the second `---`.

## Processed: `data/processed/knowledge/knowledge_articles.jsonl`

| Field | Type | Rule |
|---|---|---|
| kb_id, title, category, owner, version | string | from front matter; category ∈ 8 in-scope intents |
| approved | bool | always `true` (unapproved articles are quarantined) |
| last_reviewed / review_age_days | date / int | age at snapshot ≤ 365 days, otherwise review |
| body | string | paragraphs separated by blank lines, whitespace-normalised |
| n_paragraphs, word_count | int | quality statistics |
| content_sha256 | hex | hash of the case-folded body; unique among published |
| source_file, source_sha256 | string | lineage to the raw file |
| pipeline_version | string | `week2-v1.0` |

## Processed: `data/processed/interactions/{train,validation,test}.jsonl` (one row per published message)

| Field | Type | Rule |
|---|---|---|
| message_id, ticket_id | string | unchanged IDs |
| split | string | `train` before 1 Aug 2026, `validation` in August, `test` from 1 Sep (local time, by the ticket's first message) |
| created_at_utc | ISO-8601 Z | converted to UTC; naive values treated as UTC+07 (Assumed) |
| timestamp_source_format | string | `iso_utc`, `iso_offset` or `naive_local` |
| channel | string | ∈ {email, chat, web_form} |
| customer_ref | string | pseudonymous; not used as evidence |
| sender_role, turn_index | string / int | order inside the ticket |
| is_ticket_question | bool | true for the ticket's first customer message |
| ticket_intent | string | ∈ 8 intents; taken from the question's label |
| text | string | whitespace-normalised, e-mail and phone redacted to `[EMAIL]` / `[PHONE]` |
| char_len, pii_redactions | int | record-level quality statistics |
| source_row, source_sha256 | int / hex | lineage to the raw CSV row |
| pipeline_version | string | `week2-v1.0` |

**Never present in interactions:** `resolution_status`, `csat_score`, `resolved_at`, `handle_time_min`.

## Processed: `data/processed/interactions/ticket_outcomes.csv` (one row per ticket, baseline use only)
`ticket_id, split, resolution_status, csat_score, resolved_at, handle_time_min, handle_time_flag`.
`handle_time_flag` ∈ {ok, invalid_zero, invalid_negative, extreme_gt_480, missing}.

## Control files
- `data/processed/manifest.csv`: one row per **source record** (720): `record_type, source_id, source_file,
  source_record, record_sha256, outcome, reason_codes, details, split, output_path`.
- `data/processed/run_manifest.json`: version, config hash, input hashes, counts, reason-code counts, split counts,
  gate results, readiness metrics, run timestamps.
- `data/quarantine/quarantine_log.csv`: quarantined records with reason codes. It contains **no message text**, because
  quarantined text can hold payment data.
- `data/quarantine/review_queue.csv`: records that need a human decision, with redacted text (first 300 characters)
  and the split already assigned.

## Reason codes
Critical → quarantine: `KB_EMPTY_BODY, KB_NOT_APPROVED, KB_DUPLICATE_CONTENT, KB_MISSING_METADATA, KB_ID_MISMATCH,
MSG_DUPLICATE_EXACT, MSG_DUPLICATE_ID, MSG_MISSING_TICKET_ID, MSG_EMPTY_TEXT, MSG_INVALID_TIMESTAMP,
MSG_FUTURE_TIMESTAMP, MSG_PAYMENT_DATA, MSG_OUT_OF_SCOPE_LANGUAGE, MSG_INVALID_ROLE`.

Warning → review: `KB_STALE, KB_MISSING_OWNER, KB_UNKNOWN_CATEGORY, MSG_NEAR_DUPLICATE, MSG_LABEL_MISSING,
MSG_LABEL_UNMAPPED, MSG_LENGTH_OUTLIER, MSG_CHANNEL_UNMAPPED, THREAD_NO_QUESTION, THREAD_PENDING_REVIEW`.
