from models.conversion.Conversion_Base import Conversion_Base
import logging
import os
import re
import pandas as pd
import numpy as np
import traceback
from typing import Tuple, Union, Dict, List
from models.download.tools.download_tools import read_excel
from models.conversion.tools.conversion_tools import format_date,last_day_month,month_abr_to_number, month_to_number,to_numeric_datax

class D_BO_000000483_01(Conversion_Base):

    def extraction(self, file_path , key_words , template_path , page_number, format = "%Y-%m-%d"): 
        """
        Extracts, cleans, and reshapes tabular data from an Excel file into a tidy long format with hierarchical labels and a date reference.

        The function:
        1. Loads and cleans the Excel file (removing empty rows/columns).
        2. Locates the data block using start and end keywords.
        3. Extracts title rows and derives a reference date.
        4. Renames headers using the first row of the data block.
        5. Transposes and reshapes the table into long format.
        6. Creates hierarchical labels: 
            - nv1: top-level group (totals, filled downward).
            - nv2: subcategory (emptied when duplicated inside nv1).
            - hora: time column extracted from headers.
            - valor: numeric values.
        7. Adds the extracted reference date as column `fecha`.
        8. Returns the transformed DataFrame and metadata.

        Parameters:
        - file_path (str): Path to the Excel file.
        - key_words (list[str]): Start and end keywords to locate the data block.
        - template_path (str): Path to a template file (not used here).
        - page_number (int): Page number reference (currently always 1).
        - format (str, optional): Date format string for the extracted date (default "%Y-%m-%d").

        Returns:
        - dict: Metadata containing:
            - "file_name": processed file name.
            - "titles": extracted titles above the data block.
            - "page_number": page reference.
        - pd.DataFrame: columns ['nv1','nv2','hora','valor','fecha'].

        Raises:
        - Exception: If any error occurs, prints traceback and returns empty outputs.
    """

  
        # Extract the file name from the given file path
        file_name = os.path.basename(file_path)

        # Regex pattern to capture month (in text) and year from titles
        re_date = r'\b((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\b\D*\b(\d{4})\b'

        try:
            #Split keywords
            if isinstance(key_words, str):
                key_words = key_words.split()
            elif not isinstance(key_words, (list, tuple)):
                raise ValueError("key_words debe ser una cadena o lista de palabras clave.")
            
            # Load the Excel file and drop fully empty rows and columns
            df = read_excel(file_name=file_path)
            df = df.dropna(how='all').dropna(axis=1,how='all').reset_index(drop=True)
            
            
            # Find the index of the row where the data block starts and the data block ends (based on keyword)
            start_idx = df[df[0].astype(str).str.contains(key_words[0], case=False, na=False)].index[0]
            end_idx = df[df[0].astype(str).str.contains(key_words[1], case=False, na=False)].index[1]-1
            
            # Extract title rows (above the data block) and clean extra spaces
            titles = [ re.sub(r"\s+", " ", "".join(str(x) for x in row if pd.notna(x))).strip() 
                    for _, row in df.loc[:start_idx-1].iterrows() 
                    if any(pd.notna(row))]
            
            # Trim the DataFrame to the actual data block
            df= df.loc[start_idx:end_idx]
           

            # Extract date from file_name (YYYY-MM-DD) or titles
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", file_name)
            if date_match:
                formated_date = format_date(date_match.group(1))
            else:
                title_day_match = [m.groups() for title in titles if (m := re.search(r'(\d{1,2})\s+de\s+([a-zA-Z]+)\s+de\s+(\d{4})', title, re.IGNORECASE))]
                if title_day_match:
                    d, m, y = title_day_match[0]
                    month_num = month_to_number(month=m) or month_abr_to_number(month=m)
                    formated_date = format_date(f'{y}-{month_num:02d}-{int(d):02d}')
                else:
                    date = [dm.group(1, 2) for title in titles if (dm := re.search(re_date, title, re.IGNORECASE))][0]
                    year = int(date[1])
                    month = month_to_number(month=date[0]) or month_abr_to_number(month=date[0])
                    formated_date = format_date(f'{year}-{month:02d}-01')
            
            
            # # Rename Headers and Reset index rows
            df = df.iloc[0:].reset_index(drop=True)
            df.columns = range(df.shape[1])
            
            # # Transpose rows and columns to restructure the DataFrame
            df=df.transpose()
             # Rename headers from first row and reset index
            headers = df.iloc[0].astype(str).str.strip().tolist()
            df = df.iloc[1:].reset_index(drop=True)
            df.columns = headers
            
            # # Reshape DataFrame into long (tidy) format
            df_melted = df.melt(id_vars=["HORA"], value_vars=df.columns[1: ],var_name="nv2",value_name="valor")
                       
            # # Identify rows that correspond to totals (top-level grouping)
            bancos_nv1_mask = df_melted['nv2'].astype(str).str.contains(r'total',case=False, regex=True)
            
            # # Insert 'bancos_nv1' for top-level groups and 'nv1' for intermediate hierarchy
            df_melted.insert(0, column='nv1', value= df_melted.loc[bancos_nv1_mask, 'nv2'])
            
            # If nv2 appear in nv1 → delete, else keep 
            df_melted['nv2'] = np.where(df_melted.apply(lambda row: row['nv2'] in str(row['nv1']), axis=1), None, df_melted['nv2'])
   
            # # Forward fill 'bancos_nv1' values downwards
            df_melted['nv1'] = df_melted['nv1'].bfill()
            df_melted = df_melted.rename(columns={"HORA": "hora"})
            
            df_melted = df_melted[["nv1","nv2","hora","valor"]]
            
            # Add the extracted date as a new column in the final DataFrame
            df_melted.insert(len(df_melted.columns) - 1,column="fecha",value=formated_date.strftime(format))		
            	
            
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
        Verify that the sum of the previous data up to the data at the height of 'TOTAL', 
        minus the data at the same height of TOTAL, is within the tolerance.

        Args:
            dataframe (pd.DataFrame): DataFrame with columns ['banco_nv1',...].
            decimal_separator (str): Decimal separator used in numeric values ('.' or ',').
            TOLERANCE (float): Maximum allowed difference between the calculated and reported totals.

        Returns:
            bool: True if any validation errors are found, False if everything is correct.
        """
        try:
            df = dataframe.copy()
            
            # Safe conversion of "valor" column to numeric
            df["valor"] = to_numeric_datax(serie=df["valor"],decimal_separator=decimal_separator)

            # Detect positions where "T O T A L" appears in 'nv1'
            total_mask = df["hora"].astype(str).str.contains(r'\bTOTAL\b', case=False, regex=True)
            total_positions = df.index[total_mask].tolist()

            # Create empty DataFrame to store validation results
            results = pd.DataFrame(columns=["TOTALES", "SUMATORIA", "DIFERENCIA"])

            prev_pos = None
            for i, pos in enumerate(total_positions):
                # Define the start of the block (after previous TOTAL or beginning of DataFrame)
                start_pos = (prev_pos + 1) if prev_pos is not None else 0
                total_val = df.loc[pos, "valor"]

                # Sum all values in the block above the TOTAL
                if pos - 1 >= start_pos:
                    sumatoria = df.loc[start_pos:pos - 1, "valor"].sum(skipna=True)
                else:
                    sumatoria = 0.0

                diferencia = sumatoria - total_val

                # Save validation result for this TOTAL
                results.loc[i] = [total_val, sumatoria, diferencia]
                prev_pos = pos 
            # Check if any differences exceed the allowed tolerance
            return (results["DIFERENCIA"].abs() > TOLERANCE).any()

        except:
    
            return True

Executor_D_BO_000000483_01 = D_BO_000000483_01
Robot = D_BO_000000483_01
