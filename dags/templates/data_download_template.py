import sys
import os
import importlib
import requests
from airflow.providers.standard.operators.python import PythonOperator, BranchPythonOperator
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator as PostgresOperator
from operators.select_postgres_operator import SelectPostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
import socket
import pytz
sys.path.append('/opt/airflow')
from models.download.tools.download_tools import convert_win_path, convert_unix_path, execution_log
from models.download.tools.download_hash import Download_Hash
from datetime import datetime
import pandas as pd

local_tz = pytz.timezone("America/La_Paz")

_AIRFLOW_API_BASE = os.environ.get("AIRFLOW_API_BASE_URL", "http://airflow-apiserver:8080")


def _trigger_dag_via_api(dag_id: str, conf: dict) -> None:
    username = os.environ.get("_AIRFLOW_WWW_USER_USERNAME", "airflow")
    password = os.environ.get("_AIRFLOW_WWW_USER_PASSWORD", "airflow")
    token_resp = requests.post(
        f"{_AIRFLOW_API_BASE}/auth/token",
        json={"username": username, "password": password},
        timeout=30,
    )
    token_resp.raise_for_status()
    token = token_resp.json()["access_token"]
    resp = requests.post(
        f"{_AIRFLOW_API_BASE}/api/v2/dags/{dag_id}/dagRuns",
        json={"conf": conf, "logical_date": None},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Error al disparar DAG {dag_id}: {resp.status_code} - {resp.text}")


def get_executor(code):
    module = importlib.import_module(f'models.download.{code}.{code}')
    class_ = getattr(module, code)
    return class_()


def create_dag(dag, connection_id, id_dag=None):

    def log_dag_run_info(context):
        dag_run = context.get('dag_run')
        ti = context['task_instance']
        execution_date = dag_run.start_date.astimezone(local_tz).strftime('%Y-%m-%d %H:%M:%S')
        end_time = datetime.now(local_tz)
        duration = end_time - dag_run.start_date

        xcom_pull = lambda key: ti.xcom_pull(task_ids='read_download_data', key=key)
        path = xcom_pull('file_path')
        key_words = xcom_pull('key_words')
        file_name = xcom_pull('file_name')
        publication_frequency = xcom_pull('file_frequency')
        main_url = xcom_pull('file_url')

        get_state = lambda task_id: dag_run.get_task_instance(task_id).state == 'success'
        execution_type = None
        files = []
        num = 0

        if get_state('notify_url_broken'):
            execution_type = "4"  # "Url Broken"
        elif get_state('notify_success_revision_only'):
            execution_type = "2"  # "Revision Only"
        elif get_state('notify_success_download'):
            execution_type = "1"  # "Download"
            files = ti.xcom_pull(task_ids='store_files', key='files_dicts')

        execution_log(
            path, execution_date, key_words, id_dag, file_name,
            publication_frequency, context['dag'].schedule,
            ";".join(context['dag'].tags), execution_type, duration,
            num, files, main_url
        )

    def dag_failure_callback(context):
        task_instance = context.get('task_instance')
        log_url = task_instance.log_url
        dag_run = context.get('dag_run')
        execution_date = dag_run.start_date.astimezone(local_tz)
        exception = context.get('exception')
        host = socket.gethostname()

        file_name = task_instance.xcom_pull(task_ids='read_download_data', key='file_name')
        file_code = dag_run.dag_id
        spim_code = ";".join(context['dag'].tags)
        task = task_instance.task_id

        pg_hook = PostgresHook(postgres_conn_id=connection_id)
        insert_sql = """
            INSERT INTO dag_run_exceptions (execute_date, file_code, file_name, spim_code, failed_task, exception, log_path, host)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        pg_hook.run(insert_sql, parameters=(execution_date, file_code, file_name, spim_code, task, str(exception), log_url, host))

    dag.on_success_callback = log_dag_run_info
    dag.on_failure_callback = dag_failure_callback

    executor = get_executor(id_dag)

    def _read_download_data(ti):
        file_path = convert_win_path((ti.xcom_pull(key='return_value', task_ids='get_download_data'))[0][0])
        file_url = (ti.xcom_pull(key='return_value', task_ids='get_download_data'))[0][1]
        file_id = (ti.xcom_pull(key='return_value', task_ids='get_download_data'))[0][2]
        file_type = (ti.xcom_pull(key='return_value', task_ids='get_download_data'))[0][3]
        file_frequency = (ti.xcom_pull(key='return_value', task_ids='get_download_data'))[0][4]
        file_updated_to = (ti.xcom_pull(key='return_value', task_ids='get_download_data'))[0][5]
        file_name = (ti.xcom_pull(key='return_value', task_ids='get_download_data'))[0][6]
        last_file_path = (ti.xcom_pull(key='return_value', task_ids='get_download_data'))[0][7]
        short_name = (ti.xcom_pull(key='return_value', task_ids='get_download_data'))[0][9]
        key_words = (ti.xcom_pull(key='return_value', task_ids='get_download_data'))[0][9]

        ti.xcom_push(key='file_path', value=file_path)
        ti.xcom_push(key='file_url', value=file_url)
        ti.xcom_push(key='file_id', value=file_id)
        ti.xcom_push(key='file_type', value=file_type)
        ti.xcom_push(key='file_frequency', value=file_frequency)
        ti.xcom_push(key='file_updated_to', value=file_updated_to)
        ti.xcom_push(key='file_name', value=file_name)
        ti.xcom_push(key='last_file_path', value=last_file_path)
        ti.xcom_push(key='key_words', value=key_words)
        ti.xcom_push(key='short_name', value=short_name)

    def _verify_url(ti) -> bool:
        url = (ti.xcom_pull(key='file_url', task_ids='read_download_data'))
        isReachable = executor.verify_url(url)
        if isReachable:
            return 'check_new_data'
        else:
            return 'notify_url_broken'

    def _check_new_data(ti):
        url = (ti.xcom_pull(key='file_url', task_ids='read_download_data'))
        updatedTo = (ti.xcom_pull(key='file_updated_to', task_ids='read_download_data'))
        file_path = (ti.xcom_pull(key='file_path', task_ids='read_download_data'))
        key_words = (ti.xcom_pull(key='key_words', task_ids='read_download_data'))
        files_dicts = executor.check_new_data(url, str(updatedTo), file_path, key_words, format='%Y-%m-%d')
        ti.xcom_push(key='files_dicts', value=files_dicts)
        if not files_dicts:
            return 'record_revision_only'
        else:
            return 'store_files'

    def _store_files(ti):
        file_frequency = (ti.xcom_pull(key='file_frequency', task_ids='read_download_data'))
        files_dicts = (ti.xcom_pull(key='files_dicts', task_ids='check_new_data'))
        path = (ti.xcom_pull(key='file_path', task_ids='read_download_data'))
        short_name = (ti.xcom_pull(key='short_name', task_ids='read_download_data'))

        files_dicts = executor.store_files(files_dicts, short_name, file_frequency, path)
        for item in files_dicts:
            item['file_hash'] = Download_Hash(download_path=item['datax_file_path']).get_download_hash()
            item['datax_file_path'] = convert_unix_path(item['datax_file_path'])
        max_date_item = max(files_dicts, key=lambda x: datetime.strptime(x['updated_to'], "%Y-%m-%d"))
        ti.xcom_push(key='file_update', value=max_date_item)
        ti.xcom_push(key='files_dicts', value=files_dicts)
        try:
            from templates.dag_metadata_updater import update_dag_tag_and_doc
            update_dag_tag_and_doc(id_dag, 'download', max_date_item.get('updated_to'))
        except Exception as e:
            print(f"Warning: Could not update DAG metadata tag: {e}")

    def _assigner(ti):
        downloads_records = ti.xcom_pull(task_ids='record_download')

        conversion_pg_hook = PostgresHook(postgres_conn_id='platform_db')
        conversion_connection = conversion_pg_hook.get_conn()

        conversion_sql = f"SELECT r.code as executor_code, r.converted_to, f.code FROM report as r LEFT JOIN file as f ON r.id_file = f.id_file WHERE f.code ='{id_dag}' AND r.\"isActive\" = TRUE"
        download_df = pd.DataFrame(data=downloads_records, columns=['id_download', 'path', 'downloaded_to'])
        conversion_df = pd.read_sql(sql=conversion_sql, con=conversion_connection)

        download_df['code'] = id_dag
        merged_df = pd.merge(left=download_df, right=conversion_df, how='inner', on='code')

        merged_df['code'] = merged_df['code'].replace('D_', 'C_', regex=True)
        merged_df = merged_df.sort_values(by=['downloaded_to', 'executor_code'], ascending=[True, True])

        downloads = merged_df.to_dict(orient='records')
        ti.xcom_push(key='downloads', value=downloads)

    def _trigger_dags(ti):
        downloads = ti.xcom_pull(task_ids='assigner', key='downloads')
        for download in downloads:
            try:
                _trigger_dag_via_api(
                    dag_id=download["code"],
                    conf={
                        'file': download["path"],
                        'code': download["executor_code"],
                        'id_download': download["id_download"],
                    },
                )
            except Exception as e:
                print(f"DAG {download['code']} falló pero se continuará: {str(e)}")
                continue

    with dag:

        get_download_data = SelectPostgresOperator(
            task_id='get_download_data',
            conn_id=connection_id,
            sql="sql/get_download_data.sql",
            params={'file_code': "'" + id_dag + "'"},
            dag=dag)

        read_download_data = PythonOperator(
            task_id='read_download_data',
            python_callable=_read_download_data,
        )

        verify_url = BranchPythonOperator(
            task_id='verify_url',
            python_callable=_verify_url,
        )

        notify_url_broken = PostgresOperator(
            task_id="notify_url_broken",
            conn_id=connection_id,
            sql="sql/insert_broken_url.sql",
            params={'file_code': "'" + id_dag + "'"},
        )

        check_new_data = BranchPythonOperator(
            task_id='check_new_data',
            python_callable=_check_new_data,
        )

        store_files = PythonOperator(
            task_id='store_files',
            python_callable=_store_files,
        )

        record_revision_only = PostgresOperator(
            task_id="record_revision_only",
            conn_id=connection_id,
            sql="sql/insert_review.sql",
            params={'id_user': "'1'", 'type': "'Revision Only'"},
        )

        notify_success_revision_only = PostgresOperator(
            task_id="notify_success_revision_only",
            conn_id=connection_id,
            sql="sql/insert_custom_dag_run.sql",
            params={'state': "'Successful Revision Only'"}
        )

        record_download = PostgresOperator(
            task_id="record_download",
            conn_id=connection_id,
            sql="sql/insert_download.sql",
            params={'id_user': "'1'", 'state': "'Downloaded'", 'type_file': "'last file'"},
            do_xcom_push=True
        )

        update_file = PostgresOperator(
            task_id="update_file",
            conn_id=connection_id,
            sql="sql/update_file.sql",
        )

        notify_success_download = PostgresOperator(
            task_id="notify_success_download",
            conn_id=connection_id,
            sql="sql/insert_custom_dag_run.sql",
            params={'state': "'Successful Donwload'"}
        )

        assigner = PythonOperator(
            task_id='assigner',
            python_callable=_assigner,
        )

        trigger_task = PythonOperator(
            task_id='trigger_dags',
            python_callable=_trigger_dags,
        )

    get_download_data >> read_download_data >> verify_url >> [check_new_data, notify_url_broken]
    notify_url_broken
    check_new_data >> [record_revision_only, store_files]
    record_revision_only >> notify_success_revision_only
    store_files >> record_download >> update_file >> notify_success_download >> assigner >> trigger_task
