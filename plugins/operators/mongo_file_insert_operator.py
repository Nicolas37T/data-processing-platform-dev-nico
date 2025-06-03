from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults
from pymongo import MongoClient
import pandas as pd
from openpyxl import load_workbook
from sqlalchemy import create_engine
from airflow.providers.mongo.hooks.mongo import MongoHook
from airflow.models import Variable

class MongoFileInsertOperator(BaseOperator):
    template_fields = ('file_paths', 'collection')

    @apply_defaults
    def __init__(self, mongo_conn_id, collection, file_paths, file_type='csv', *args, **kwargs):
        super(MongoFileInsertOperator, self).__init__(*args, **kwargs)
        self.mongo_conn_id = mongo_conn_id
        self.collection = collection
        self.file_paths = file_paths
        self.file_type = file_type.lower()

        if self.file_type not in ['csv', 'xls', 'xlsx', 'sqlite']:
            raise ValueError("Invalid file type. Supported types are 'csv', 'xls', 'xlsx', and 'sqlite'.")

    def execute(self, context):
        # Obtener el nombre del DAG en tiempo de ejecución
        dag_id = context['dag_run'].dag_id
        # Obtener el valor de la variable en tiempo de ejecución
        mi_variable_valor = Variable.get(dag_id, default_var=None)
        print("VARIABLE", mi_variable_valor)
        # Retrieve MongoDB connection information from Airflow connection
        mongo_conn = MongoHook.get_connection(self.mongo_conn_id)
        #mongo_conn = BaseHook.get_connection(self.mongo_conn_id)

        # Obtener los atributos de la conexión
        login = mongo_conn.login
        print("LOGIN",login)
        password = mongo_conn.password
        print("Password", password)
        host = mongo_conn.host
        print("HOST",host)
        port = mongo_conn.port
        print("PORT",port)
        database = mongo_conn.schema
        print("DATABASE",database )

        # Construir la cadena de conexión
        #mongo_uri = f"mongodb://{login}:{password}@{host}:{port}/{database}"
        mongo_uri = f"mongodb://{login}:{password}@{host}:{port}/"
        print("Mongo _URI", mongo_uri)
        
        
        
        #mongo_uri = mongo_conn.uri
        #mongo_uri = "mongodb://datax:datax@127.0.0.1:27017/"
                      #mongodb://***:***@127.0.0.1:27017/RAW_DB

        # Connect to MongoDB
        with MongoClient(mongo_uri) as client:
            frames = []

            for file_path in self.file_paths:
                # Load the file into a DataFrame of pandas based on the file type
                if self.file_type == 'csv':
                    df = pd.read_csv(file_path)
                elif self.file_type == 'xls' or self.file_type == 'xlsx':
                    df = pd.read_excel(file_path, engine='openpyxl')
                elif self.file_type == 'sqlite':
                    engine = create_engine(f"sqlite:///{file_path}")
                    df = pd.read_sql_query("SELECT * FROM your_table_name", engine)

                frames.append(df)

            # Concatenate all DataFrames into one
            acum_df = pd.concat(frames, ignore_index=True)
            # Convert the DataFrame to a list of documents (dictionaries)
            records = acum_df.to_dict(orient='records')

            try:
                # Access the specified collection and execute the query
                db = client[mongo_conn.schema]
                db[self.collection].delete_many({})
                db[self.collection].insert_many(records)
                self.log.info(f"Se insertaron {len(records)} documentos en la colección {self.collection} de MongoDB desde el archivo {self.file_paths}.")
            except Exception as e:
                self.log.error(f"Error al ejecutar la operación: {str(e)}")
                raise
            
