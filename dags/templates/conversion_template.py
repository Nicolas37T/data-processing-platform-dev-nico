import sys
import os
import re
import shutil
import zipfile
import pytz
import uuid
import importlib
import requests
sys.path.append('/opt/airflow')
from sqlalchemy import create_engine, inspect, text
from airflow.providers.standard.operators.python import PythonOperator, BranchPythonOperator
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator as PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.mongo.hooks.mongo import MongoHook
from models.conversion.tools.conversion_tools import organize_and_copy_files_by_status, insert_metadata, convert_win_path, convert_unix_path
from models.conversion.tools.ia_tools import IA_Tools

# Setting the local timezone
local_tz = pytz.timezone('America/La_Paz')

_AIRFLOW_API_BASE = os.environ.get("AIRFLOW_API_BASE_URL", "http://airflow-apiserver:8080")

_DATA_DB_HOST = os.environ.get("DATA_DB_HOST", "postgres")
_DATA_DB_PORT = os.environ.get("DATA_DB_PORT", "5432")
_DATA_DB_USER = os.environ.get("DATA_DB_USER", "postgres")
_DATA_DB_PASSWORD = os.environ.get("DATA_DB_PASSWORD", "datax")


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


def delete_tmp_dirs(context):
    ti = context['task_instance']
    tmp_path = ti.xcom_pull(key='tmp_path', task_ids='get_conversion_data')
    if tmp_path and os.path.exists(tmp_path):
        shutil.rmtree(tmp_path, ignore_errors=True)


# Create an instance of the Executor associated with the DAG
def get_executor(code):
    db_code = '_'.join(code.split('_')[:-1]).replace('D_','C_')
    module = importlib.import_module(f'models.conversion.{db_code}.{code}')
    class_ = getattr(module, code)
    return class_()

