# Apache Airflow — 10‑minute demo

A tiny, self‑contained demo to show learners **what Airflow is and why it exists**.

## What is Airflow?

Airflow is a tool for **orchestrating workflows**. You describe a pipeline as
Python code, and Airflow runs it for you — in the correct order, on a schedule,
with automatic **retries**, **logging**, and a **web UI** to watch and debug it.

The core idea is the **DAG** (Directed Acyclic Graph):

| Term | Meaning |
|------|---------|
| **DAG** | the whole workflow |
| **Task** | one step in it (here, a Python function) |
| **Dependency** | "this step must finish before that one starts" (the arrows) |

## What this demo does

`dags/ml_pipeline.py` defines a miniature ML pipeline that trains two models on
the Iris dataset and keeps the better one:

```
         ┌──> train_logreg ──┐
    extract                   ├──> pick_best ──> report
         └──> train_tree ────┘
```

`train_logreg` and `train_tree` don't depend on each other, so **Airflow runs
them in parallel** — a key reason to use an orchestrator instead of one long script.

## Run it

The `airflow` virtualenv already has everything installed
(`apache-airflow 3.2.2`, `scikit-learn`, `pandas`).

### Option A — see it run in the terminal (fast)

```bash
source /Users/shivam13juna/Documents/virtual_envs/airflow/bin/activate
export AIRFLOW_HOME=$(pwd)            # run from this airflow_demo/ folder
airflow dags test ml_pipeline        # runs the whole pipeline once, prints logs
```

You'll see each task run in order and the final "Best model" report.

### Option B — see it in the Web UI (the real experience)

```bash
bash run_airflow.sh
```

Then:
1. Open **http://localhost:8080** and log in as `admin` (password is printed in
   the terminal, and saved in `simple_auth_manager_passwords.json.generated`).
2. Click the **`ml_pipeline`** DAG, toggle it **on** (unpause), then hit
   **Trigger** (▶).
3. Open the **Graph** view and watch the boxes turn green as tasks run. Click any
   task → **Logs** to see its output.

Stop the server with `Ctrl‑C`.

## Talking points for the class

- **Graph view** — the pipeline *is* the picture; dependencies are explicit.
- **Parallelism** — the two training tasks light up at the same time.
- **Logs per task** — each step's output is captured separately for debugging.
- **Retries / scheduling** — change `schedule=None` to `"@daily"` and Airflow
  would run this every day on its own; add `retries=2` and a flaky task
  auto‑retries. (We keep `schedule=None` so it only runs when triggered.)

## Files

```
airflow_demo/
├── dags/ml_pipeline.py   # the DAG — start here
├── run_airflow.sh        # launches the web UI + scheduler
├── README.md             # this file
└── (airflow.db, logs/, airflow.cfg)   # auto-created; safe to delete to reset
```

> This folder is its own `AIRFLOW_HOME`, so the demo is isolated and you can
> reset it any time by deleting `airflow.db`, `logs/`, and `airflow.cfg`.
