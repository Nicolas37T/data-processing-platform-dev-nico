import logging
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.models import BaseOperator


class SelectPostgresOperator(BaseOperator):
    """
     Executes sql code in a specific Postgres database
     and returns table result as a pandas dataframe
     :param postgres_conn_id: reference to a specific postgres database
     :type postgres_conn_id: string
     :param sql: the sql code to be executed
     :type sql: Can receive a str representing a sql statement,
         a list of str (sql statements), or reference to a template file.
         Template reference are recognized by str ending in '.sql'
     """

    template_fields = ('sql',)
    template_ext = ('.sql',)
    ui_color = '#ededed'

    def __init__(
            self, sql,
            conn_id='select_postgres_default', autocommit=False,
            parameters=None,
            *args, **kwargs):
        super(SelectPostgresOperator, self).__init__(*args, **kwargs)
        self.sql = sql
        self.conn_id = conn_id
        self.hook = PostgresHook(postgres_conn_id=self.conn_id)
        self.autocommit = autocommit
        self.parameters = parameters

    def execute(self, context):
        logging.info("Executing: " + str(self.sql))
        #df = self.hook.get_pandas_df(self.sql, parameters=self.parameters)
        df = self.hook.get_records(self.sql)
        logging.info("Result count: {0}".format(len(df)))
        #df = df.to_json()
        return df
        #return "test"