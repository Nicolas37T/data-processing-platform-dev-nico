# Airflow 3.2.2 Migration Notes

This document records all breaking-change fixes applied when upgrading from **Apache Airflow 2.10.4 → 3.2.2** (Python 3.12 → 3.13).

---

## Infrastructure

### `Dockerfile`
- Base image: `apache/airflow:2.10.4` → `apache/airflow:3.2.2`
- `JAVA_HOME`: hardcoded `java-11-openjdk-amd64` → `default-java` symlink (Debian bookworm ships Java 17 by default; symlink works on both amd64 and arm64)

### `docker-compose.yaml` (full rewrite)
- `airflow-webserver` renamed to `airflow-apiserver` with command `api-server`
- Healthcheck updated to `/api/v2/monitor/health`
- New mandatory service `airflow-dag-processor` (command `dag-processor`) — required in Airflow 3 because the DAG processor was separated from the scheduler
- PostgreSQL upgraded: `postgres:13` → `postgres:16`
- New env vars:
  - `AIRFLOW__CORE__AUTH_MANAGER` — FAB auth manager now requires explicit declaration
  - `AIRFLOW__CORE__EXECUTION_API_SERVER_URL` — worker-to-apiserver communication endpoint
  - `AIRFLOW__API_AUTH__JWT_SECRET` / `AIRFLOW__API_AUTH__JWT_ISSUER` — JWT auth for the API server
- `AIRFLOW__CELERY__RESULT_BACKEND`: added `+psycopg2` driver suffix (required for SQLAlchemy 2.0)
- `airflow-worker` now depends on `airflow-apiserver: condition: service_healthy`
- Removed deprecated `AIRFLOW__API__AUTH_BACKENDS`

### `requirements.txt`
- Added `apache-airflow-providers-standard` — Airflow 3 moved `PythonOperator`, `BranchPythonOperator`, and `TriggerDagRunOperator` here
- Added `apache-airflow-providers-fab` — required for the Airflow 3 web UI (FAB auth manager)
- `pandas>=2.1.2,<2.2` → `pandas>=2.2.0` — 2.1.x has no Python 3.13 wheels

---

## DAG Templates

All five download templates and the two pipeline templates received the same set of changes:

### Import changes (all templates)
| Removed | Replaced with |
|---------|--------------|
| `from airflow.operators.python import PythonOperator, BranchPythonOperator` | `from airflow.providers.standard.operators.python import PythonOperator, BranchPythonOperator` |
| `from airflow.operators.trigger_dagrun import TriggerDagRunOperator` | *(removed — see REST API below)* |
| `from airflow.utils.db import provide_session` | *(removed)* |
| `from airflow.models import XCom` | *(removed)* |
| `from airflow.models import DagBag` | *(removed, conversion template only)* |

- `sys.path.append('/home/datax/platform_project')` → `sys.path.append('/opt/airflow')`

### `delete_xcoms` function removed (all templates)
In Airflow 3, tasks cannot access the metadata DB directly (`@provide_session` decorator was removed). This function used to delete XComs via ORM. It is no longer needed — Airflow 3 manages XCom lifecycle automatically.

### `provide_context=True` removed (all templates)
This parameter was deprecated in Airflow 2.x and removed in 3.x. Context is now always injected into callables by default.

### `schedule_interval` → `schedule` (all DAG definitions)
The `schedule_interval` parameter was removed in Airflow 3. All DAGs now use `schedule=`.

### `TriggerDagRunOperator.execute()` → REST API (all templates)
Calling `.execute()` on an operator programmatically inside a task is blocked in Airflow 3 (the Task Runner no longer supports it). Replaced with HTTP calls to the Airflow REST API v2:

```python
_AIRFLOW_API_BASE = os.environ.get("AIRFLOW_API_BASE_URL", "http://airflow-apiserver:8080")

def _trigger_dag_via_api(dag_id: str, conf: dict) -> None:
    resp = requests.post(
        f"{_AIRFLOW_API_BASE}/api/v2/dags/{dag_id}/dagRuns",
        json={"conf": conf},
        auth=(
            os.environ.get("_AIRFLOW_WWW_USER_USERNAME", "airflow"),
            os.environ.get("_AIRFLOW_WWW_USER_PASSWORD", "airflow"),
        ),
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Error al disparar DAG {dag_id}: {resp.status_code} - {resp.text}")
```

### `DagBag` check removed (`conversion_template.py`)
The old code used `DagBag()` to check whether a migration DAG existed before triggering it. In Airflow 3, workers cannot instantiate `DagBag`. Replaced with a `try/except` around the REST API call — a 404 response means the DAG doesn't exist and is silently skipped.

### `context['dag'].schedule_interval` → `context['dag'].schedule` (all templates)
Used in `log_dag_run_info` callbacks.

---

## Download DAG Files (`dags/download/D_PE_*.py`)

Applied to all 6 files:
- `schedule_interval=` → `schedule=`
- Removed `from airflow.utils.dates import days_ago` (deprecated in 2.x, removed in 3.x)
- Fixed import path: `from dags.templates.data_download_template import create_dag` → `from templates.data_download_template import create_dag` (files 002–006 had an incorrect `dags.` prefix)

---

## `models/migration/Migration_Base.py`

SQLAlchemy 2.0 (required by Airflow 3) removed support for passing raw strings to `connection.execute()`. Fixed two occurrences by wrapping the query string in `text()`:

```python
# Before
result = connection.execute(count_query)

# After
result = connection.execute(text(count_query))
```

Same fix applied to the `sql_query` string in `migration_template.py`'s `_pre_load` function.
