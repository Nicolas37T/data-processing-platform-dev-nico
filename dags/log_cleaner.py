from airflow import DAG
from airflow.models import XCom
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone

def days_ago(n):
    return datetime.now(tz=timezone.utc) - timedelta(days=n)
from airflow.utils.session import provide_session
import os
import time

def cleanup_logs():
    log_path = '/home/datax/platform_project/logs'
    
    now = time.time()
    for root, dirs, files in os.walk(log_path):
        for f in files:
            file_path = os.path.join(root, f)
            if os.stat(file_path).st_mtime < now - 7 * 86400:  # 7 días
                os.remove(file_path)
        for d in dirs:
            dir_path = os.path.join(root, d)
            if not os.listdir(dir_path):  # Borra el directorio si está vacío
                os.rmdir(dir_path)
@provide_session
def delete_old_xcoms(session=None):
    target_date = datetime.now() - timedelta(days=7)
    deleted = session.query(XCom).filter(
        XCom.execution_date <= target_date
    ).delete(synchronize_session=False)
    session.commit()
    print(f"{deleted} XComs deleted.")

default_args = {
    'owner': 'airflow',
    'start_date': days_ago(1),
    'retries': 1,
}

with DAG(
    'cleanup_logs',
    default_args=default_args,
    schedule_interval='0 22 * * 0',
    catchup=False,
    tags=["maintenance"],
) as dag:

    cleanup_logs_task = PythonOperator(
        task_id='cleanup_logs',
        python_callable=cleanup_logs,
    )

    delete_xcoms_task = PythonOperator(
        task_id='delete_xcoms_task',
        python_callable=delete_old_xcoms,
    )

    cleanup_logs_task >> delete_xcoms_task