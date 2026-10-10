# QuanSkill Week 3 — ML Baseline

## Task
Classify a question–passage pair as relevant evidence (1) or not (0).

## Dataset
Rows: 192; questions: 48; documents: 48; prevalence: 0.250.
Synthetic teaching data: True.

## Split
Grouped by question_id. Validation selected the model and threshold. Test was used for final evaluation.

## Selection
Model: random_forest; threshold: 0.560.
Selection: maximum validation F1; baseline-ladder simplicity breaks ties.

## Final held-out test (teaching dataset only)
- accuracy: 0.8750
- precision: 1.0000
- recall: 0.5000
- f1: 0.6667
- f2: 0.5556
- specificity: 1.0000
- tn: 24
- fp: 0
- fn: 4
- tp: 4
- roc_auc: 0.8568
- average_precision: 0.8036
- brier: 0.1031

## Error review
False positives: 0; false negatives: 4.
Question hit rate (among questions with positives): 0.500.
Manually inspect source pages and annotate recurring error patterns.

## Limits
The synthetic corpus repeats passage patterns; this is a runnable teaching exercise, not a production or research performance claim.