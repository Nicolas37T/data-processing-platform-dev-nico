from airflow.models import BaseOperator
#from airflow.utils.decorators import apply_defaults
from pymongo import MongoClient
from airflow.providers.mongo.hooks.mongo import MongoHook
import pandas as pd

class MongoCustomOperator(BaseOperator):
    template_fields = ['query', 'update']

    #@apply_defaults
    def __init__(self, mongo_conn_id, collection, operation, data=None, query=None, update=None, provide_context=False, *args, **kwargs):
        super(MongoCustomOperator, self).__init__(*args, **kwargs)
        self.mongo_conn_id = mongo_conn_id
        self.collection = collection
        self.operation = operation
        self.data = data
        self.query = query
        self.update = update
        self.provide_context = provide_context

    def execute(self, context):
        # Retrieve MongoDB connection information from Airflow connection
        mongo_conn = MongoHook.get_connection(self.mongo_conn_id)
        connection = f"mongodb://{mongo_conn.login}:{mongo_conn.password}@{mongo_conn.host}:{mongo_conn.port}/"

        # Connect to MongoDB
        client = MongoClient(connection)
        db = client[mongo_conn.schema][self.collection]

        try:
            # Perform the specified operation
            if self.operation == 'read':
                result_df = pd.DataFrame(list(db.find(self.query))) if self.query else pd.DataFrame(list(db.find()))
                self.log.info(f'Resultados de la lectura:\n{result_df}')

            elif self.operation == 'write':
                records = self.data.to_dict(orient='records')
                db.insert_many(records)

            elif self.operation == 'update':
                print("Consulta ", self.query)
                print("Actualizacion ", self.update)
                print("consulta ejecutada ",db.update_many(self.query, self.update))

            elif self.operation == 'delete':
                db.delete_many(self.query)

            else:
                raise ValueError("Operación no válida. Las operaciones válidas son 'read', 'write', 'update' y 'delete'.")
            if self.provide_context:
                execution_date = context['execution_date']
                self.log.info("Airflow context provided. Execution date: {}".format(execution_date))


        finally:
            # Close the MongoDB connection
            client.close()
