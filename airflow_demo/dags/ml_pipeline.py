from __future__ import annotations

from datetime import datetime, timedelta

# Airflow 3.x exposes the TaskFlow API (the @dag / @task decorators) here.
# Param        -> declares a runtime input + a "Trigger with config" UI form.
# get_current_context -> lets a task read those params (and other run info).
from airflow.sdk import Param, dag, get_current_context, task

# Where the extract step drops the dataset so the training steps can read it.
# Tasks may run in separate processes, so they pass a *file path*, not the data
# itself. (Small values like numbers/strings can be returned directly — Airflow
# moves them between tasks through a mechanism called XCom.)
DATA_PATH = "/tmp/airflow_ml_demo/iris.csv"


@dag(
    dag_id="ml_pipeline",
    description="Minimal ML pipeline: extract -> train 2 models -> pick best -> report",

    # --- Scheduling -----------------------------------------------------------
    schedule=None,                 # None = manual only. Could be "@daily", a cron
                                   # string like "0 6 * * *", or a timedelta.
    start_date=datetime(2024, 1, 1),
    catchup=False,                 # don't backfill the gap between start_date & now
    max_active_runs=1,             # never run two copies of this DAG at once
    dagrun_timeout=timedelta(minutes=30),   # kill a run that hangs past 30 min

    # --- Failure behaviour ----------------------------------------------------
    max_consecutive_failed_dag_runs=3,      # auto-pause after 3 straight failures

    # --- UI niceties ----------------------------------------------------------
    tags=["demo", "ml"],
    doc_md=__doc__,                # render this file's docstring on the DAG page

    # --- Defaults applied to EVERY task in the DAG ---------------------------
    default_args={
        "owner": "shivam",
        "retries": 2,                          # retry a failed task twice...
        "retry_delay": timedelta(seconds=30),  # ...waiting 30s between tries
        "execution_timeout": timedelta(minutes=10),
    },

    # --- Runtime inputs: these create a form under "Trigger ▸ with config" ---
    params={
        "test_size": Param(
            0.3, type="number", minimum=0.1, maximum=0.5,
            title="Test split fraction",
            description="Portion of the data held out for evaluation.",
        ),
        "random_state": Param(42, type="integer", title="Random seed"),
    },


)


def ml_pipeline():

    @task
    def extract_data() -> str:
        """Step 1 — load the Iris dataset and save it to disk."""
        # Heavy libraries are imported *inside* the task, not at the top of the
        # file: Airflow re-parses every DAG file frequently, and you don't want
        # to pay the import cost on every parse.
        import os
        import pandas as pd
        from sklearn.datasets import load_iris

        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        df = load_iris(as_frame=True).frame
        df.to_csv(DATA_PATH, index=False)
        print(f"Saved {len(df)} rows to {DATA_PATH}")
        return DATA_PATH               # returned value flows to the next tasks

    @task
    def train_logreg(data_path: str) -> dict:
        """Step 2a — train a Logistic Regression model."""
        import pandas as pd
        from sklearn.model_selection import train_test_split
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score

        # Read the values entered in the "Trigger with config" form (or the
        # defaults declared in the @dag params= above).
        params = get_current_context()["params"]

        df = pd.read_csv(data_path)
        X, y = df.drop(columns="target"), df["target"]
        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=params["test_size"], random_state=params["random_state"])

        model = LogisticRegression(max_iter=200).fit(X_tr, y_tr)
        acc = accuracy_score(y_te, model.predict(X_te))
        print(f"LogisticRegression accuracy = {acc:.3f}")
        return {"model": "LogisticRegression", "accuracy": float(acc)}

    @task
    def train_tree(data_path: str) -> dict:
        """Step 2b — train a Decision Tree (runs in parallel with 2a)."""
        import pandas as pd
        from sklearn.model_selection import train_test_split
        from sklearn.tree import DecisionTreeClassifier
        from sklearn.metrics import accuracy_score

        params = get_current_context()["params"]

        df = pd.read_csv(data_path)
        X, y = df.drop(columns="target"), df["target"]
        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=params["test_size"], random_state=params["random_state"])

        model = DecisionTreeClassifier(random_state=params["random_state"]).fit(X_tr, y_tr)
        acc = accuracy_score(y_te, model.predict(X_te))
        print(f"DecisionTree accuracy = {acc:.3f}")
        return {"model": "DecisionTree", "accuracy": float(acc)}

    @task
    def pick_best(results: list[dict]) -> dict:
        """Step 3 — compare the models and keep the most accurate one."""
        best = max(results, key=lambda r: r["accuracy"])
        print(f"All scores : {results}")
        print(f"Winner     : {best['model']} ({best['accuracy']:.3f})")
        return best

    @task
    def report(best: dict) -> dict:
        """Step 4 — 'deploy'. Here we simply announce the chosen model."""
        print("=" * 44)
        print(f"  Best model : {best['model']}")
        print(f"  Accuracy   : {best['accuracy']:.3f}")
        print("  (in production you'd register / deploy it here)")
        print("=" * 44)
        # Returning the result stores it in XCom, so you can always inspect the
        # outcome from the UI's XCom tab even if the task logs aren't available.
        return best

    # ---- Wiring the tasks together is what defines the graph ----
    # Calling a @task returns a handle to its output. Passing that handle into
    # the next task creates the dependency (the arrow in the UI).
    data = extract_data()
    scores = [train_logreg(data), train_tree(data)]   # both depend on extract
    best = pick_best(scores)                           # depends on both trainings
    report(best)                                       # depends on pick_best


# Airflow discovers DAGs by importing this file and looking for DAG objects,
# so we must actually *call* the decorated function to create one.
ml_pipeline()
