from airflow.models import Variable
from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults
from airflow.hooks.postgres_hook import PostgresHook
import json
import datetime


class ConversionStatusLog(BaseOperator):
    """
    Operador personalizado que accede a una variable definida en Airflow.
    """

    @apply_defaults
    def __init__(self, variable_name, postgres_conn_id, table_name, *args, **kwargs):
        """
        Constructor del operador.

        :param variable_name: El nombre de la variable en Airflow.
        :type variable_name: str
        :param postgres_conn_id: El ID de conexión de PostgreSQL definido en Airflow.
        :type postgres_conn_id: str
        :param table_name: El nombre de la tabla en PostgreSQL.
        :type table_name: str
        """
        super(ConversionStatusLog, self).__init__(*args, **kwargs)
        self.variable_name = variable_name
        self.postgres_conn_id = postgres_conn_id
        self.table_name = table_name
    def execute(self, context):
        """
        Método ejecutado cuando la tarea se ejecuta.

        :param context: El contexto proporcionado por Airflow.
        :type context: dict
        """
        # Obtener el dag_id
        dag_id = context['dag'].dag_id
        execution_date = context['execution_date']
        # Obtener el valor de la variable desde Airflow
        conversion_data = Variable.get(self.variable_name)
        #print("VALOR DE LA VARIABLE", conversion_data)
        #print("Type VARIBALE", type(conversion_data))
        self.log.info(f"El valor de {self.variable_name} es: {conversion_data}")

        obj_conversion_data = json.loads(conversion_data)
        
        # Usa el hook de PostgreSQL para obtener la conexión a la base de datos destino
        hook_dest = PostgresHook(postgres_conn_id=self.postgres_conn_id)
        conn_dest = hook_dest.get_conn()
        cursor_dest = conn_dest.cursor()
        # Verifica si la tabla existe, si no, la crea
        #cursor_dest.execute(f"CREATE TABLE IF NOT EXISTS {self.dest_table} (id_script_report_instance BIGSERIAL PRIMARY KEY, id_script integer NOT NULL DEFAULT 0, id_report integer NOT NULL DEFAULT 0, run_date date, report_name text, spim_code character varying(100), dag_id character varying(100), execution_date text, path_file text, read_script text, is_readable character varying(100));")



        sql_queries = []
        # Construir SQLs de inserción
        spim_code = obj_conversion_data["codespim"]
        for file in obj_conversion_data["files"]:
            file_path = file["file_path"]
            is_readable = file["is_readable"]
            read_script = file["read_script"]
            id_read_script = file ["id_read_script"]
            for report in file["reports"]:
                report_name = report["report_name"]
                id_report = report["id_report"]
                transformation_scrip = report["transformation_script"]
                id_transformation_script = report["id_transformation_script"]
                is_transformed = report["is_transformed"]
                structure_review_script = report["structure_review_script"]
                id_structure_review_script = report["id_structure_review_script"]
                structure_conservator = report["structure_conservator"]
                extraction_script = report["extraction_script"]
                id_extraction_script = report["id_extraction_script"]
                is_extractable = report["is_extractable"]
                path_temp = report["path_temp"]
                previous_extracted_file = report["previous_extracted_file"]

                sql = f"INSERT INTO {self.table_name} (id_script, id_report, run_date, report_name, spim_code, dag_id, execution_date, file_path, read_script, is_readable, id_read_script) VALUES ('{id_extraction_script}', '{id_report}', '{datetime.datetime.now()}', '{report_name}', '{spim_code}', '{dag_id}', '{execution_date}', '{file_path}', '{read_script}', '{is_extractable}', '{id_read_script}');"
                print("SQL", sql)
                sql = f"INSERT INTO {self.table_name} (id_script, id_report, run_date, report_name, spim_code, dag_id, execution_date, file_path, read_script, is_readable, id_read_script) VALUES ('{id_structure_review_script}', '{id_report}', '{datetime.datetime.now()}', '{report_name}', '{spim_code}', '{dag_id}', '{execution_date}', '{file_path}', '{read_script}', '{is_readable}', '{id_read_script}');"
                print("SQL", sql)
                sql = f"INSERT INTO {self.table_name} (id_script, id_report, run_date, report_name, spim_code, dag_id, execution_date, file_path, read_script, is_readable, id_read_script) VALUES ('{id_extraction_script}', '{id_report}', '{datetime.datetime.now()}', '{report_name}', '{spim_code}', '{dag_id}', '{execution_date}', '{file_path}', '{read_script}', '{is_readable}', '{id_read_script}');"
                print("SQL", sql)
                sql_queries.append(sql)
                #sql_queries.append(sql)




        '''
        
        for result in results:
            result = (self.spim_code,) + result
            # Personaliza la lógica según tu estructura de base de datos destino y el nombre de la tabla
            insert_sql = f"INSERT INTO {self.dest_table} (spim_code, dag_id, run_id, execution_date, task_id, start_date, end_date, duration, state, host_name, log_path) VALUES {result};"
            print("INSERT ", insert_sql)
            cursor_dest.execute(insert_sql)

        conn_dest.commit()
        cursor_dest.close()
        conn_dest.close()








        sql_queries = []
        for key, value in valor_variable.items():
            sql = f"INSERT INTO {self.table_name} (dag_id, columna_key, columna_value) VALUES ('{dag_id}', '{key}', '{value}');"
            

        # Conectar a PostgreSQL y ejecutar las consultas
        hook = PostgresHook(postgres_conn_id=self.postgres_conn_id)
        for sql_query in sql_queries:
            hook.run(sql_query)
            self.log.info(f"Consulta ejecutada: {sql_query}")

        '''