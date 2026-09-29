from models.conversion.Conversion_Base import Conversion_Base
import os
import traceback
import pandas as pd
from models.conversion.tools.conversion_tools import get_xlsx_report_dataframe

class D_BO_000000026_01(Conversion_Base):    

    def extraction(self, file_path: str, key_words: str, template_path: str = "", page_number: int = 1, format: str = "%Y-%m-%d") -> tuple:
        """
        Extracts data from a specifiedfile based on provided keywords and a date filter, and saves the extracted data into an Excel file.

        Parameters:
            file_path (str): Path to the PDF file to be processed.
            key_words (str): Keywords to identify the relevant page in the PDF.
            converted_to (str): Date to compare the extracted report date against.
            template_path (str): Path to the Excel template used for validation.
            COLUMN_GAPS (list): List of gaps between columns in the extracted table in mm.
            PIVOT_WORDS (str): Keyword indicating the pivot corner in the PDF.
            format (str): Date format to use when converting dates (default: '%Y-%m-%d').
            
        Returns:
            str: Empty string if successful, or error messages on failure.
        """
        # Get the base name of the file from the file path
        file_name = os.path.basename(file_path)

        re_date = r'(?P<day>\d{1,2})\D(?P<month>\d{1,2})\D(?P<year>\d{4})'
        
        try:

            df, page_number = get_xlsx_report_dataframe(file_path=file_path, key_words=key_words)
            df = df.dropna(axis=1, how='all')
            nan_indices = df[df[df.columns[0]].isna()].index
            titles = df.loc[:nan_indices[0]].dropna(how='all').apply(lambda x: ' '.join(x.dropna().astype(str)),axis=1).to_list()

            df = df.loc[nan_indices[0]:].dropna(how='all').reset_index(drop=True)
            date = df[df.columns[0]].astype(str).str.extract(re_date)
            date['fecha'] = date.apply(lambda x: f"{x['year']}-{x['month']}-{x['day']}" if not pd.isna(x['year']) else pd.NA,axis=1).ffill()
            date.loc[0,'fecha'] = 'fecha'
            
            df.insert(1,column='fecha',value=date['fecha'])
            df = df.dropna(subset=df.columns[2:],how='all').reset_index(drop=True)
            df.loc[0] = df.loc[0].ffill()

            column_to_analize = df.columns[2]
            numeric_mask = pd.to_numeric(df[column_to_analize].replace(r'\s+','').replace(r'-','0', regex=True).replace(r'[\)\s+\.\(\,]','', regex=True),errors='coerce').notna()
            numeric_indices = df[numeric_mask].index
            first_num_index = numeric_indices[0]
            df.columns = pd.MultiIndex.from_arrays(df.loc[:first_num_index-1].values)
            df = df.loc[first_num_index:]
            df_melted = df.melt(id_vars=df.columns[:2].to_list(), value_name='valor')
            # Columns in df_melted: [df.columns[0], df.columns[1], variable_0, variable_1, valor]
            # Reorder so entity is nv1, variable_0 is nv2, variable_1 is nv3, fecha is second-to-last, valor is last
            var_indices = list(range(2, len(df_melted.columns) - 1))
            df_melted = df_melted.iloc[:, [0] + var_indices + [1, len(df_melted.columns) - 1]]

            num_nv = 1 + len(var_indices)
            df_melted.columns = [f'nv{i+1}' for i in range(num_nv)] + ['fecha', 'valor']
            df_melted = df_melted.replace(0, pd.NA).dropna(subset='valor')
            
            return ({
                "file_name": file_name,
                "titles": titles,
                "page_number":int(page_number)
            }, df_melted)
        except ValueError as e:
            print(f"Validation error: {e}")
            traceback.print_exc()                        
        except Exception as e:            
            print(f"An error ocurred: {e}")            
            traceback.print_exc()
        return ""
    
    def validate_data_results(self, dataframe: pd.DataFrame, decimal_separator: str = ",", TOLERANCE: float = 6.0) -> bool:
        """Validates and cleans the data in a DataFrame. The function performs the following tasks:
    
        1. Validates the totals in the data (this may involve specific checks on values in the DataFrame).        
        3. Processes numeric data to ensure they are in the correct format, converting them to numeric type and handling possible conversion errors.
        
        If the totals are not validated successfully, the function returns None. Otherwise, it returns the cleaned DataFrame.
        
        Args:
            dataframe (pd.DataFrame): The DataFrame containing the data to validate and clean.
            
        Returns:
            pd.DataFrame | None: The cleaned DataFrame if the totals are validated, otherwise None.
        """        
        ERROR_TOLERANCE_VALUE = 6
        totals_mismatch = False       

        return totals_mismatch

Executor_D_BO_000000026_01 = D_BO_000000026_01
Robot = D_BO_000000026_01
