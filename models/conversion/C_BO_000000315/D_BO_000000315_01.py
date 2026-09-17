from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import traceback
import pandas as pd
import numpy as np

class D_BO_000000315_01(Conversion_Base):
    """
    Type III Conversion Robot for Ticket D_BO_000000315_01.
    Processes "Bmu-financiamiento de Entidades del Exterior", transforming 
    the table into a strict vertical (melted) structure following DATAX rules.
    """

    def extraction(
        self, 
        file_path: str, 
        key_words: str, 
        template_path: str, 
        page_number: int, 
        format_str: str = '%Y-%m-%d'
    ) -> tuple:
        """
        Reads the Excel file, dynamically locates the headers and date,
        extracts the banks data, and melts it into nv1, nv2, fecha, valor.
        """
        try:
            # 1. Read the raw Excel file
            df_raw = pd.read_excel(file_path, header=None)

            # 2. Extract Date dynamically from the text
            fecha = pd.Timestamp.now().strftime(format_str) # Default fallback
            months = {
                "ENERO": "01", "FEBRERO": "02", "MARZO": "03", "ABRIL": "04", 
                "MAYO": "05", "JUNIO": "06", "JULIO": "07", "AGOSTO": "08", 
                "SEPTIEMBRE": "09", "OCTUBRE": "10", "NOVIEMBRE": "11", "DICIEMBRE": "12"
            }
            
            # Scan top rows for the date string "AL DD DE MMM DE YYYY"
            for i in range(min(10, len(df_raw))):
                val = str(df_raw.iloc[i, 0]).upper()
                if "AL " in val and " DE " in val:
                    match = re.search(r'AL\s+(\d+)\s+DE\s+([A-Z]+)\s+DE\s+(\d+)', val)
                    if match:
                        day = match.group(1).zfill(2)
                        month = months.get(match.group(2), "01")
                        year = match.group(3)
                        # Construct valid datetime string
                        parsed_date = pd.to_datetime(f"{year}-{month}-{day}")
                        fecha = parsed_date.strftime(format_str)
                        break

            # 3. Locate the Headers row dynamically
            header_row_idx = -1
            for i in range(min(15, len(df_raw))):
                row_str = " ".join(df_raw.iloc[i].astype(str).str.upper())
                if "CORTO PLAZO" in row_str and "MEDIANO PLAZO" in row_str:
                    header_row_idx = i
                    break
                    
            if header_row_idx == -1:
                raise ValueError("Could not locate the table headers (CORTO PLAZO, MEDIANO PLAZO).")
                
            # Extract valid header names, skipping empty ones
            raw_headers = df_raw.iloc[header_row_idx].tolist()
            headers = [str(h).strip() for h in raw_headers if pd.notna(h) and str(h).strip() != '']
            
            # Sometimes 'BANCOS' is in the header row, sometimes not. Skip if present.
            if headers[0].upper() == "BANCOS":
                headers = headers[1:] 

            # Identify the actual column indices for these headers
            col_indices = []
            for j in range(len(df_raw.columns)):
                val = str(df_raw.iloc[header_row_idx, j]).strip()
                if val in headers:
                    col_indices.append(j)
                    
            # Keep column 0 (Banks) plus the data columns
            cols_to_keep = [0] + col_indices

            # 4. Find the start and end of the data rows
            start_idx = header_row_idx + 1
            end_idx = start_idx
            for i in range(start_idx, len(df_raw)):
                val = str(df_raw.iloc[i, 0]).strip().upper()
                # Stop when hitting totals, participation, empty rows, or NaN
                if "TOTAL" in val or "PARTICIPACIÓN" in val or val == "NAN" or val == "":
                    end_idx = i
                    break
                    
            # 5. Build the clean DataFrame
            df_data = df_raw.iloc[start_idx:end_idx, cols_to_keep].copy()
            df_data.columns = ['nv1'] + headers
            
            # Clean Bank Names (nv1)
            df_data['nv1'] = df_data['nv1'].astype(str).str.strip()
            
            # 6. Melt into DATAX format
            df_melted = pd.melt(df_data, id_vars=['nv1'], var_name='nv2', value_name='valor')
            df_melted['fecha'] = fecha
            
            # Enforce strict column order for this specific ticket
            df_melted = df_melted[['nv1', 'nv2', 'fecha', 'valor']]
            
            # Enforce numeric data and drop missing rows (Airflow standard applied)
            df_melted['valor'] = pd.to_numeric(df_melted['valor'], errors='coerce')
            df_melted = df_melted.dropna(subset=['valor'])

            # 7. Metadata Dictionary
            file_name = os.path.basename(file_path)
            metadata_dict = {
                "file_name": file_name,
                "titles": ["Financiamiento de Entidades del Exterior"],
                "page_number": page_number
            }

            return metadata_dict, df_melted

        except Exception as error:
            print(f"Could not extract report from {file_path}: {error}")
            traceback.print_exc()
            return "", pd.DataFrame()

    def validate_data_results(
        self, 
        dataframe: pd.DataFrame, 
        decimal_separator: str, 
        TOLERANCE: float = 6.0
    ) -> bool:
        """
        Validates the integrity of extracted numerical data.
        Returns False as there are no printed totals to validate strictly.
        """
        try:
            return False
        except Exception as error:
            print(f"Validation error: {error}")
            traceback.print_exc()
            return True

Executor_D_BO_000000315_01 = D_BO_000000315_01
Robot = D_BO_000000315_01
