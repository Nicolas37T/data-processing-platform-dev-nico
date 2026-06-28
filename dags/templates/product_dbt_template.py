import os
import pytz
import sys
sys.path.append('/home/datax/platform_project')
from sqlalchemy import create_engine
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from models.product.tools.product_tools import get_free_date
from models.product.Product_Base import Product_Base

# Setting the local timezone
local_tz = pytz.timezone('America/La_Paz')

_DATA_DB_HOST = os.environ.get("DATA_DB_HOST", "postgres")
_DATA_DB_PORT = os.environ.get("DATA_DB_PORT", "5432")
_DATA_DB_USER = os.environ.get("DATA_DB_USER", "postgres")
_DATA_DB_PASSWORD = os.environ.get("DATA_DB_PASSWORD", "datax")

def create_dag(dag,connection_id,id_dag):
   
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

        ti.xcom_push(key='dbt_dict', value={
            "code": query_result_report['code'],
            "from": from_date
        })

    def _post_load(ti):
        code = ti.xcom_pull(key='code', task_ids='get_product_data')
        data_frequency = ti.xcom_pull(key='data_frequency', task_ids='get_product_data')
        csv_sql = ti.xcom_pull(key='csv_sql', task_ids='get_product_data')

        country_code = code.split('_')[1]
        db_conn = create_engine(f"postgresql+psycopg2://{_DATA_DB_USER}:{_DATA_DB_PASSWORD}@{_DATA_DB_HOST}:{_DATA_DB_PORT}/DATA_DB_{country_code}")

        executor = Product_Base()

        csv_sql = csv_sql.strip()

        free_date = get_free_date(db_conn=db_conn, frecuency=data_frequency, database_code=id_dag)

        last_date = executor.get_dates(db_conn=db_conn,database_code=id_dag)[1]
        if csv_sql:
            executor.create_csv(db_conn=db_conn, sql=csv_sql,database_code=id_dag)
            executor.create_free_csv(db_conn=db_conn,frecuency=data_frequency,sql=csv_sql,database_code=id_dag,free_date=free_date)
        
        ti.xcom_push(key='free_date', value=free_date)
        ti.xcom_push(key='last_date', value=last_date)

    with dag:

        get_product_data = PythonOperator(
            task_id='get_product_data',
            python_callable=_get_product_data,
            dag=dag,
            provide_context=True            
        )        

        load = BashOperator(
            task_id='load',
            bash_command= f'cd ~/platform_project/dbt/product && dbt run --select {id_dag} --vars \'{{ ti.xcom_pull(task_ids="pre_load", key="dbt_dict") | tojson }}\'',
        )
       
        # post_load = BashOperator(
        #     task_id='post_load',
        #     bash_command=f'cd ~/platform_project/dbt/product && dbt test --select {id_dag}*',            
        # )
        post_load = PythonOperator(
            task_id='post_load',
            python_callable= _post_load
        )

        update_database = PostgresOperator(
            task_id="update_database",
            postgres_conn_id=connection_id,
            sql="sql/update_database.sql"
        )

    # Define task dependencies to establish the order of execution in the DAG
    get_product_data >> load >> post_load >> update_database
   