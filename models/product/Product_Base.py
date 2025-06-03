import inspect
import os
import re
import csv
import uuid
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy import text, MetaData, Table
from models.product.tools.product_tools import TableColumnTypes, get_free_date
from models.tools.tools import measure_execute_time, measure_resources

def get_date_sql(sql_base:str,from_date:str,to_date:str, date_col='tiempo'):
    sql_base = sql_base.strip()
    if from_date is None and to_date is None:
        return sql_base
    if from_date is None:
        raise ValueError("From date is required")
    sql_base = sql_base if sql_base[-1] != ';' else sql_base[:-1]
    sql_base = sql_base + " AND " if re.search('where',sql_base,re.IGNORECASE) else sql_base + " WHERE "
    if to_date is None:
        return sql_base + f"{date_col} >= \'{from_date}\';"
    return sql_base + f"{date_col} >= \'{from_date}\' AND {date_col} <= \'{to_date}\';"

class Product_Base():
    select: dict
    def __init__(self):
        self.path = os.path.dirname(inspect.getfile(self.__class__))

    def pre_load(self,db_conn:Engine, database_code:str, executor_code:str,from_date:str,to_date:str):
        delete_sql = f"DELETE FROM database.\"{database_code}\" WHERE robot LIKE \'%{executor_code}%\';"

        delete_sql = get_date_sql(sql_base=delete_sql, from_date=from_date, to_date=to_date)        
        print("PRINT",delete_sql)
        with db_conn.connect() as connection:
            connection.execute(text(delete_sql))
                
    
    def get_load(self,db_conn:Engine, storage_table_name:str, storage_table_schema:str,from_date:str,to_date:str)->pd.DataFrame:
        
        select_query = ', '.join([f'{key} AS {value}' for key,value in self.select.items()])
        # If no table_name is provided, use the class name as the default
        query = f'SELECT {select_query} FROM \"{storage_table_schema}\".\"{storage_table_name}\";'

        query = get_date_sql(sql_base=query, from_date=from_date, to_date=to_date, date_col='fecha')

        dtype_map = TableColumnTypes.get_column_types(engine=db_conn,schema=storage_table_schema, table_name=storage_table_name)
        dtype_filtered = {
            value: dtype_map.get(key,str)
            for key,value in self.select.items() 
        }
        
        return pd.read_sql_query(query,con=db_conn, dtype=dtype_filtered)

    def filter_table_columns(self,dataframe:pd.DataFrame, db_conn:Engine,storage_table_name:str, storage_table_schema:str):
        metadata = MetaData()
        table = Table(storage_table_name, metadata, schema=storage_table_schema, autoload_with=db_conn)
        table_cols = [col.name for col in table.columns]

        dataframe_cols = [col for col in dataframe.columns if str(col) in table_cols]

        dataframe = dataframe[dataframe_cols]

        return dataframe

    def load_to_database(self, dataframe:pd.DataFrame, database_code:str, db_conn:Engine):
        # dataframe['robot'] = self.__class__.__name__
        string_cols = dataframe.select_dtypes(exclude=['number']).columns.to_list()
        string_cols = [col for col in string_cols if col not in ['id']]
        value_cols = dataframe.select_dtypes(include=['number']).columns.to_list()
        table_name = str(uuid.uuid4()).replace('-','')
        dataframe.to_sql(table_name,con=db_conn,schema='database',index=False)
        
        load_query = f"""
            MERGE INTO database."{database_code}" target
            USING database."{table_name}" source
            ON ({' AND '.join([f'target.{col} = source.{col}' for col in string_cols])})
            WHEN MATCHED THEN
                UPDATE SET 
                    {', '.join([f"{col} = source.{col}" for col in value_cols] + [f"robot = robot || ';{self.__class__.__name__}'"])}
            WHEN NOT MATCHED THEN
                INSERT ({', '.join([col for col in dataframe.columns.to_list() if col != id] + ['robot'])})
                VALUES ({', '.join([f"source.{col}" for col in dataframe.columns.to_list() if col != id]+ [f"'{self.__class__.__name__}'"])});
        """
        delete_tmp_table = f'DROP TABLE IF EXISTS database."{table_name}";'
        with db_conn.connect() as connection:
            connection.execute(load_query)
            connection.execute(delete_tmp_table)
            
        # return df_dict
    
    def get_dates(self, db_conn:Engine,database_code:str,format='%Y-%m-%d')->tuple:        
        date_query = f"SELECT MIN(tiempo),MAX(tiempo) FROM database.\"{database_code}\""
        with db_conn.connect() as connection:
            result = connection.execute(date_query).fetchone()
        
        return result[0],result[1]
    
    @measure_resources
    @measure_execute_time
    def create_csv(self, db_conn:Engine, sql:str,database_code:str, path:str=r"/media/datax/Local_Disk_B/spim/DATABASES_CSV", plus=True):
        sql = sql.strip()
        sql = sql[:-1].strip() if sql[-1] == ';' else sql
        sql = sql + " ORDER BY tiempo ASC;" if not 'ORDER' in sql else sql

        version = 'plus' if plus else 'free'
        csv_path = os.path.join(path,f'{database_code}_{version}.csv')
        with db_conn.connect() as connection, open(csv_path, 'w', newline='', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file, delimiter=";")

            result = connection.execute(text(sql))

            writer.writerow(result.keys())

            writer.writerows(result)
        
        print(f"[SUCCESS] CSV file generated at: {csv_path}")
    
    def create_free_csv(self, db_conn:Engine, frecuency:str, database_code:str, sql:str, free_date:str):
        sql = sql.strip()
        sql = sql[:-1].strip() if sql[-1] == ';' else sql
        
        sql = sql + f" AND tiempo <= \'{free_date}\';" if "WHERE" in sql.upper() else sql + f" WHERE tiempo <= \'{free_date}\'"
        sql = sql + " ORDER BY tiempo ASC;"
        
        self.create_csv(db_conn=db_conn, sql=sql, database_code=database_code, plus=False)
        