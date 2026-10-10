# W3: Chapter 5, Build the Simplest Baseline First

Student: **Nguyen Tien Viet Hung** · Cohort K10 · Track: Customer Support Assistant

> All metrics come from a **teaching run on the notebook's built-in synthetic data** (`USE_UPLOAD = False`).
> They are not evidence of real-world performance.

## Submission items

| Item | File |
|---|---|
| Executed notebook (outputs visible) | [`notebooks/QuanSkill_Chapter5_ML_Baselines_Executed_Hung.ipynb`](notebooks/QuanSkill_Chapter5_ML_Baselines_Executed_Hung.ipynb) (+ `.html` export) |
| Written response (3 pages) | [`QuanSkill_Chapter5_Week3_Response_Hung.pdf`](QuanSkill_Chapter5_Week3_Response_Hung.pdf) / `.docx` |
| Controlled experiment 2D (exploratory) | [`notebooks/QuanSkill_Chapter5_Run2_ControlledExperiment_C10.ipynb`](notebooks/QuanSkill_Chapter5_Run2_ControlledExperiment_C10.ipynb) |
| Saved artifact and run outputs | `outputs/run1_formal/` (joblib, validation CSV, generated report) |

## Key results (run 1, the formal run)

- Data: 192 pairs, 48 questions, prevalence 0.250. Grouped split: train 33, validation 7, test 8 questions. Question sets are disjoint.
- Selected on validation F1: **random forest**, τ = 0.56 (validation F1 0.769, AP 0.766).
- **Final test (once):** TP 4 · FP 0 · TN 24 · FN 4 → F1 0.667, recall 0.500, AP 0.804. Question hit rate 0.500.
- 2D (sparse TF–IDF LR, C = 1 → 10): validation AP 0.246 → 0.260, still about chance. This supports a representation problem rather than a regularisation problem.
- Decision: fix the label issue first (2 of the 4 FNs come from index-assigned labels), then test learned representations in Week 4.

## Notebook edits and seeds

- No original cell was changed in run 1. Section 11 (student analysis, read-only) was appended at the end.
- Run 2 changes exactly one line: `LogisticRegression(..., C=10.0)` in the sparse TF–IDF pipeline.
- Seeds: `GroupShuffleSplit` 42 / 43; all models `random_state=42`.
- Environment: Python 3.13, scikit-learn 1.9.1, numpy 2.5.3, pandas 3.0.5. Results in Colab may differ slightly if its library versions differ.

## Rerun

```bash
cd W3/notebooks
pip install -r ../requirements.txt
jupyter nbconvert --to notebook --execute QuanSkill_Chapter5_ML_Baselines_Executed_Hung.ipynb --output rerun.ipynb
```

The notebook writes its artifact to `quanskill_ch5_output/` (in Colab: `/content/quanskill_ch5`).
Only load a `.joblib` file that your own run produced.
