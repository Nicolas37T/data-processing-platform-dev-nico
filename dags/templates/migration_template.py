import os
import importlib
import pytz
import traceback
import sys
import requests
sys.path.append('/opt/airflow')
from sqlalchemy import create_engine, inspect, text
from airflow.providers.standard.operators.python import PythonOperator, BranchPythonOperator
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator as PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from models.conversion.tools.conversion_tools import convert_win_path
from models.conversion.tools.text_normalization import Text_Normalization

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


def get_executor(code):
    db_code = '_'.join(code.split('_')[:-1]).replace('D_', 'M_')
    module = importlib.import_module(f'models.migration.{db_code}.{code}')
    class_ = getattr(module, code)
    return class_()

def create_dag(dag, connection_id, id_dag=None):

    def dag_failure_callback(context):
        ti = context["ti"]
        dag_run = context['dag_run']
        execution_date = dag_run.start_date.astimezone(local_tz)
        exception = context['exception']
        task = ti.task_id

        id_report = ti.xcom_pull(key='id_report', task_ids='get_migration_data')
        code = ti.xcom_pull(key='code', task_ids='get_migration_data')

        pg_hook = PostgresHook(postgres_conn_id=connection_id)

        insert_sql = """
            INSERT INTO migration_exceptions (id_report, migration_date, migration_code, failed_task, exceptions)
            VALUES (%s, %s, %s, %s, %s)
        """
        pg_hook.run(insert_sql, parameters=(id_report, execution_date, code, task, str(exception)))

    def _get_migration_data(**context):
        ti = context["ti"]
        report_code = context['dag_run'].conf.get('code')
        id_conversion = context['dag_run'].conf.get('id_conversion')
        conversion_path = context['dag_run'].conf.get('conversion_path')
        conversion_path = convert_win_path(conversion_path)

        pg_hook = PostgresHook(postgres_conn_id=connection_id)
        select_columns = ['id_report', 'path', 'code', 'name', 'storage_table', 'decimal_separator', 'load_scope', 'conversion_factor', 'migrated_to']
        sql = f"SELECT {', '.join(['r.' + col for col in select_columns])}, f.code as file_code FROM report AS r INNER JOIN file as f ON r.id_file = f.id_file WHERE r.code = %s"

        query_result = pg_hook.get_first(sql, parameters=(report_code,))
        query_result = dict(zip(select_columns + ['file_code'], query_result))

        ti.xcom_push(key='id_conversion', value=id_conversion)
        ti.xcom_push(key='conversion_path', value=conversion_path)

        path = convert_win_path(query_result['path'])
        ti.xcom_push(key='id_report', value=query_result['id_report'])
        ti.xcom_push(key='path', value=path)
        ti.xcom_push(key='code', value=query_result['code'])
        ti.xcom_push(key='name', value=query_result['name'])
        ti.xcom_push(key='storage_table', value=query_result['storage_table'])
        ti.xcom_push(key='decimal_separator', value=query_result['decimal_separator'])
        ti.xcom_push(key='load_scope', value=query_result['load_scope'])
        ti.xcom_push(key='conversion_factor', value=query_result['conversion_factor'])
        ti.xcom_push(key='migrated_to', value=query_result['migrated_to'])

    def _pre_load(ti):
        conversion_path = ti.xcom_pull(key='conversion_path', task_ids='get_migration_data')
        code = ti.xcom_pull(key='code', task_ids='get_migration_data')
        load_scope = ti.xcom_pull(key='load_scope', task_ids='get_migration_data')
        storage_table = ti.xcom_pull(key='storage_table', task_ids='get_migration_data')

        country_code = code.split('_')[1]
        storage_table = storage_table.split(';')

        executor = get_executor(code=code)
        db_conn = create_engine(f"postgresql+psycopg2://{_DATA_DB_USER}:{_DATA_DB_PASSWORD}@{_DATA_DB_HOST}:{_DATA_DB_PORT}/DATA_DB_{country_code}")
        with db_conn.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {storage_table[0]}"))
            conn.commit()
        inspector = inspect(db_conn)
        table_exists = inspector.has_table(storage_table[1], schema=storage_table[0])
        print("TABLE_EXISTS", table_exists)
        if not table_exists:
            sql_file_path = os.path.join(executor.path, f'{code}.sql')
            print('SQL_PATH', sql_file_path)
            if not os.path.exists(sql_file_path):
                raise FileNotFoundError(f"SQL file doesn't exists")

            with open(sql_file_path, 'r') as file:
                sql_query = file.read()
            sql_query = sql_query % (storage_table[0], storage_table[1], storage_table[0], storage_table[1])
            with db_conn.connect() as connection:
                connection.execute(text(sql_query))
                connection.commit()

        table_dates = executor.get_table_dates(table_path=conversion_path)
        backup_db, num_records_before = executor.pre_load(db_conn=db_conn, storage_table_name=storage_table[1], storage_table_schema=storage_table[0], load_scope=load_scope, load_dates=table_dates)

        ti.xcom_push(key='backup_db', value=backup_db)
        ti.xcom_push(key='num_records_before', value=num_records_before)
        ti.xcom_push(key='converted_to', value=table_dates["max"])

    def _load(ti):
        conversion_path = ti.xcom_pull(key='conversion_path', task_ids='get_migration_data')
        code = ti.xcom_pull(key='code', task_ids='get_migration_data')
        decimal_separator = ti.xcom_pull(key='decimal_separator', task_ids='get_migration_data')
        conversion_factor = ti.xcom_pull(key='conversion_factor', task_ids='get_migration_data')
        storage_table = ti.xcom_pull(key='storage_table', task_ids='get_migration_data')

        country_code = code.split('_')[1]
        storage_table = storage_table.split(';')

        try:
            executor = get_executor(code=code)
            dataframe = executor.read_table(table_path=conversion_path)
            dataframe = Text_Normalization.standarize_dataframe_cols(dataframe=dataframe)
            df_dict, dataframe = executor.standard_report(dataframe=dataframe, conversion_factor=conversion_factor)
            print("LENGTH", len(dataframe))
            print(dataframe.head())
            dataframe = executor.process_numeric_column(dataframe=dataframe, decimal_separator=decimal_separator, conversion_factor=df_dict['conversion_factor'])
            print("LENGTH", len(dataframe))

            db_conn = create_engine(f"postgresql+psycopg2://{_DATA_DB_USER}:{_DATA_DB_PASSWORD}@{_DATA_DB_HOST}:{_DATA_DB_PORT}/DATA_DB_{country_code}")

            df_dict = executor.load_to_storage_table(dataframe=dataframe, df_dict=df_dict, storage_table_name=storage_table[1], storage_table_schema=storage_table[0], db_conn=db_conn)

            ti.xcom_push(key='load_metadata', value=df_dict)

            return 'post_load'
        except Exception as error:
            traceback.print_exc()
            print(error)
            return 'restore_backup'

    def _restore_backup(ti):
        code = ti.xcom_pull(key='code', task_ids='get_migration_data')
        backup_path = ti.xcom_pull(key='backup_db', task_ids='pre_load')
        storage_table = ti.xcom_pull(key='storage_table', task_ids='get_migration_data')
        if backup_path:
            country_code = code.split('_')[1]
            storage_table = storage_table.split(';')
            db_conn = create_engine(f"postgresql+psycopg2://{_DATA_DB_USER}:{_DATA_DB_PASSWORD}@{_DATA_DB_HOST}:{_DATA_DB_PORT}/DATA_DB_{country_code}")
            with db_conn.begin() as connection:
                connection.execute(text(f"""
                            INSERT INTO \"{storage_table[0]}\".\"{storage_table[1]}\"
                            SELECT * FROM \"{storage_table[0]}\".\"{storage_table[1]}_backup\";
                        """))

    def _post_load(ti):
        num_records_before = ti.xcom_pull(key='num_records_before', task_ids='pre_load')
        load_metadata = ti.xcom_pull(key='load_metadata', task_ids='load')

        num_records_added = load_metadata['num_records_after'] - num_records_before

        print(num_records_added)
        print(load_metadata['num_records'])

        if num_records_added == load_metadata['num_records']:
            return 'record_migration'

        return 'notify_post_load_error'

    def _trigger_product_dags(ti):
        code = ti.xcom_pull(key='code', task_ids='get_migration_data')
        load_metadata = ti.xcom_pull(key='load_metadata', task_ids='load')
        sql = f"SELECT db_code FROM data_base_report WHERE report_code = %s"
        pg_hook = PostgresHook(postgres_conn_id='platform_db')
        product_codes = pg_hook.get_records(sql=sql, parameters=(code,))
        print("PRODUCT_CODES", product_codes)
        for product_code in product_codes:
            try:
                _trigger_dag_via_api(
                    dag_id=product_code[0],
                    conf={'code': code, 'from': load_metadata["from_date"], 'to': load_metadata["to_date"]},
                )
            except Exception as e:
                print(f"There is an error trying to execute: {product_code[0]}", e)
                continue

    with dag:

        get_migration_data = PythonOperator(
            task_id='get_migration_data',
            python_callable=_get_migration_data,
            dag=dag,
            on_failure_callback=dag_failure_callback
        )

        pre_load = PythonOperator(
            task_id='pre_load',
            python_callable=_pre_load,
            on_failure_callback=dag_failure_callback
        )

        load = BranchPythonOperator(
            task_id='load',
            python_callable=_load,
            on_failure_callback=dag_failure_callback
        )

        restore_backup = PythonOperator(
            task_id='restore_backup',
            python_callable=_restore_backup,
            on_failure_callback=dag_failure_callback
        )

        post_load = BranchPythonOperator(
            task_id='post_load',
            python_callable=_post_load,
            on_failure_callback=dag_failure_callback
        )

        notify_load_error = PostgresOperator(
            task_id="notify_load_error",
            conn_id=connection_id,
            sql="sql/insert_migration_status.sql",
            params={'status': "load_error"},
            on_failure_callback=dag_failure_callback
        )

        notify_post_load_error = PostgresOperator(
            task_id="notify_post_load_error",
            conn_id=connection_id,
            sql="sql/insert_migration_status.sql",
            params={'status': "post_load_error"},
            on_failure_callback=dag_failure_callback
        )

        record_migration = PostgresOperator(
            task_id="record_migration",
            conn_id=connection_id,
            sql="sql/insert_migration.sql",
            on_failure_callback=dag_failure_callback
        )

        update_report = PostgresOperator(
            task_id="update_report",
            conn_id=connection_id,
            sql="sql/update_report.sql",
            on_failure_callback=dag_failure_callback
        )

        trigger_product_dags = PythonOperator(
            task_id='trigger_product_dags',
            python_callable=_trigger_product_dags,
        )

    get_migration_data >> pre_load >> load >> [restore_backup, post_load]
    restore_backup >> notify_load_error
    post_load >> [notify_post_load_error, record_migration]
    notify_post_load_error
    record_migration >> update_report >> trigger_product_dags
