import os
import importlib
import pytz
import sys
sys.path.append('/home/datax/platform_project')
from sqlalchemy import create_engine, inspect, text
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.utils.db import provide_session
from airflow.models import XCom
from models.product.tools.product_tools import get_free_date

# Setting the local timezone
local_tz = pytz.timezone('America/La_Paz')

@provide_session
def delete_xcoms(dag_run, session=None):
    """
    Function to delete XComs for the current DAG run, ensuring no old XCom data interferes with current execution.
    """
    session.query(XCom).filter(
    XCom.dag_id == dag_run.dag_id,
    XCom.execution_date == dag_run.execution_date
    ).delete(synchronize_session=False)
    session.commit()


def create_dag(dag,connection_id,id_dag):

    def get_executor(code):        
        module = importlib.import_module(f'models.product.{id_dag}.{code}')
        class_ = getattr(module, code)    
        return class_()

    def dag_failure_callback(context):         
        dag_run = context['dag_run']        

        delete_xcoms(dag_run=dag_run)   

    def _get_product_data(**context):
        ti = context["ti"]
        report_code = context['dag_run'].conf.get('code')
        from_date = context['dag_run'].conf.get('from')
        to_date = context['dag_run'].conf.get('to')
        
        pg_hook = PostgresHook(postgres_conn_id=connection_id)
        select_columns_report = ['id_report','code','storage_table']
        sql_report = f"SELECT {', '.join(['r.'+ col for col in select_columns_report])} FROM report AS r WHERE r.code = %s"

        query_result_report = pg_hook.get_first(sql_report,parameters=(report_code,))    
        query_result_report = dict(zip(select_columns_report,query_result_report))

        select_columns_database = ['id_data_base','name','data_frequency','csv_sql']
        sql_database = f"SELECT {', '.join(['d.'+ col for col in select_columns_database])} FROM data_base AS d WHERE d.db_code = %s"

        query_result_database = pg_hook.get_first(sql_database,parameters=(id_dag,))    
        query_result_database = dict(zip(select_columns_database,query_result_database))        
        
        ti.xcom_push(key='id_report', value=query_result_report['id_report'])        
        ti.xcom_push(key='code', value=query_result_report['code'])        
        ti.xcom_push(key='storage_table', value=query_result_report['storage_table'])        
        ti.xcom_push(key='from_date', value=from_date)
        ti.xcom_push(key='to_date', value=to_date)
        
        ti.xcom_push(key='id_data_base', value=query_result_database['id_data_base'])
        ti.xcom_push(key='name', value=query_result_database['name'])
        ti.xcom_push(key='data_frequency', value=query_result_database['data_frequency'])
        ti.xcom_push(key='csv_sql', value=query_result_database['csv_sql'])

    def _pre_load(ti):
        from_date = ti.xcom_pull(key='from_date', task_ids='get_product_data')
        to_date = ti.xcom_pull(key='to_date', task_ids='get_product_data')
        code = ti.xcom_pull(key='code', task_ids='get_product_data')
        
        print("FROM_DATE",from_date)
        print("TO_DATE",to_date)
        country_code = code.split('_')[1]
       
        executor = get_executor(code=code)
        db_conn = create_engine(f"postgresql+psycopg2://postgres:datax@10.0.0.12:5432/DATA_DB_{country_code}")
        with db_conn.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS database"))
        inspector = inspect(db_conn)
        table_exists = inspector.has_table(id_dag, schema='database')
        print("TABLE_EXISTS",table_exists)
        if not table_exists:
            print('SQL_PATH',executor.path)
            sql_file_path = os.path.join(executor.path,f'{id_dag}.sql')
            print('SQL_PATH',sql_file_path)
            if not os.path.exists(sql_file_path):
                raise FileNotFoundError(f"SQL file doesn't exists")

            with open(sql_file_path, 'r') as file:
                sql_query = file.read()
            sql_query = sql_query % (id_dag, id_dag)    
            with db_conn.connect() as connection:
                connection.execute(sql_query)
        
        executor.pre_load(db_conn=db_conn, database_code=id_dag, executor_code=code,from_date=from_date,to_date=to_date)        

    def _load(ti):    
        
        code = ti.xcom_pull(key='code', task_ids='get_product_data')        
        storage_table = ti.xcom_pull(key='storage_table', task_ids='get_product_data')
        from_date = ti.xcom_pull(key='from_date', task_ids='get_product_data')
        to_date = ti.xcom_pull(key='to_date', task_ids='get_product_data')
        
        country_code = code.split('_')[1]
        storage_table = storage_table.split(';')


        executor = get_executor(code=code)

        db_conn = create_engine(f"postgresql+psycopg2://postgres:datax@10.0.0.12:5432/DATA_DB_{country_code}")
        dataframe = executor.get_load(db_conn=db_conn, storage_table_name=storage_table[1], storage_table_schema=storage_table[0],from_date=from_date,to_date=to_date)
        if dataframe.empty:
            print("There's no data to load")
            return
        
        dataframe = executor.transform_report(dataframe=dataframe)
        # dataframe['robot'] = executor.__class__.__name__
        dataframe = executor.filter_table_columns(dataframe=dataframe, db_conn=db_conn,storage_table_name=id_dag, storage_table_schema='database')

        # if hasattr(executor,"value_columns"):
        #     load_to_merge = executor.get_load_to_merge(db_conn=db_conn,to_load_dataframe=dataframe,database_code=id_dag)

        #     if not load_to_merge.empty:
        #         dataframe = executor.merge_verticaly_report(main_dataframe=load_to_merge, to_load_dataframe=dataframe)

        dataframe = dataframe.sort_values(by='tiempo')
        executor.load_to_database(dataframe=dataframe, database_code=id_dag, db_conn=db_conn)        


    def _post_load(ti):
        code = ti.xcom_pull(key='code', task_ids='get_product_data')
        data_frequency = ti.xcom_pull(key='data_frequency', task_ids='get_product_data')
        csv_sql = ti.xcom_pull(key='csv_sql', task_ids='get_product_data')

        country_code = code.split('_')[1]
        db_conn = create_engine(f"postgresql+psycopg2://postgres:datax@10.0.0.12:5432/DATA_DB_{country_code}")

        executor = get_executor(code=code)

        free_date = get_free_date(db_conn=db_conn, frecuency=data_frequency, database_code=id_dag)

        last_date = executor.get_dates(db_conn=db_conn,database_code=id_dag)[1]
        if csv_sql is not None and csv_sql.strip() != "":
            executor.create_csv(db_conn=db_conn, sql=csv_sql,database_code=id_dag)
            executor.create_free_csv(db_conn=db_conn,frecuency=data_frequency,sql=csv_sql,database_code=id_dag,free_date=free_date)
        
        ti.xcom_push(key='free_date', value=free_date)
        ti.xcom_push(key='last_date', value=last_date)

    with dag:

        get_product_data = PythonOperator(
            task_id='get_product_data',
            python_callable=_get_product_data,
            dag=dag,
            provide_context=True,
            on_failure_callback=dag_failure_callback

        )

        # load_testing = PythonOperator(
        #     task_id='load_testing',
        #     python_callable= _load_testing,
        # )

        pre_load = PythonOperator(
            task_id='pre_load',
            python_callable= _pre_load,
            on_failure_callback=dag_failure_callback
        )

        load = PythonOperator(
            task_id='load',
            python_callable= _load,
            on_failure_callback=dag_failure_callback
        )

        # restore_backup = PythonOperator(
        #     task_id='restore_backup',
        #     python_callable= _restore_backup,
        #     on_failure_callback=dag_failure_callback
        # )

        # load_validation = PythonOperator(
        #     task_id='load_validation',
        #     python_callable= _load_validation,
        # )

        post_load = PythonOperator(
            task_id='post_load',
            python_callable= _post_load,
            on_failure_callback=dag_failure_callback
        )

        # sub_products = PythonOperator(
        #     task_id='sub_products',
        #     python_callable= _sub_products,
        #     on_failure_callback=dag_failure_callback
        # )

        # notify_load_error = PostgresOperator(
        #     task_id="notify_load_error",
        #     postgres_conn_id=connection_id,
        #     sql="sql/insert_product_status.sql", 
        #     params= {'status':"load_error"},
        #     on_failure_callback=dag_failure_callback
        # )

        # notify_post_load_error = PostgresOperator(
        #     task_id="notify_post_load_error",
        #     postgres_conn_id=connection_id,
        #     sql="sql/insert_product_status.sql", 
        #     params= {'status':"post_load_error"},
        #     on_failure_callback=dag_failure_callback
        # )

        # record_product = PostgresOperator(
        #     task_id="record_product",
        #     postgres_conn_id=connection_id,
        #     sql="sql/insert_product.sql",
        #     on_failure_callback=dag_failure_callback
        # )

        update_database = PostgresOperator(
            task_id="update_database",
            postgres_conn_id=connection_id,
            sql="sql/update_database.sql",
            on_failure_callback=dag_failure_callback
        )

    # Define task dependencies to establish the order of execution in the DAG
    get_product_data >> pre_load >> load >> post_load >> update_database