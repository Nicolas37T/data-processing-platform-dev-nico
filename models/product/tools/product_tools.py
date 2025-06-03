import math
import pandas as pd
import numpy as np
from datetime import date
from abc import ABC, abstractmethod
from sqlalchemy.engine import Engine
from sqlalchemy import text, create_engine, inspect
from rapidfuzz import process, fuzz
from datetime import datetime
from models.download.tools.download_tools import format_date
from models.conversion.tools.text_normalization import Text_Normalization

def get_dim_tiempo(db_conn:Engine, dataframe:pd.DataFrame)->pd.DataFrame:
    dim_tiempo_df = pd.read_sql('SELECT id_tiempo, fecha FROM dim_tiempo;',con=db_conn)
    
    dataframe['tiempo'] = pd.to_datetime(dataframe['tiempo'],errors='raise').dt.strftime(date_format='%Y-%m-%d')
    dim_tiempo_df['fecha'] = pd.to_datetime(dim_tiempo_df['fecha'],errors='raise').dt.strftime(date_format='%Y-%m-%d')

    df = pd.merge(dataframe,dim_tiempo_df,left_on="tiempo",right_on="fecha",how='inner')
    return df

def get_dim_ids(db_conn:Engine, dataframe:pd.DataFrame, column_dataframe_name:str, table_name:str, column_table_name:str)->pd.DataFrame:
    dim_df = pd.read_sql(f'SELECT * FROM {table_name};',con=db_conn)
    search_dim_col = f'search_{column_table_name}'
    dim_df[search_dim_col] = dim_df[column_table_name].astype(str).apply(lambda x: Text_Normalization.get_srch_value(text=x))

    id_dim_col = [col for col in dim_df.columns if str(col).startswith('id')][0]
    
    column_df = dataframe.loc[:,[column_dataframe_name]].drop_duplicates()
    search_col = f'search_{column_dataframe_name}'
    column_df[search_col] = column_df[column_dataframe_name].astype(str).apply(lambda x: Text_Normalization.get_srch_value(text=x))
    column_df["possible_replacements"] = column_df[search_col].apply(lambda x: process.extract(x, dim_df[search_dim_col],scorer=fuzz.ratio, limit=3))

    column_df["possible_replacements"] = column_df["possible_replacements"].apply(lambda x: Text_Normalization.filter_possible_replacements(list_posiblilities=x))

    replacements_mask = column_df['possible_replacements'].apply(lambda x: len(x)!=1)

    replacements_df = column_df.loc[replacements_mask].drop_duplicates(subset=column_dataframe_name)
    
    if not replacements_df.empty:
        replacements_df['possible_replacements'] = replacements_df['possible_replacements'].apply(lambda x: [dim_df.loc[index,column_table_name] for index in x if index!=None])
        replacements_df = replacements_df[[column_dataframe_name,'possible_replacements']]

        print('Replaces error')
        print(replacements_df)
        raise ValueError('There\'s a replaces error')
    
    column_df['possible_replacements'] = column_df['possible_replacements'].apply(lambda x: [dim_df.loc[index,id_dim_col] for index in x if index!=None])
    column_df['possible_replacements'] = column_df['possible_replacements'].apply(lambda x: x[0])
    column_df = column_df.rename(columns={'possible_replacements':id_dim_col})
    
    dataframe = dataframe.merge(right=column_df[[id_dim_col,column_dataframe_name]],how='left',on=column_dataframe_name)

    return dataframe    

def add_dim_cols(db_conn:Engine, dataframe:pd.DataFrame,dims:list)->pd.DataFrame:
    for dim in dims:        
        replaces = dim.get('replaces')
        if replaces:
            dataframe[dim['df_col']] = dataframe[dim['df_col']].replace(replaces)
        
        dataframe = get_dim_ids(db_conn=db_conn,dataframe=dataframe, column_dataframe_name=dim['df_col'], table_name=dim['table_name'], column_table_name=dim['table_col'])
    return dataframe

