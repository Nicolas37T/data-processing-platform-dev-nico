import sys
import os
import importlib
import requests
import logging
import time
import traceback
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

logger = logging.getLogger("airflow.task")

local_tz = pytz.timezone("America/La_Paz")

_AIRFLOW_API_BASE = os.environ.get("AIRFLOW_API_BASE_URL", "http://airflow-apiserver:8080")


def _trigger_dag_via_api(dag_id: str, conf: dict) -> None:
    username = os.environ.get("_AIRFLOW_WWW_USER_USERNAME", "airflow")
    password = os.environ.get("_AIRFLOW_WWW_USER_PASSWORD", "airflow")
    logger.info(f"Triggering DAG '{dag_id}' via Airflow API: {_AIRFLOW_API_BASE} with conf={conf}")
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
        logger.error(f"Failed to trigger DAG '{dag_id}' via API: status={resp.status_code}, response={resp.text}")
        raise RuntimeError(f"Error al disparar DAG {dag_id}: {resp.status_code} - {resp.text}")
    logger.info(f"Successfully posted dagRun for '{dag_id}' (status {resp.status_code}).")


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
            execution_type = "4"
        elif get_state('notify_success_revision_only'):
            execution_type = "2"
        elif get_state('notify_success_download_revision'):
            execution_type = "3"
        elif get_state('notify_success_download'):
            execution_type = "1"
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

        logger.error("=" * 80)
        logger.error(f"[FAILURE CALLBACK] Task '{task}' FAILED in Direct Download DAG '{file_code}'")
        logger.error(f"  Execution Date : {execution_date}")
        logger.error(f"  File Name      : {file_name}")
        logger.error(f"  Host           : {host}")
        logger.error(f"  Exception Type : {type(exception).__name__ if exception else 'Unknown'}")
        logger.error(f"  Exception Msg  : {exception}")
        logger.error(f"  Log URL        : {log_url}")
        logger.error(f"  Traceback:\n{traceback.format_exc()}")
        logger.error("=" * 80)

        pg_hook = PostgresHook(postgres_conn_id=connection_id)
        insert_sql = """
            INSERT INTO dag_run_exceptions (execute_date, file_code, file_name, spim_code, failed_task, exception, log_path, host)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        try:
            pg_hook.run(insert_sql, parameters=(execution_date, file_code, file_name, spim_code, task, str(exception), log_url, host))
            logger.info("Recorded failure details into 'dag_run_exceptions' table.")
        except Exception as log_err:
            logger.error(f"Failed to record exception in 'dag_run_exceptions': {log_err}")

        try:
            from templates.taiga_notifier import send_taiga_incident
            send_taiga_incident(
                dag_code=dag_run.dag_id,
                error_type="download_exception",
                failed_task=task,
                exception_msg=str(exception),
                file_code=file_code,
                subreport_name=file_name
            )
        except Exception as _e_taiga:
            print(f"[TAIGA_CALLBACK] Warning download failure: {_e_taiga}")

    dag.on_success_callback = log_dag_run_info
    dag.on_failure_callback = dag_failure_callback

    executor = get_executor(id_dag)

    def _read_download_data(ti):
        start_time = time.time()
        logger.info("=" * 80)
        logger.info(f">>> [TASK: read_download_data] Extracting download configuration for DAG: '{id_dag}'")
        logger.info("=" * 80)

        raw_data = ti.xcom_pull(key='return_value', task_ids='get_download_data')
        if not raw_data or not raw_data[0]:
            err_msg = f"No download configuration data returned by 'get_download_data' for DAG: '{id_dag}'"
            logger.error(err_msg)
            raise ValueError(err_msg)

        record = raw_data[0]
        file_path = convert_win_path(record[0])
        file_url = record[1]
        file_id = record[2]
        file_type = record[3]
        file_frequency = record[4]
        file_updated_to = record[5]
        file_name = record[6]
        last_file_path = record[7]
        short_name = record[9]
        key_words = record[9]

        logger.info("Parsed download parameters:")
        logger.info(f"  - file_id        : {file_id}")
        logger.info(f"  - file_name      : {file_name}")
        logger.info(f"  - file_url       : {file_url}")
        logger.info(f"  - file_type      : {file_type}")
        logger.info(f"  - file_frequency : {file_frequency}")
        logger.info(f"  - file_updated_to: {file_updated_to}")
        logger.info(f"  - file_path      : {file_path}")
        logger.info(f"  - last_file_path : {last_file_path}")

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

        elapsed = time.time() - start_time
        logger.info("=" * 80)
        logger.info(f"<<< [TASK: read_download_data] COMPLETED in {elapsed:.2f}s")
        logger.info("=" * 80)

    def _verify_url(ti) -> bool:
        start_time = time.time()
        url = ti.xcom_pull(key='file_url', task_ids='read_download_data')
        logger.info("=" * 80)
        logger.info(f">>> [TASK: verify_url] Verifying accessibility of URL: '{url}'")
        logger.info("=" * 80)

        isReachable = executor.verify_url(url)
        elapsed = time.time() - start_time

        if isReachable:
            logger.info("=" * 80)
            logger.info(f"BRANCH DECISION -> 'verify_download' (URL is reachable in {elapsed:.2f}s)")
            logger.info("=" * 80)
            return 'verify_download'
        else:
            logger.warning("=" * 80)
            logger.warning(f"BRANCH DECISION -> 'notify_url_broken' (URL is NOT reachable: '{url}')")
            logger.warning("=" * 80)
            return 'notify_url_broken'

    def _verify_download(ti):
        start_time = time.time()
        url = ti.xcom_pull(key='file_url', task_ids='read_download_data')
        updatedTo = ti.xcom_pull(key='file_updated_to', task_ids='read_download_data')
        file_path = ti.xcom_pull(key='file_path', task_ids='read_download_data')

        logger.info("=" * 80)
        logger.info(f">>> [TASK: verify_download] Verifying and downloading files from: '{url}' (updatedTo='{updatedTo}')")
        logger.info("=" * 80)

        file_paths = executor.verify_download(url, str(updatedTo), file_path)
        logger.info(f"Downloaded files: {file_paths}")
        ti.xcom_push(key='files_paths', value=file_paths)

        elapsed = time.time() - start_time
        if not file_paths:
            logger.info("=" * 80)
            logger.info(f"BRANCH DECISION -> 'record_revision_only' (No files downloaded in {elapsed:.2f}s)")
            logger.info("=" * 80)
            return 'record_revision_only'
        else:
            logger.info("=" * 80)
            logger.info(f"BRANCH DECISION -> 'compare_files' ({len(file_paths)} file(s) downloaded in {elapsed:.2f}s)")
            logger.info("=" * 80)
            return 'compare_files'

    def _compare_files(ti):
        start_time = time.time()
        file_path_download = ti.xcom_pull(key='files_paths', task_ids='verify_download')
        updated_to = ti.xcom_pull(key='file_updated_to', task_ids='read_download_data')

        logger.info("=" * 80)
        logger.info(f">>> [TASK: compare_files] Comparing downloaded files against cut-off: '{updated_to}'")
        logger.info("=" * 80)

        ti.xcom_push(key='file_path_download', value=file_path_download)
        files_dicts = executor.compare_files(file_path_download, updated_to)
        ti.xcom_push(key='files_dicts', value=files_dicts)

        elapsed = time.time() - start_time
        if not files_dicts:
            logger.info("=" * 80)
            logger.info(f"BRANCH DECISION -> 'record_download_revision' (No newer files detected in {elapsed:.2f}s)")
            logger.info("=" * 80)
            return 'record_download_revision'
        else:
            logger.info(f"New or modified files detected: {len(files_dicts)}")
            logger.info("=" * 80)
            logger.info(f"BRANCH DECISION -> 'store_files' ({len(files_dicts)} file(s) proceed to storage)")
            logger.info("=" * 80)
            return 'store_files'

    def _store_files(ti):
        start_time = time.time()
        file_frequency = ti.xcom_pull(key='file_frequency', task_ids='read_download_data')
        files_dicts = ti.xcom_pull(key='files_dicts', task_ids='compare_files')
        path = ti.xcom_pull(key='file_path', task_ids='read_download_data')
        short_name = ti.xcom_pull(key='short_name', task_ids='read_download_data')

        logger.info("=" * 80)
        logger.info(f">>> [TASK: store_files] Organizing and storing {len(files_dicts) if files_dicts else 0} file(s)")
        logger.info("=" * 80)

        files_dicts = executor.store_files(files_dicts, short_name, file_frequency, path)
        for item in files_dicts:
            item['file_hash'] = Download_Hash(download_path=item['datax_file_path']).get_download_hash()
            item['datax_file_path'] = convert_unix_path(item['datax_file_path'])
            logger.info(f"  Stored: '{item['datax_file_path']}' | Hash: {item.get('file_hash')}")

        max_date_item = max(files_dicts, key=lambda x: datetime.strptime(x['updated_to'], "%Y-%m-%d"))
        logger.info(f"Max update date item: {max_date_item.get('updated_to')}")
        ti.xcom_push(key='file_update', value=max_date_item)
        ti.xcom_push(key='files_dicts', value=files_dicts)

        elapsed = time.time() - start_time
        logger.info("=" * 80)
        logger.info(f"<<< [TASK: store_files] COMPLETED in {elapsed:.2f}s")
        logger.info("=" * 80)

    def _assigner(ti):
        start_time = time.time()
        downloads_records = ti.xcom_pull(task_ids='record_download')

        logger.info("=" * 80)
        logger.info(f">>> [TASK: assigner] Mapping download records to conversion reports for '{id_dag}'")
        logger.info("=" * 80)

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
        logger.info(f"Assigned {len(downloads)} conversion job(s): {[d.get('code') for d in downloads]}")
        ti.xcom_push(key='downloads', value=downloads)

        elapsed = time.time() - start_time
        logger.info("=" * 80)
        logger.info(f"<<< [TASK: assigner] COMPLETED in {elapsed:.2f}s")
        logger.info("=" * 80)

    def _trigger_dags(ti):
        start_time = time.time()
        downloads = ti.xcom_pull(task_ids='assigner', key='downloads') or []

        logger.info("=" * 80)
        logger.info(f">>> [TASK: trigger_dags] Triggering {len(downloads)} conversion DAG(s)")
        logger.info("=" * 80)

        for download in downloads:
            c_dag_id = download["code"]
            logger.info(f"Triggering Conversion DAG: '{c_dag_id}' with conf: file='{download['path']}', code='{download['executor_code']}'")
            try:
                _trigger_dag_via_api(
                    dag_id=c_dag_id,
                    conf={
                        'file': download["path"],
                        'code': download["executor_code"],
                        'id_download': download["id_download"],
                    },
                )
                logger.info(f"Successfully triggered conversion DAG '{c_dag_id}'.")
            except Exception as e:
                logger.error(f"DAG '{c_dag_id}' failed to trigger, continuing: {e}")
                continue

        elapsed = time.time() - start_time
        logger.info("=" * 80)
        logger.info(f"<<< [TASK: trigger_dags] COMPLETED in {elapsed:.2f}s")
        logger.info("=" * 80)

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

        verify_download = BranchPythonOperator(
            task_id='verify_download',
            python_callable=_verify_download,
        )

        compare_files = BranchPythonOperator(
            task_id='compare_files',
            python_callable=_compare_files,
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

        record_download_revision = PostgresOperator(
            task_id="record_download_revision",
            conn_id=connection_id,
            sql="sql/insert_review.sql",
            params={'id_user': "'1'", 'type': "'Download Revision'"},
        )

        notify_success_revision_only = PostgresOperator(
            task_id="notify_success_revision_only",
            conn_id=connection_id,
            sql="sql/insert_custom_dag_run.sql",
            params={'state': "'Successful Revision Only'"}
        )

        notify_success_download_revision = PostgresOperator(
            task_id="notify_success_download_revision",
            conn_id=connection_id,
            sql="sql/insert_custom_dag_run.sql",
            params={'state': "'Successful Download Revision'"}
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

    get_download_data >> read_download_data >> verify_url >> [verify_download, notify_url_broken]
    verify_download >> [record_revision_only, compare_files]
    record_revision_only >> notify_success_revision_only
    compare_files >> [store_files, record_download_revision]
    record_download_revision >> notify_success_download_revision
    store_files >> record_download >> update_file >> notify_success_download >> assigner >> trigger_task