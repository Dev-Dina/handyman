# Review Notebooks

These marimo notebooks are an interactive review layer over existing reports.
They do not retrain models, fetch data, call external services, or mutate source
artifacts.

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m marimo run notebooks/00_reports_map.py
.\.venv\Scripts\python.exe -m marimo run notebooks/01_classifier_experiments_review.py
.\.venv\Scripts\python.exe -m marimo run notebooks/02_rag_retrieval_review.py
```

Regenerate the report inventory first when reports change:

```powershell
.\.venv\Scripts\python.exe scripts/audit_reports.py
```
