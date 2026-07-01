# Handyman — Next Steps & Handoff

> Forward-plan doc so a fresh session (or you in a month) can resume the data
> work without re-deriving anything. Last updated 2026-06-29.

## Current state

Handyman is **portfolio-complete and pushed to `main`, CI green**:

- Cleaned repo, dark-indigo UI redesign, polished React chat widget.
- Working chat path: **Groq LLM + tool calling** (RAG + classifier + entities + summarize + memory tools).
- README with verified Mermaid diagrams and **4 screenshots** (`screenshots/01-login.png`, `02-chat.png`, `03-evals.png`, `04-rag.png`).
- The **classifier screenshot is deliberately deferred** until the model improves (see Known issues + Planned data work below).

Recent fixes already on `main` this session:
- `fix: harden groq key handling and redact bearer tokens` (`d6f686a`) + RUNBOOK note (`c12bd81`).
- `fix: handle title-only issues and surface Groq errors gracefully` (`94d0fd5`).

---

## Known issues — classifier

Diagnosed in detail on 2026-06-29. Numbers below are pulled directly from the
served model (`artifacts/classical/best_model.joblib`) and the eval reports
(`reports/classical/best_classical_eval.json`, `reports/classical/confusion_matrix.csv`).
The runtime/served classifier is the **LogisticRegression TF-IDF** fallback
(CodeBERT is the eval-best primary but needs GPU and isn't served).

### 1. The model learned template boilerplate, not bug semantics

TF-IDF + LogisticRegression keys "bug" off the **GitHub bug-report template
fields** rather than what an issue means. A free-text issue without that
template (e.g. a CrashLoopBackOff report written as prose) has nothing to fire
the "bug" features and drifts into **`question`**, the residual catch-all class.

**Top-12 positive features per class** (the learned vocabulary signature):

| Class | Top features | Read |
|---|---|---|
| **bug** | `version, kubeadm, details, url, bug, happened, what happened, os, linux, reproduce, to reproduce, as possible` | **Template boilerplate** — "What happened?", "Environment: OS / kubeadm version", "Steps to reproduce", "as much detail as possible" |
| **docs** | `docs, document, examples, documentation, md, user, guide, user user, doc, getting started, example, should` | Topical doc words (genuinely semantic — docs is the strong class) |
| **feature** | `you like, this needed, what would, be added, would you, like to, would, needed, why is, is this, added, like` | Feature-request template phrasing ("What would you like to be added?", "Why is this needed?") — template-ish but semantically aligned |
| **question** | `21, k8s, how, am, is there, error, image url, how to, version, 2021, and and, me` | **Weak/noisy residual** — number junk (`21`, `2021`), artifacts (`and and`), conversational (`me`, `am`, `how`). The catch-all bin. |

Key tell from the per-token analysis: the term **`crashloopbackoff` itself leans
`question`, not `bug`** — because people *asking* "how do I fix CrashLoopBackOff?"
used it as much as templated bug reports did, and bag-of-words only sees
co-occurrence, not that a crash is a defect.

### 2. "question" is the weakest class; bug↔question is the dominant confusion axis

**Test per-class metrics** (`reports/classical/best_classical_eval.json`, test split, 90/class, overall accuracy 0.7139, macro-F1 0.6938):

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| feature | 0.835 | 0.900 | **0.866** | 90 |
| docs | 0.862 | 0.833 | **0.847** | 90 |
| bug | 0.608 | 0.844 | **0.707** | 90 |
| **question** | **0.490** | **0.278** | **0.355** | 90 |

`question` F1 (0.355) is less than half of feature/docs; recall 0.278 means it
catches barely a quarter of real questions.

**Confusion matrix** (`reports/classical/confusion_matrix.csv`, rows = actual, cols = predicted):

```
actual\predicted   bug  feature  docs  question
bug                 76      3      2       9
feature              4     81      1       4
docs                 0      2     75      13
question            45     11      9      25
```

- **45 of 90** actual `question`s are misread as `bug`; **9 of 90** `bug`s are misread as `question`.
- `bug ↔ question` is the weakest decision boundary in the model (54 cross-errors on that axis).

### 3. Train/serve normalization skew — REAL BUG, fix first

The classifier is trained and served on **different text**:

- **Training** vectorizes the normalized `model_text` field — `ml/classical_baseline.py:52`
  (`texts = [str(row.get("model_text") or "") for row in rows]`). `model_text` is
  produced by the normalization in **`ml/text_preprocessing.py`** (URLs → token,
  usernames → `<USER>`, number/non-ASCII handling, etc.).
- **Serving** feeds **raw** `title\n\nbody` with no normalization —
  `model_server/classifier.py:23-28` (`_combine_issue_text` → `f"{title}\n\n{body}"`),
  then `model.predict([text])` at `model_server/classifier.py:54-57`.

So in production the model sees raw URLs, usernames, markdown and bare numbers
(e.g. `v1.29`, `2021`) that training never saw in that form — note `2021` and
`image url` literally appear in the `question` signature above. This adds noise
on top of an already-weak boundary. **Small, clearly-correct fix — do it first.**

### 4. Source data is noisy

The original Kubernetes issue corpus was assembled under a deadline and carries:
Reddit-sourced markdown, time discrepancies (`created_at` / `closed_at`), and
general noise. Splits are balanced (420/420/420/420 train, 90/class val+test) —
so the weakness is **vocabulary/semantics, not class imbalance**.

---

## Planned data work (phased, priority order)

### Phase 1 — Fix the train/serve normalization skew *(do first, regardless of the rest)*
Make serving apply the **same** `model_text` normalization used in training, so
the model sees identical tokens in prod and train. Small, clearly correct, and
independently valuable. Touch `model_server/classifier.py` (apply the
`ml/text_preprocessing.py` normalization before vectorizing) — confirm the
normalization module is importable from `model_server` without pulling torch.

### Phase 2 — Re-clean source data
Strip Reddit markdown, fix the time discrepancies, de-noise. **Document
before/after data quality** (counts, examples removed, distribution shifts) —
the documentation is part of the deliverable.

### Phase 3 — Re-split, retrain, re-eval with honest before/after metrics
Re-run split → train → eval. The deliverable is the **documented comparison**
(per-class F1, confusion matrix, before vs after), not just a higher number.
Existing scripts: `ml/split_dataset.py`, `ml/classical_baseline.py`,
`ml/classical/compare_classical.py`; eval reports land in `reports/classical/`.

### Phase 4 *(optional)* — Representation upgrade
Bag-of-words fundamentally can't encode "a crash is a defect," so even clean data
may leave `bug ↔ question` fuzzy. Consider an embedding/transformer classifier —
the infra already exists (`model_server` + `ml/finetune.py`; CodeBERT is already
the eval-best at macro-F1 0.7061 but needs GPU). **Decide after Phase 3** whether
the lift over a cleaned TF-IDF model justifies serving a heavier model.

---

## Open question — decide before starting

**Is the goal a better model (Phases 1–4) or a documented findings story (the
diagnosis itself is already a strong portfolio artifact)?**

**Recommendation:** do **Phases 1–3** (high value either way — Phase 1 is a real
bug, Phases 2–3 produce an honest before/after narrative). **Defer Phase 4**
until Phase 3 shows whether clean TF-IDF is "good enough."

---

## Operational gotchas (so the next session doesn't lose time)

- **Dev Vault is ephemeral.** Every `docker compose up --build` or restart
  recreates the `vault` container (`server -dev`, no volume) and **wipes
  `secret/llm/groq_api_key`**. `vault-init.sh` only restores the `secret/handyman`
  placeholders. Put a **fresh** Groq key in `.env` (the previous key is revoked)
  and reseed each time — trim-safe, value never in argv/history:
  ```bash
  key=$(grep -m1 '^GROQ_API_KEY=' .env | sed 's/^GROQ_API_KEY=//' | tr -d '\r\n')
  printf '%s' "$key" | docker compose exec -T vault sh -c \
    'k=$(tr -d "\r\n"); printf "%s" "$k" | VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=dev-root-token vault kv put secret/llm groq_api_key=-'
  ```
  Without it, `/api/v1/chat` returns a clean 503 ("temporarily unavailable").
- **Commits/pushes are the user's call.** `git commit` / `git push` are run by the
  user, not the agent (permission settings) — agent prepares changes and shows
  diffs.
- **Stack bring-up:** `docker compose up -d`. Hard dependencies are
  **Vault, Postgres, Redis** (api waits on them); `vault-init` + `migrate` run
  once and exit. Docker Desktop on this machine has been flaky mid-`--build` —
  if the daemon drops, restart Docker Desktop and re-run.

---

## Where the numbers live (re-pull anytime)

| What | Path |
|---|---|
| Served LR TF-IDF model | `artifacts/classical/best_model.joblib` |
| Per-class metrics + confusion + vectorizer settings | `reports/classical/best_classical_eval.json` |
| Confusion matrix (CSV) | `reports/classical/confusion_matrix.csv` |
| Model comparison | `reports/classical/classical_comparison.{json,csv}` |
| Training text field source | `ml/classical_baseline.py:52` (`model_text`) |
| Normalization that builds `model_text` | `ml/text_preprocessing.py` |
| Serving text assembly (skew) | `model_server/classifier.py:23-28`, `:54-57` |
| Living classifier report | `docs/CLASSIFIER_TRACK_REPORT.md` |
| Project state of record | `PROJECT_STATE.md` |