class CurrencyExchange():    
    FORMAT = '%Y-%m-%d'
    def __init__(self,min_date:str):
        self.memory = {}
        self.currency_dataframe = pd.DataFrame()

        db_conn = create_engine(f"postgresql+psycopg2://postgres:datax@10.0.0.12:5432/DATA_DB_BO")
        query = f"SELECT titulo6, titulo7, fecha, unidad_metrica, en_boliviano FROM \"bcb\".\"DATA_D_BO_000000219_01\" WHERE fecha >= \'{min_date}\'"
        self.currency_dataframe = pd.read_sql_query(query, con=db_conn)        
        self.currency_dataframe = self.currency_dataframe[~self.currency_dataframe['titulo7'].str.contains('venta',case=False)]
        if not self.currency_dataframe.empty:
            self.fill_gaps()

    def fill_gaps(self):
        self.currency_dataframe['fecha'] = pd.to_datetime(self.currency_dataframe['fecha'])
        min_date = self.currency_dataframe['fecha'].min()
        max_date = self.currency_dataframe['fecha'].max()

        date_range = pd.date_range(start=min_date, end=max_date, freq='D')
        date_serie = pd.DataFrame({'fecha': date_range,'key':1})

        possible_comb = self.currency_dataframe[['titulo6','unidad_metrica']].drop_duplicates()
        possible_comb['key'] = 1
        date_df = possible_comb.merge(date_serie, on='key')
        
        df_merged = date_df.merge(self.currency_dataframe,how='left',on=['titulo6','unidad_metrica','fecha'])
        df_sorted = df_merged.sort_values(by=['titulo6','unidad_metrica','fecha'],ascending=[True,True,True])
        df_sorted = df_sorted.ffill()

        df_sorted['fecha'] = df_sorted['fecha'].dt.strftime(self.FORMAT)
        self.currency_dataframe = df_sorted
        
    def get_currency_exchange(self,date:str|datetime,currency_from:str,currency_to:str, value:float, format='%Y-%m-%d'):
        if pd.isna(value):
            return value
        date = date if isinstance(date,str) else date.strftime(format)
        if self.currency_dataframe.empty:
            return pd.NA
        from_exchange = 1
        to_exchange = 1
        currency_in_memory = self.memory.get(f'{currency_from}-{currency_to}-{date}')
        if currency_in_memory:
            return round(value * currency_in_memory,2)

        if currency_from != 'BOB':
            currency_from_mask = (
               (self.currency_dataframe['unidad_metrica'] == currency_from) & (self.currency_dataframe['fecha'] == date)
            )
            currency_from_df = self.currency_dataframe.loc[currency_from_mask,'en_boliviano']
            if currency_from_df.empty:
                return pd.NA
            from_exchange = currency_from_df.iloc[0]

        if currency_to != 'BOB':
            currency_to_mask = (
                (self.currency_dataframe['unidad_metrica'] == currency_to) & (self.currency_dataframe['fecha'] == date)
            )
            currency_to_df = self.currency_dataframe.loc[currency_to_mask,'en_boliviano']            
            if currency_to_df.empty:
                return pd.NA
            to_exchange = currency_to_df.iloc[0]
        
        currency_exchange = from_exchange / to_exchange
        self.memory[f'{currency_from}-{currency_to}-{date}'] = currency_exchange

        return round(value * currency_exchange,2)

class TableColumnTypes:
    SQL_TYPE_TO_PANDAS = {
        'INTEGER': pd.Int64Dtype(),
        'BIGINT': pd.Int64Dtype(),
        'SMALLINT': pd.Int64Dtype(),
        'FLOAT': np.float64,
        'REAL': np.float32,
        'NUMERIC': np.float64,
        'DECIMAL': np.float64,
        'BOOLEAN': bool,
        'CHAR': str,
        'VARCHAR': str,
        'TEXT': str,
        'DATE': 'datetime64[ns]',
        'TIMESTAMP': 'datetime64[ns]',
        'TIMESTAMP WITH TIME ZONE': 'datetime64[ns]',
        'TIMESTAMP WITHOUT TIME ZONE': 'datetime64[ns]'
    }

    @staticmethod
    def map_sqlalchemy_type_to_numpy(sql_type_str):
        for key in TableColumnTypes.SQL_TYPE_TO_PANDAS:
            if key in sql_type_str.upper():
                return TableColumnTypes.SQL_TYPE_TO_PANDAS.get(key)
        return object
    
    @staticmethod
    def get_column_types(engine:Engine, schema:str, table_name:str) -> dict:
        inspector = inspect(engine)
        columns_info = inspector.get_columns(table_name, schema=schema)
        return {
            col['name'] : TableColumnTypes.map_sqlalchemy_type_to_numpy(str(col['type'])) for col in columns_info
        }

def get_free_date(db_conn:Engine, frecuency:str, database_code:str, format:str='%Y-%m-%d') -> str:
    frecuency = frecuency.lower().strip()
    free_dict = {
        'diario':200,
        'semanal':100,
        'mensual':12,
        'trimestral':24,
        'semestral':6,
        'anual':2,
    }
    free_values = free_dict.get(frecuency)
    if not free_values:
        raise ValueError(f"Bad base_dates frecuency: {frecuency}")

    dates_query = f"SELECT DISTINCT(tiempo) AS dates FROM \"database\".\"{database_code}\" ORDER BY dates DESC LIMIT {free_values+1}"

    with db_conn.connect() as connection:
        result = connection.execute(dates_query).fetchall()
    
    free_date = result[-1][0]
    free_date:date = free_date.strftime(format)

    return free_date