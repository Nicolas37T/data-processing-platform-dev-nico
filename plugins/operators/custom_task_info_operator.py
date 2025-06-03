from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults
from airflow.hooks.postgres_hook import PostgresHook

class CustomTaskInfoOperator(BaseOperator):

    @apply_defaults
    def __init__(self, source_conn_id, dest_conn_id, spim_code, dest_table, *args, **kwargs):
        super(CustomTaskInfoOperator, self).__init__(*args, **kwargs)
        self.source_conn_id = source_conn_id
        self.dest_conn_id = dest_conn_id
        self.spim_code = spim_code
        self.dest_table = dest_table

    def execute(self, context):
        dag_id = context['dag'].dag_id
        execution_date = context['execution_date']

        # Construye la consulta SQL utilizando dag_id y execution_date
        sql = f'''
            SELECT DISTINCT
                dag.dag_id,
                dag_run.run_id,
                TO_CHAR(dag_run.execution_date, 'YYYY-MM-DD HH24:MI:SS.US'),
                task_instance.task_id,
                TO_CHAR(task_instance.start_date, 'YYYY-MM-DD HH24:MI:SS.US'),
                TO_CHAR(task_instance.end_date, 'YYYY-MM-DD HH24:MI:SS.US'),
                task_instance.duration,
                task_instance.state,
                task_instance.hostname,
                CONCAT('/home/datax/platform_project/logs/dag_id=', task_instance.dag_id, '/run_id=', task_instance.run_id, '/task_id=', task_instance.task_id, '/attempt=', task_instance.try_number, '.log') AS log_path
            FROM
                dag
            JOIN
                dag_run ON dag.dag_id = dag_run.dag_id
            JOIN
                task_instance ON dag_run.run_id = task_instance.run_id
            LEFT JOIN
                log ON task_instance.task_id = log.task_id
            WHERE
                dag.dag_id = '{dag_id}'
                AND dag_run.execution_date = '{execution_date}'
                AND task_instance.state IN ('success', 'failed')
                AND log.execution_date = '{execution_date}';
        '''

        print("SQL ", sql)

        # Usa el hook de PostgreSQL para obtener la conexión a la base de datos fuente
        hook_source = PostgresHook(postgres_conn_id=self.source_conn_id)
        
        conn_source = hook_source.get_conn()
        # Crea un cursor para ejecutar la consulta SQL en la base de datos fuente
        cursor_source = conn_source.cursor()

        try:
            cursor_source.execute(sql)
            results = cursor_source.fetchall()
            print("RESULT ", results)
        except Exception as e:
            self.log.error(f"Error executing SQL in source database: {str(e)}")
            cursor_source.close()
            conn_source.close()
            return

        cursor_source.close()
        conn_source.close()

        # Usa el hook de PostgreSQL para obtener la conexión a la base de datos destino
        hook_dest = PostgresHook(postgres_conn_id=self.dest_conn_id)
        conn_dest = hook_dest.get_conn()

        cursor_dest = conn_dest.cursor()
        # Verifica si la tabla existe, si no, la crea

        cursor_dest.execute(f"CREATE TABLE IF NOT EXISTS {self.dest_table} (spim_code character varying(100), dag_id character varying(250), run_id character varying(250), execution_date text, task_id character varying(250), start_date text, end_date text, duration double precision, state character varying(20), host_name character varying(1000),log_path text);")
        for result in results:
            result = (self.spim_code,) + result
            print("RESULT**********", result)
            # Personaliza la lógica según tu estructura de base de datos destino y el nombre de la tabla
            insert_sql = f"INSERT INTO {self.dest_table} (spim_code, dag_id, run_id, execution_date, task_id, start_date, end_date, duration, state, host_name, log_path) VALUES {result};"
            print("INSERT ", insert_sql)
            cursor_dest.execute(insert_sql)

        conn_dest.commit()
        cursor_dest.close()
        conn_dest.close()