def create_dag(dag, connection_id, id_dag=None):

    def dag_failure_callback(context):
        ti = context["ti"]
        dag_run = context['dag_run']
        execution_date = dag_run.start_date.astimezone(local_tz)
        exception = context['exception']
        task = ti.task_id

        id_report = ti.xcom_pull(key='id_report', task_ids='get_conversion_data')
        report_name = ti.xcom_pull(key='name', task_ids='get_conversion_data')
        file_code = ti.xcom_pull(key='file_code', task_ids='get_conversion_data')

        pg_hook = PostgresHook(postgres_conn_id=connection_id)

        insert_sql = """
            INSERT INTO conversion_exceptions (id_report, conversion_date, report_name, file_code, failed_task, exceptions)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        pg_hook.run(insert_sql, parameters=(id_report, execution_date, report_name, file_code, task, str(exception)))

        delete_tmp_dirs(context)


    def _get_conversion_data(**context):
        ti = context["ti"]
        report_code = context['dag_run'].conf.get('code')
        id_download = context['dag_run'].conf.get('id_download')
        compare_dates = context['dag_run'].conf.get('compare_dates')
        pg_hook = PostgresHook(postgres_conn_id=connection_id)
        sql = "SELECT r.path, r.id_report, r.key_words, r.converted_report_path, r.code, r.converted_to, r.name, r.publication_frequency, r.file_extension, r.replacement_table, r.compare_dates, r.page_number, r.decimal_separator, f.code as file_code FROM report AS r INNER JOIN file as f ON r.id_file = f.id_file WHERE r.code = %s"
        connection = pg_hook.get_conn()
        cursor = connection.cursor()
        cursor.execute(sql, (report_code,))
        columns = [col[0] for col in cursor.description]

        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        report = results[0]
        path = convert_win_path(report["path"])
        last_conversion_path = convert_win_path(report["converted_report_path"])

        tmp_path = os.path.join(path, f'tmp_{uuid.uuid4()}')
        os.makedirs(tmp_path)

        file_downloaded = context['dag_run'].conf.get('file')
        file_downloaded = convert_win_path(file_downloaded)

        compare_dates = compare_dates if compare_dates is not None else report["compare_dates"]

        ti.xcom_push(key='path', value=path)
        ti.xcom_push(key='key_words', value=report["key_words"])
        ti.xcom_push(key='last_conversion_path', value=last_conversion_path)
        ti.xcom_push(key='code', value=report["code"])
        converted_to = report["converted_to"]
        ti.xcom_push(key='converted_to', value=converted_to.strftime('%Y-%m-%d') if converted_to else None)
        ti.xcom_push(key='tmp_path', value=tmp_path)
        ti.xcom_push(key='file_code', value=report["file_code"])
        ti.xcom_push(key='id_report', value=report["id_report"])
        ti.xcom_push(key='name', value=report["name"])
        ti.xcom_push(key='publication_frequency', value=report["publication_frequency"])
        ti.xcom_push(key='file_extension', value=report["file_extension"])
        ti.xcom_push(key='replacement_table', value=report["replacement_table"])
        ti.xcom_push(key='compare_dates', value=compare_dates)
        ti.xcom_push(key='page_number', value=report["page_number"])
        ti.xcom_push(key='decimal_separator', value=report["decimal_separator"])
        ti.xcom_push(key='id_download', value=id_download)

        splited_file_downloaded = file_downloaded.split(';')
        dirs = [f for f in splited_file_downloaded if os.path.isdir(f)]
        zips = [f for f in splited_file_downloaded if re.search(r'\.zip', f, re.IGNORECASE)]
        downloaded_files = []
        if dirs:
            dir_path = dirs[0]
            ti.xcom_push(key='type', value='Multiple')
            downloaded_files = [os.path.join(dir_path, f) for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]
        elif zips:
            dir_path = zips[0]
            ti.xcom_push(key='type', value='Multiple')
            with zipfile.ZipFile(dir_path[0], 'r') as zip_ref:
                for f in zip_ref.infolist():
                    if not f.is_dir():
                        downloaded_files.append(zip_ref.extract(f, tmp_path))
        else:
            ti.xcom_push(key='type', value='One')
            if len(splited_file_downloaded) > 1:
                downloaded_files = [f for f in splited_file_downloaded if re.search(r'\.(xls)', f, re.IGNORECASE)]
            else:
                downloaded_files = splited_file_downloaded
            if not downloaded_files:
                downloaded_files = [splited_file_downloaded[0]]
        downloaded_files = [{"file_path": f, "status": None} for f in downloaded_files]
        ti.xcom_push(key='downloaded_files', value=downloaded_files)

    def _read_file(**context):
        ti = context['ti']
        dag_run = context['dag_run']
        code = ti.xcom_pull(key='code', task_ids='get_conversion_data')
        executor = get_executor(code)
        path = ti.xcom_pull(key='path', task_ids='get_conversion_data')
        publication_frequency = ti.xcom_pull(key='publication_frequency', task_ids='get_conversion_data')
        tmp_path = ti.xcom_pull(key='tmp_path', task_ids='get_conversion_data')
        downloaded_files = ti.xcom_pull(key='downloaded_files', task_ids='get_conversion_data')

        for item in downloaded_files:
            file_path = executor.read_file(file_path=item["file_path"], path=tmp_path)
            if not file_path:
                item["status"] = "corrupted_file"
            else:
                item['file_path'] = file_path

        if all(item.get('status') is not None for item in downloaded_files):
            corrupted_files_path = organize_and_copy_files_by_status(files=downloaded_files, date=dag_run.start_date.astimezone(local_tz), base_path=path, publication_frequency=publication_frequency)
            ti.xcom_push(key='corrupted_files_path', value=corrupted_files_path)
            return 'notify_corrupt_file'
        else:
            ti.xcom_push(key='read_files', value=downloaded_files)
            return 'extraction'

    def _extraction(**context):
        ti = context['ti']
        dag_run = context['dag_run']
        code = ti.xcom_pull(key='code', task_ids='get_conversion_data')
        executor = get_executor(code)
        path = ti.xcom_pull(key='path', task_ids='get_conversion_data')
        publication_frequency = ti.xcom_pull(key='publication_frequency', task_ids='get_conversion_data')
        read_files = ti.xcom_pull(key='read_files', task_ids='read_file')
        converted_to = ti.xcom_pull(key='converted_to', task_ids='get_conversion_data')
        key_words = ti.xcom_pull(key='key_words', task_ids='get_conversion_data')
        last_conversion_path = ti.xcom_pull(key='last_conversion_path', task_ids='get_conversion_data')
        replacement_table = ti.xcom_pull(key='replacement_table', task_ids='get_conversion_data')
        compare_dates = ti.xcom_pull(key='compare_dates', task_ids='get_conversion_data')
        page_number = ti.xcom_pull(key='page_number', task_ids='get_conversion_data')

        country_code = code.split('_')[1]
        replacement_table = replacement_table.split(';')

        db_conn = create_engine(f"postgresql+psycopg2://{_DATA_DB_USER}:{_DATA_DB_PASSWORD}@{_DATA_DB_HOST}:{_DATA_DB_PORT}/DATA_DB_{country_code}_AUX")

        with db_conn.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {replacement_table[0]}"))
            conn.commit()
        inspector = inspect(db_conn)
        table_exists = inspector.has_table(replacement_table[1], schema=replacement_table[0])

        for item in read_files:
            if item["status"] is not None:
                continue
            extracted_result = executor.extraction(file_path=item["file_path"], key_words=key_words, template_path=last_conversion_path, page_number=page_number)
            if not extracted_result:
                item["status"] = "unextractable_report"
                continue

            report_dict, repor_df = extracted_result
            if repor_df.empty:
                extracted_file_path = executor.store_excel_file(df=repor_df, file_path=item["file_path"], sufix='extracted')
                item['file_path'] = extracted_file_path
                item['replaces_dict'] = {}
                continue
            replaces_dict, report_df = executor.text_match(df=repor_df, db_aux_conn=db_conn, replacement_table_name=replacement_table[1], replacement_table_schema=replacement_table[0], table_exists=table_exists, dag_run_date=dag_run.start_date.astimezone(local_tz))

            if compare_dates:
                date_comparison = executor.compare_dates(df=report_df, converted_to=converted_to)
                if date_comparison == 'no_updates':
                    item["status"] = "no_updates"
                    continue

            report_dict['titles'] = [IA_Tools.standardize_text(text=title) for title in report_dict['titles']]
            final_df = insert_metadata(dataframe=report_df, titles=report_dict['titles'], file_name=report_dict['file_name'])
            extracted_file_path = executor.store_excel_file(df=final_df, file_path=item["file_path"], sufix='extracted')

            item['page_number'] = report_dict['page_number']
            item['file_path'] = extracted_file_path
            item['replaces_dict'] = replaces_dict

        if all(item.get('status') is not None for item in read_files):
            corrupted_files_path = organize_and_copy_files_by_status(files=read_files, date=dag_run.start_date.astimezone(local_tz), base_path=path, publication_frequency=publication_frequency)
            ti.xcom_push(key='corrupted_files_path', value=corrupted_files_path)
            return 'notify_extraction_error'
        else:
            ti.xcom_push(key='extracted_files', value=read_files)
            return 'structure_review'

    def _structure_review(**context):
        ti = context['ti']
        dag_run = context['dag_run']
        code = ti.xcom_pull(key='code', task_ids='get_conversion_data')
        executor = get_executor(code)
        path = ti.xcom_pull(key='path', task_ids='get_conversion_data')
        publication_frequency = ti.xcom_pull(key='publication_frequency', task_ids='get_conversion_data')
        extracted_files = ti.xcom_pull(key='extracted_files', task_ids='extraction')
        last_conversion_path = ti.xcom_pull(key='last_conversion_path', task_ids='get_conversion_data')

        for item in extracted_files:
            if item["status"] is not None:
                continue
            review_result = executor.structure_review(data_file=item["file_path"], last_conversion_path=last_conversion_path)
            if not review_result:
                item["status"] = "report_structure_change"
                continue
            item["status"] = "successful_conversion"

        corrupted_files_path = organize_and_copy_files_by_status(files=extracted_files, date=dag_run.start_date.astimezone(local_tz), base_path=path, publication_frequency=publication_frequency)
        ti.xcom_push(key='corrupted_files_path', value=corrupted_files_path)
        if not any(item.get('status') == "successful_conversion" for item in extracted_files):
            return 'notify_structure_change'
        else:
            ti.xcom_push(key='reviewed_files', value=extracted_files)
            return 'report_data_validation'

    def _report_data_validation(ti):
        mongo_hook = MongoHook(mongo_conn_id="mongo_db")
        client = mongo_hook.get_conn()
        reviewed_files = ti.xcom_pull(key='reviewed_files', task_ids='structure_review')
        reviewed_files = [f for f in reviewed_files if f["status"] == 'successful_conversion']

        code = ti.xcom_pull(key='code', task_ids='get_conversion_data')
        file_extension = ti.xcom_pull(key='file_extension', task_ids='get_conversion_data')
        executor = get_executor(code)
        path = ti.xcom_pull(key='path', task_ids='get_conversion_data')
        publication_frequency = ti.xcom_pull(key='publication_frequency', task_ids='get_conversion_data')
        last_conversion_path = ti.xcom_pull(key='last_conversion_path', task_ids='get_conversion_data')
        decimal_separator = ti.xcom_pull(key='decimal_separator', task_ids='get_conversion_data')

        converted_file = executor.report_data_validation(code=code, reviewed_files=reviewed_files, path=path, publication_frequency=publication_frequency, last_conversion_path=last_conversion_path, file_extension=file_extension, mongo_client=client, decimal_separator=decimal_separator)

        client.close()
        converted_file["conversion_path"] = convert_unix_path(converted_file["conversion_path"])

        if converted_file:
            ti.xcom_push(key='converted_file', value=converted_file)
            return 'record_conversion'

    def _trigger_dag(ti):
        conversion = ti.xcom_pull(task_ids='record_conversion')[0]
        code = ti.xcom_pull(key='code', task_ids='get_conversion_data')
        migration_dag = '_'.join(re.sub('D_', 'M_', code).split('_')[:-1])
        print("MIGRATION", migration_dag)
        try:
            _trigger_dag_via_api(
                dag_id=migration_dag,
                conf={'code': code, 'conversion_path': conversion[1], 'id_conversion': conversion[0]},
            )
        except RuntimeError as e:
            if '404' in str(e):
                print(f"DAG {migration_dag} no existe, se omite.")
            else:
                raise

    with dag:

        get_conversion_data = PythonOperator(
            task_id='get_conversion_data',
            python_callable=_get_conversion_data,
            dag=dag,
            on_failure_callback=dag_failure_callback)

        read_file = BranchPythonOperator(
            task_id='read_file',
            python_callable=_read_file,
            on_failure_callback=dag_failure_callback
        )

        extraction = BranchPythonOperator(
            task_id='extraction',
            python_callable=_extraction,
            on_failure_callback=dag_failure_callback
        )

        structure_review = BranchPythonOperator(
            task_id='structure_review',
            python_callable=_structure_review,
            on_failure_callback=dag_failure_callback
        )

        report_data_validation = PythonOperator(
            task_id='report_data_validation',
            python_callable=_report_data_validation,
            on_failure_callback=dag_failure_callback
        )

        notify_corrupt_file = PostgresOperator(
            task_id="notify_corrupt_file",
            conn_id=connection_id,
            sql="sql/insert_conversion_status.sql",
            params={'task': "read_file", 'key': "corrupted_files_path"},
            on_failure_callback=dag_failure_callback,
            on_success_callback=delete_tmp_dirs
        )

        notify_extraction_error = PostgresOperator(
            task_id="notify_extraction_error",
            conn_id=connection_id,
            sql="sql/insert_conversion_status.sql",
            params={'task': "extraction", 'key': "corrupted_files_path"},
            on_failure_callback=dag_failure_callback,
            on_success_callback=delete_tmp_dirs
        )

        notify_structure_change = PostgresOperator(
            task_id="notify_structure_change",
            conn_id=connection_id,
            sql="sql/insert_conversion_status.sql",
            params={'task': "structure_review", 'key': "corrupted_files_path"},
            on_failure_callback=dag_failure_callback,
            on_success_callback=delete_tmp_dirs
        )

        record_conversion = PostgresOperator(
            task_id="record_conversion",
            conn_id=connection_id,
            sql="sql/insert_conversion.sql",
            on_failure_callback=dag_failure_callback
        )

        update_report = PostgresOperator(
            task_id="update_report",
            conn_id=connection_id,
            sql="sql/update_report.sql",
            on_failure_callback=dag_failure_callback
        )

        trigger_task = PythonOperator(
            task_id='trigger_dags',
            python_callable=_trigger_dag,
            on_failure_callback=dag_failure_callback,
            on_success_callback=delete_tmp_dirs
        )

    get_conversion_data >> read_file >> [notify_corrupt_file, extraction]
    notify_corrupt_file
    extraction >> [notify_extraction_error, structure_review]
    notify_extraction_error
    structure_review >> [notify_structure_change, report_data_validation]
    notify_structure_change
    report_data_validation >> record_conversion >> update_report >> trigger_task
