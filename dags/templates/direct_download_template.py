import sys
import importlib
from airflow.utils.db import provide_session
from airflow.models import XCom
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from operators.select_postgres_operator import SelectPostgresOperator
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
import socket
import pytz
sys.path.append('/home/datax/platform_project')
from models.download.tools.download_tools import convert_win_path, convert_unix_path, execution_log
from models.download.tools.download_hash import Download_Hash
from airflow.utils.db import provide_session
from airflow.models import XCom
from datetime import datetime
import pandas as pd

# Función para borrar los XCom
@provide_session
def delete_xcoms(dag_run, session=None):
    """
    Función para borrar los XComs de la ejecución actual del DAG.
    """
    session.query(XCom).filter(
    XCom.dag_id == dag_run.dag_id,
    XCom.execution_date == dag_run.execution_date
    ).delete(synchronize_session=False)
    session.commit()

def get_executor(code):    
    module = importlib.import_module(f'models.download.{code}.{code}')
    class_ = getattr(module, code)    
    return class_()

local_tz = pytz.timezone("America/La_Paz")

def create_dag(dag,connection_id,id_dag=None):

    def log_dag_run_info(context):
        """
        Registra la información de la ejecución de un DAG.
        
        Args:
            context (dict): El contexto de ejecución del DAG.
        """
        dag_run = context.get('dag_run')
        ti = context['task_instance']
        execution_date = dag_run.start_date.astimezone(local_tz).strftime('%Y-%m-%d %H:%M:%S')
        end_time = datetime.now(local_tz)
        
        # Calcular la duración del DAG
        duration = end_time - dag_run.start_date
        
        # Obtener el valor de xcom
        xcom_pull = lambda key: ti.xcom_pull(task_ids='read_download_data', key=key)
        path = xcom_pull('file_path')
        key_words = xcom_pull('key_words')
        file_name = xcom_pull('file_name')
        publication_frequency = xcom_pull('file_frequency')
        main_url = xcom_pull('file_url')

        # Obtener el estado de la tarea específica
        get_state = lambda task_id: dag_run.get_task_instance(task_id).state == 'success'
        execution_type = None
        files = []
        num = 0

        if get_state('notify_url_broken'):
            print("El camino seguido fue el de 'tarea_rama_1'.")
            execution_type = "4"  # "Url Broken"
        elif get_state('notify_success_revision_only'):
            print("El camino seguido fue el de 'tarea_rama_2'.")
            execution_type = "2"  # "Revision Only"
        elif get_state('notify_success_download_revision'):
            print("El camino seguido fue el de 'tarea_rama_3'.")
            execution_type = "3"  # "Download Revision"
        elif get_state('notify_success_download'):
            print("El camino seguido fue el de 'tarea_rama_3'.")
            execution_type = "1"  # "Download"
            files = ti.xcom_pull(task_ids='store_files', key='files_dicts')
        else:
            print("No se siguió ninguno de los caminos de ramificación esperados.")

        execution_log(
            path, execution_date, key_words, id_dag, file_name,
            publication_frequency, context['dag'].schedule_interval, 
            ";".join(context['dag'].tags), execution_type, duration, 
            num, files, main_url
        )
        # Llamada a la función para borrar los XComs al final del callback de éxito
        dag_run = context.get('dag_run')
        delete_xcoms(dag_run)

    # Función de callback para registrar fallos
    def dag_failure_callback(context):
        """
        Callback que se ejecuta cuando falla una tarea en el DAG.
        Registra la información del fallo en una base de datos PostgreSQL.

        Parámetros:
        context (dict): El contexto proporcionado por Airflow que contiene información sobre la tarea fallida.
        """
        # Extraer información del contexto
        task_instance = context.get('task_instance')
        log_url = task_instance.log_url
        dag_run = context.get('dag_run')
        execution_date = dag_run.start_date.astimezone(local_tz)
        exception = context.get('exception')
        host = socket.gethostname()
        
        # Obtener nombre del archivo desde XCom
        file_name = task_instance.xcom_pull(task_ids='read_download_data', key='file_name')
        
        # Datos específicos de la tarea y el DAG
        file_code = dag_run.dag_id
        spim_code = ";".join(context['dag'].tags)
        task = task_instance.task_id

        # Conectar a la base de datos PostgreSQL
        pg_hook = PostgresHook(postgres_conn_id=connection_id)

        # SQL de inserción
        insert_sql = """
            INSERT INTO dag_run_exceptions (execute_date, file_code, file_name, spim_code, failed_task, exception, log_path, host)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        # Ejecutar la inserción
        pg_hook.run(insert_sql, parameters=(execution_date, file_code, file_name, spim_code, task, str(exception), log_url, host))

        dag_run = context.get('dag_run')
        delete_xcoms(dag_run)

    dag.on_success_callback = log_dag_run_info

    dag.on_failure_callback = dag_failure_callback

    # Crear una instancia del ejecutor asociado a la DAG
    executor = get_executor(id_dag)

    def _read_download_data(ti):
        """
        Lee los datos de la descarga y los asigna a variables XComs para que sean accesibles por las demás tareas.

        Args:
            ti (TaskInstance): Instancia de Tarea.

        Returns:
            None
        """
        file_path = ""
        file_url = ""
        file_id = ""
        file_type = ""
        # Obtener los valores de XCom
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

        # Asignar los valores a las variables XCom
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
        """
        Verifica si el URL es accesible o no.

        Args:
            ti (TaskInstance): Instancia de Tarea.

        Returns:
            bool: True si es accesible, False en otro caso.
        """
        isReachable = False  # Valor de salida
        url = (ti.xcom_pull(key='file_url', task_ids='read_download_data'))
        isReachable = executor.verify_url(url)
        if isReachable:
            return 'verify_download'
        else:
            return 'notify_url_broken'
        
    def _verify_download(ti):
        """ Obtiene los Urls del ultimo archivo de la Web
        Args:
            file url (url): Url del archivo
        Returns:
            array (lastFileLinks): retorna un arreglo con los  Urls del archivo (formato: xlsx, pdf, ...)
        """
        file_paths = []
        url = (ti.xcom_pull(key='file_url', task_ids='read_download_data'))
        updatedTo = (ti.xcom_pull(key='file_updated_to', task_ids='read_download_data'))
        file_path = (ti.xcom_pull(key='file_path', task_ids='read_download_data'))
        file_paths = executor.verify_download(url, str(updatedTo), file_path)#investgar el tipo de dato que se guarda en los xcoms
        print("Archivos descargados ", file_paths)
        ti.xcom_push(key='files_paths', value=file_paths)
        print("path de los archivos ",file_paths)
        if not file_paths:
            print("entro aqui record_revision")
            return 'record_revision_only'
        else:
            print("entro aqui file_download")
            return 'compare_files' 
        
    def _compare_files(ti):
        """
        Compara si dos archivos son iguales o no.

        Args:
            ti (TaskInstance): Instancia de Tarea.

        Returns:
            str: 'download_review' si los archivos son iguales, o 'store_files' si son diferentes.
        """
        file_path_datax = ti.xcom_pull(key='last_file_path', task_ids='read_download_data')
        file_path_download = ti.xcom_pull(key='files_paths', task_ids='verify_download')
        updated_to = (ti.xcom_pull(key='file_updated_to', task_ids='read_download_data'))
        ti.xcom_push(key='file_path_download', value = file_path_download)
        files_dicts = executor.compare_files(file_path_download, updated_to)
        ti.xcom_push(key='files_dicts', value = files_dicts)
        if not files_dicts:
            return 'record_download_revision'
        else:
            return 'store_files'
        
    def _store_files(ti):
        """
        Almacena los archivos y actualiza la información relacionada.

        Args:
            ti (TaskInstance): Instancia de Tarea.

        Returns:
            str: 'download_review' si los archivos son iguales, o 'store_files' si son diferentes.
        """
        file_frequency = (ti.xcom_pull(key='file_frequency', task_ids='read_download_data'))
        files_dicts = (ti.xcom_pull(key='files_dicts', task_ids='compare_files'))
        path = (ti.xcom_pull(key='file_path', task_ids='read_download_data'))
        short_name  = (ti.xcom_pull(key='short_name', task_ids='read_download_data'))
        
        files_dicts = executor.store_files(files_dicts, short_name , file_frequency, path)
        for item in files_dicts:
            item['file_hash'] = Download_Hash(download_path=item['datax_file_path']).get_download_hash()
            item['datax_file_path'] = convert_unix_path(item['datax_file_path'])
        max_date_item = max(files_dicts, key=lambda x: datetime.strptime(x['updated_to'], "%Y-%m-%d"))
        ti.xcom_push(key='file_update', value=max_date_item)
        ti.xcom_push(key='files_dicts', value=files_dicts)

    def _assigner(ti):    
        downloads_records = ti.xcom_pull(task_ids='record_download')
    
        conversion_pg_hook = PostgresHook(postgres_conn_id='platform_db')
        conversion_connection = conversion_pg_hook.get_conn() 
        
        conversion_sql = f"SELECT r.code as executor_code, r.converted_to, f.code FROM report as r LEFT JOIN file as f ON r.id_file = f.id_file WHERE f.code ='{id_dag}' AND r.\"isActive\" = TRUE"
        download_df = pd.DataFrame(data=downloads_records,columns=['id_download','path','downloaded_to'])
        conversion_df = pd.read_sql(sql=conversion_sql, con=conversion_connection)
        
        download_df['code'] = id_dag
        merged_df = pd.merge(left=download_df,right=conversion_df,how='inner',on='code')

        merged_df['code'] = merged_df['code'].replace('D_','C_',regex=True)
        merged_df = merged_df.sort_values(by=['downloaded_to', 'executor_code'], ascending=[True, True])
        
        downloads = merged_df.to_dict(orient='records')
        ti.xcom_push(key='downloads', value=downloads)        
        
    def _trigger_dags(**context):
        ti = context['ti']
        downloads = ti.xcom_pull(task_ids='assigner', key='downloads')
        for download in downloads:    
            TriggerDagRunOperator(
                task_id=f'trigger_{download["executor_code"]}',
                trigger_dag_id=f'{download["code"]}',
                conf={'file': download["path"], 'code':download["executor_code"], 'id_download':download["id_download"]},
                wait_for_completion=True,
            allowed_states=['success', 'failed']
            ).execute(context=context)

    with dag:
        
        get_download_data = SelectPostgresOperator(
        task_id='get_download_data',
        postgres_conn_id=connection_id,
        sql="sql/get_download_data.sql",
        params={'file_code':"'"+id_dag+"'"},
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
            postgres_conn_id=connection_id,
            sql="sql/insert_broken_url.sql",
            params= {'file_code':"'"+id_dag+"'"},
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
            postgres_conn_id=connection_id,
            sql="sql/insert_review.sql",
            params= {'id_user': "'1'", 'type':"'Revision Only'"},
        )
        
        record_download_revision = PostgresOperator(
            task_id="record_download_revision",
            postgres_conn_id=connection_id,
            sql="sql/insert_review.sql",
            params= {'id_user': "'1'", 'type':"'Download Revision'"},
        )
        
        notify_success_revision_only = PostgresOperator(
            task_id="notify_success_revision_only",
            postgres_conn_id= connection_id,
            sql="sql/insert_custom_dag_run.sql",
            params= {'state':"'Revision Only'"}
        )
        
        notify_success_download_revision = PostgresOperator(
            task_id="notify_success_download_revision",
            postgres_conn_id= connection_id,
            sql="sql/insert_custom_dag_run.sql",
            params= {'state':"'Download Revision'"}
        )

        record_download =PostgresOperator(
            task_id="record_download",
            postgres_conn_id=connection_id,
            sql="sql/insert_download.sql",
            params= { 'id_user':"'1'", 'state':"'Downloaded'", 'type_file':"'last file'"},
            do_xcom_push=True
        )

        update_file =PostgresOperator(
            task_id="update_file",
            postgres_conn_id=connection_id,
            sql="sql/update_file.sql",
        )
        
        notify_success_download = PostgresOperator(
            task_id="notify_success_download",
            postgres_conn_id= connection_id,
            sql="sql/insert_custom_dag_run.sql",
            params= {'state':"'Successful Donwload'"}
        )

        assigner =  PythonOperator(
            task_id='assigner',
            python_callable=_assigner,
        )

        trigger_task = PythonOperator(
            task_id='trigger_dags',
            python_callable=_trigger_dags,
            provide_context=True
        )

    get_download_data >> read_download_data >> verify_url >> [verify_download, notify_url_broken]
    notify_url_broken
    verify_download >> [record_revision_only, compare_files]
    record_revision_only >> notify_success_revision_only
    compare_files >> [store_files, record_download_revision] 
    record_download_revision >> notify_success_download_revision
    store_files >> record_download >> update_file >> notify_success_download >> assigner >> trigger_task