import inspect
import os
import re
import sqlite3
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy import text, MetaData, Table
from datetime import datetime
from models.download.tools.download_tools import format_date
from models.conversion.tools.conversion_tools import to_numeric_datax

class Migration_Base():
    def __init__(self):
        self.path = os.path.dirname(inspect.getfile(self.__class__))

    def pre_load(self,db_conn:Engine, storage_table_name:str, storage_table_schema:str,load_scope:str,load_dates:dict):
        load_scope = load_scope if load_scope != None else ''
        load_scope = re.sub(r'\s+','',load_scope.strip().lower())
        count_query = f"SELECT COUNT(*) FROM \"{storage_table_schema}\".\"{storage_table_name}\""
        print("LOAD DATES", load_dates)
        converted_to = load_dates['max']
        converted_to = format_date(date=converted_to) if isinstance(converted_to,str) else converted_to
        
        
        with db_conn.begin() as connection:
            connection.execute(text(f"""
                DROP TABLE IF EXISTS \"{storage_table_schema}\".\"{storage_table_name}_backup\";
                CREATE TABLE IF NOT EXISTS \"{storage_table_schema}\".\"{storage_table_name}_backup\" AS 
                SELECT * FROM \"{storage_table_schema}\".\"{storage_table_name}\" WHERE false;
            """))
            if load_scope and load_scope == 'all':
                connection.execute(text(f"""
                    INSERT INTO \"{storage_table_schema}\".\"{storage_table_name}_backup\"
                    SELECT * FROM \"{storage_table_schema}\".\"{storage_table_name}\";
                """))
                connection.execute(text(f"DELETE FROM \"{storage_table_schema}\".\"{storage_table_name}\";"))
                return f'\"{storage_table_schema}\".\"{storage_table_name}_backup\"',0            
            
            date_condition = None
            if not load_scope:
                date_condition = f"{load_dates['min']}\' and fecha <= \'{load_dates['max']}"
            elif load_scope == 'current_year':
                date_condition = f'{converted_to.year}-01-01'
            
            connection.execute(text(f"""
                INSERT INTO \"{storage_table_schema}\".\"{storage_table_name}_backup\"
                SELECT * FROM \"{storage_table_schema}\".\"{storage_table_name}\" WHERE fecha >= \'{date_condition}\';
            """))
            connection.execute(text(f"DELETE FROM \"{storage_table_schema}\".\"{storage_table_name}\" WHERE fecha >= \'{date_condition}\';"))

            result = connection.execute(text(count_query))
            num_records = result.scalar()
            return f'{storage_table_schema}.{storage_table_name}_backup',num_records


    def read_table(self,table_path:str, table_name=None)->pd.DataFrame:
        # If no table_name is provided, use the class name as the default
        if not table_name:
            table_name = self.__class__.__name__
        with sqlite3.connect(table_path) as connection:
            query = f"SELECT * FROM {table_name}"
        return pd.read_sql_query(query,con=connection)    

    def process_numeric_column(self,dataframe:pd.DataFrame, decimal_separator: str, conversion_factor:int) -> pd.DataFrame:

        dataframe[dataframe.columns[-1]] = to_numeric_datax(serie=dataframe[dataframe.columns[-1]],decimal_separator=decimal_separator)
        dataframe = dataframe.dropna(subset=dataframe.columns[-1])        
        dataframe[dataframe.columns[-1]] = dataframe[dataframe.columns[-1]] * conversion_factor
        
        return dataframe

    def filter_table_columns(self,dataframe:pd.DataFrame, db_conn:Engine,storage_table_name:str, storage_table_schema:str):
        metadata = MetaData()
        table = Table(storage_table_name, metadata, schema=storage_table_schema, autoload_with=db_conn)
        table_cols = [col.name for col in table.columns]

        dataframe_cols = [col for col in dataframe.columns if str(col) in table_cols]

        dataframe = dataframe[dataframe_cols]

        return dataframe
    
    def load_to_storage_table(self, dataframe:pd.DataFrame, df_dict:dict, storage_table_name:str, storage_table_schema:str, db_conn:Engine):

        dataframe = self.filter_table_columns(dataframe=dataframe, db_conn=db_conn, storage_table_name=storage_table_name, storage_table_schema=storage_table_schema)
        from_date, to_date = dataframe['fecha'].min(), dataframe['fecha'].max()
        
        num_records = len(dataframe)

        if num_records<10_000:
            dataframe.to_sql(name=storage_table_name,schema=storage_table_schema, con=db_conn, if_exists="append", index=False)
        elif num_records<100_000:
            dataframe.to_sql(name=storage_table_name,schema=storage_table_schema, con=db_conn, if_exists="append", index=False,chunksize=1_000)
        else:
            dataframe.to_sql(name=storage_table_name,schema=storage_table_schema, con=db_conn, if_exists="append", index=False,chunksize=10_000)
        
        count_query = f"SELECT COUNT(*) FROM \"{storage_table_schema}\".\"{storage_table_name}\""
        with db_conn.connect() as connection:
            result = connection.execute(text(count_query))
            num_records_after = result.scalar()
            
        df_dict['num_records'] = num_records
        df_dict['num_records_after'] = num_records_after
        df_dict['from_date'] = from_date
        df_dict['to_date'] = to_date
        return df_dict
    
    def get_table_dates(self,table_path:str, table_name=None):
        if not table_name:
            table_name = self.__class__.__name__
        with sqlite3.connect(table_path) as connection:
            query = f"SELECT MIN(fecha), MAX(fecha) FROM {table_name} WHERE fecha != '-'"
            result = connection.execute(query)
            data = result.fetchone()
        return {
            "min":data[0],
            "max":data[1]
        }