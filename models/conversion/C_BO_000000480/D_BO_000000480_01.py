from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import pandas as pd
import numpy as np
import traceback

from models.download.tools.download_tools import read_excel
from models.conversion.tools.conversion_tools import to_numeric_datax,get_col_date

class D_BO_000000480_01(Conversion_Base):

    def extraction(self, file_path , key_words , template_path , page_number, format = "%Y-%m-%d"): 
        """
                Extracts and cleans a table structured by days, months, and years from an Excel file, 
                then reshapes it into a tidy long format with parsed dates.

                The function:
                - Loads the Excel file and removes empty rows/columns.
                - Locates the data block using start and end keywords.
                - Normalizes the header rows (years and months) to create column labels like "YYYY-MMM".
                - Converts the table into long format with columns:
                    * nv1: category marker (e.g., "Max." values).
                    * fecha: parsed date (Día + Mes + Año) formatted as YYYY-MM-DD.
                    * valor: numeric value.
                - Cleans the fecha column (removes parentheses, extra spaces, coerces to datetime).

                Returns:
                - dict: Metadata with file name, extracted titles, and page number.
                - pd.DataFrame: Tidy table with ['nv1','fecha','valor'].
            """  
    

        # Extract the file name from the given file path
        file_name = os.path.basename(file_path)
        
        try:
            # Slip keywords
            if isinstance(key_words, str):
                key_words = key_words.split()
            elif not isinstance(key_words, (list, tuple)):
                raise ValueError("key_words debe ser una cadena o lista de palabras clave.")
            
            
            # Load the Excel file and remove fully empty rows and columns
            df = read_excel(file_name=file_path)
            df.loc[0, 1] = df.loc[0, 0]  
            df.loc[0, 0] = np.nan   
            df = df.dropna(how='all').dropna(axis=1,how='all').reset_index(drop=True)
            
            # Find the index of the row where the data block starts and the data block ends (based on keyword)
            start_idx = df[df[1].astype(str).str.contains(key_words[0], case=False, na=False)].index[0]+1
            end_idx = df[df[1].astype(str).str.contains(key_words[1], case=False, na=False)].index[0]-1
            
            # Extract title rows (above the data block) and clean extra spaces
            titles = [ re.sub(r"\s+", " ", "".join(str(x) for x in row if pd.notna(x))).strip() 
                    for _, row in df.loc[:start_idx-1].iterrows() 
                    if any(pd.notna(row))]
            
        
            # # Trim the DataFrame to the actual data block
            df_melted = df.loc[start_idx:end_idx]
            
            # # Rename Headers and Reset index rows
            df_melted = df_melted.iloc[0:].reset_index(drop=True)
            df_melted.columns = range(df_melted.shape[1])
            
            
            # Clean and normalize the "years" row
            years = df_melted.iloc[0].copy()
            years = years.ffill(axis=0).infer_objects()
            years = years.ffill().astype("Int64")
            df_melted.iloc[0] = years
    
            
             # Build new column headers using years and months
            years = df_melted.iloc[0].ffill().astype(str).tolist()
            months = df_melted.iloc[1].tolist()
            new_cols = ["Día" if m == "Día" else f"{y}-{m}" for y, m in zip(years, months)]
            df_melted.columns = new_cols

            # Remove duplicated header rows
            df_melted = df_melted.drop([0, 1]).reset_index(drop=True)
            
            df_melted = pd.melt(df_melted,id_vars=["Día"],var_name="fecha",value_name="valor")
            df_melted = df_melted.dropna(subset=["valor"])
            df_melted['nv1'] = np.where(df_melted['Día'].str.contains(r'\bMax\.', regex=True,na=False),df_melted['Día'],None)
           
            condition = df_melted['Día'].str.contains(r'\bMax\.', regex=True, na=False)
            
             # Replace only those rows where the condition is met ("Total")
            # with the previous value in the same column
            df_melted.loc[condition, 'Día'] = df_melted['Día'].shift(1)
            df_melted["fecha"] = df_melted["Día"].astype(str) + "-" + df_melted["fecha"]
            df_melted = df_melted.drop(columns=["Día"])

            # Remove any text in parentheses from "fecha" and strip extra spaces
            df_melted['fecha'] = df_melted['fecha'].str.replace(r'\(.*?\)', '', regex=True).str.strip()
            
            #Parse: D-YYYY-Mes  → YYYY-MM-DD
            df_melted['fecha'] = df_melted['fecha'].astype(str).apply(get_col_date)
            
            # Convert "fecha" to datetime and format it according to the given pattern
            df_melted['fecha'] = pd.to_datetime(df_melted['fecha'], errors='coerce').dt.strftime(format)
            df_melted = df_melted[["nv1","fecha","valor"]]
            
    
           
        
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
        Verify that the maximum of the previous data up to the row labeled 'Max.' (or 'Max.')
        minus the reported value at the same row is within the tolerance.

        Args:
            dataframe (pd.DataFrame): DataFrame with columns ['nv1',...].
            decimal_separator (str): Decimal separator used in numeric values ('.' or ',').
            TOLERANCE (float): Maximum allowed difference between the calculated and reported maximum.

        Returns:
            bool: True if any validation errors are found, False if everything is correct.
        """
        try:
            df = dataframe.copy()

            # Safe conversion of "valor" column to numeric
            df["valor"] = to_numeric_datax(serie=df["valor"], decimal_separator=decimal_separator)

            # Detect positions where "Total" (or "Max.") appears in 'nv1'
            total_mask = df["nv1"].astype(str).str.contains(r'\bMax\.', case=False, regex=True)
            total_positions = df.index[total_mask].tolist()
           

            # Create empty DataFrame to store validation results
            results = pd.DataFrame(columns=["Max", "MAXIMO ENCONTRADO", "DIFERENCIA"])

            prev_pos = None
            for i, pos in enumerate(total_positions):
                # Define the start of the block (after previous TOTAL or beginning of DataFrame)
                start_pos = (prev_pos + 1) if prev_pos is not None else 0
                total_val = df.loc[pos, "valor"]

                # Take the maximum of the block above the TOTAL
                if pos - 1 >= start_pos:
                    maximo = df.loc[start_pos:pos - 1, "valor"].max(skipna=True)
                else:
                    maximo = np.nan

                diferencia = maximo - total_val

                # Save validation result for this TOTAL
                results.loc[i] = [total_val, maximo, diferencia]
                prev_pos = pos
                    
    

            # Check if any differences exceed the allowed tolerance
            return (results["DIFERENCIA"].abs() > TOLERANCE).any()

        except Exception:
            import traceback; traceback.print_exc()
            return True

Executor_D_BO_000000480_01 = D_BO_000000480_01
Robot = D_BO_000000480_01
