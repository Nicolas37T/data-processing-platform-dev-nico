from airflow.models import DagRun
from airflow.utils.session import create_session

with create_session() as session:
    all_runs = session.query(DagRun.dag_id, DagRun.run_id, DagRun.state).order_by(DagRun.id.desc()).limit(10).all()
    print("Latest DagRuns in Airflow:")
    for r in all_runs:
        print(" ", r)
