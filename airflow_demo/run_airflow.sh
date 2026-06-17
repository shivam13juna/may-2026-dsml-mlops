#!/usr/bin/env bash
#
# Launches the full Airflow stack (web UI + scheduler) for this demo.
# Usage:   bash run_airflow.sh      then open http://localhost:8080
#
# `airflow standalone` starts everything you need and prints the admin
# login on first run. Stop it any time with Ctrl-C.

set -euo pipefail

# Keep everything for this demo inside this folder (its own DB, config, logs)
# so it never touches any other Airflow setup on the machine.
export AIRFLOW_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export AIRFLOW__CORE__DAGS_FOLDER="$AIRFLOW_HOME/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=False   # show only OUR dag, not Airflow's samples

# Put the project's "airflow" virtualenv on PATH. This matters: `airflow
# standalone` launches the scheduler/api-server/dag-processor as child processes
# by calling the bare command `airflow`, so that name must resolve on PATH
# (pointing only at the full binary path is not enough for the children).
export PATH="/Users/shivam13juna/Documents/virtual_envs/airflow/bin:$PATH"

echo "AIRFLOW_HOME = $AIRFLOW_HOME"
echo "Open the UI at http://localhost:8080  (user: admin)"
echo "The admin password is printed below on first run, and also saved in:"
echo "  $AIRFLOW_HOME/simple_auth_manager_passwords.json.generated"
echo

exec airflow standalone
