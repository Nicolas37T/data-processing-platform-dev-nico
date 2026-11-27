from models.conversion.Conversion_Base import Conversion_Base
import logging
import os
import re
import pandas as pd
import numpy as np
import traceback
from typing import Tuple, Union, Dict, List
from models.download.tools.download_tools import read_excel
from models.conversion.tools.conversion_tools import format_date,last_day_month,month_abr_to_number, month_to_number

class D_BO_000000488_01(Conversion_Base):

    def extraction(self, file_path , key_words , template_path , page_number, format = "%Y-%m-%d"): 
      
        """
            This function readsand extracts a specific table
            based on given keywords. It works in the following way:

            1. Opens the Excel file and removes completely empty rows and columns.  
            2. Uses the first keyword to locate where the data block begins,
                and the second keyword to identify where it ends.  
            3. Collects the titles that appear above the table (report headers).  
            4. Searches the titles to detect the report date (day, month, year).  
            5. Cuts the DataFrame to keep only the relevant table rows.  
            6. Renames the headers, converts them to lowercase, and adjusts column names.  
            7. Adds the detected date as a new column called 'fecha'.  
            8. Adds an extra column called 'valor' with constant value 1 (for validation use).  

            At the end, it returns:
            - Metadata with the file name, titles, and page number.  
            - The cleaned DataFrame with the extracted table.  

            If something fails during the process, it returns an empty string.
        """

        # Extract the file name from the given file path
        file_name = os.path.basename(file_path)
        
        # Regex pattern to capture month (in text) and year from titles
        re_date = r'\b((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\b\D*\b(\d{4})\b'

        try:
            #Split keywrods
            if isinstance(key_words, str):
                key_words = key_words.split()
            elif not isinstance(key_words, (list, tuple)):
                raise ValueError("key_words debe ser una cadena o lista de palabras clave.")
            
            # Load the Excel file and remove fully empty rows and columns
            df = read_excel(file_name=file_path)
            df = df.dropna(how='all').dropna(axis=1,how='all').reset_index(drop=True)
            
            # Find the index of the row where the data block starts and the data block ends (based on keyword)
            start_idx = df[df[0].astype(str).str.contains(key_words[0], case=False, na=False)].index[1]
            end_idx = df[df[0].astype(str).str.contains(key_words[1], case=False, na=False)].index[0]-1
            
            # Extract title rows (above the data block) and clean extra spaces
            titles = [ re.sub(r"\s+", " ", "".join(str(x) for x in row if pd.notna(x))).strip() 
                    for _, row in df.loc[:start_idx-1].iterrows() 
                    if any(pd.notna(row))]
            
             # Extract and format the date found in the titles
            date = [date_match.group(1,2) for title in titles if (date_match:= re.search(re_date,title, re.IGNORECASE))][0]                
            year = int(date[1])
            month = month_conv if(month_conv:=month_to_number(month=date[0])) else month_abr_to_number(date=[0])
            day = next((int(m.group(1)) for title in titles if (m := re.search(r'(\d{1,2})\D+\s*', title))),31)
            formated_date = format_date(f'{year}-{month}-{day}')
            
            # Trim the DataFrame to the actual data block
            df_melted = df.loc[start_idx:end_idx]
            
            # Rename Headers and Reset index rows
            header = df_melted.iloc[0].fillna("").astype(str).tolist()
            df_melted = df_melted.iloc[1:].reset_index(drop=True)
            df_melted.columns = header
            df_melted.columns = df_melted.columns.str.lower()
            
            df_melted = df_melted.rename(columns={"unidad o componente":"componente"})
           
            # Add the extracted date as a new column in the final DataFrame
            df_melted.insert(len(df_melted.columns), column="fecha",value=formated_date.strftime(format))		
          
            # Add the column valor with constant 1
            df_melted.insert(len(df_melted.columns), column="valor",value=1)
        
            return (
                {
                    "file_name": file_name,
                    "titles": titles,
                    "page_number":1
                },df_melted)

        except Exception as e:
            print(f"An error ocurred: {e}")            
            traceback.print_exc()
        return ""
    def validate_data_results(self, dataframe: pd.DataFrame, decimal_separator: str, TOLERANCE: float = 6.0):
        """
        No way to validate this report (no numerical data).
        """
        try:
            return False
        except:
            return True

Executor_D_BO_000000488_01 = D_BO_000000488_01
Robot = D_BO_000000488_01
