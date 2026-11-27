from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import traceback
import calendar
import pandas as pd
import numpy as np
import unicodedata

from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000300_01(Conversion_Base):
    """
    Conversion robot for D_BO_000000300_01: Bmu-ranking de Depositos del Publico y de Empresas Publicas.
    Extracts tabular data, flattening it to a normalized format without hardcoding.
    """

    def extraction(self, file_path: str, key_words: str = "", template_path: str = "", page_number: int = 1, format: str = "%Y-%m-%d") -> tuple:
        """
        Locates and extracts the specific table from the Excel file.
        Returns a tuple containing metadata dictionary and the flattened pandas DataFrame.
        """
        try:
            df_raw = pd.read_excel(file_path, header=None)
            
            metadata_dict = {
                "file_name": os.path.basename(file_path),
                "titles": [],
                "page_number": int(page_number)
            }
            
            header_row_dates = -1
            header_row_metrics = -1
            
            # Identify the row containing temporal headers (e.g., 'DIC-20')
            date_pattern = re.compile(r"^(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)-(\d{2})$", re.IGNORECASE)
            
            month_map = {
                "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
                "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12
            }
            
            # Locate the exact rows for dates and metric definitions
            for idx, row in df_raw.iterrows():
                for col_idx, cell in enumerate(row):
                    if pd.notna(cell) and isinstance(cell, str):
                        match = date_pattern.search(cell.strip())
                        if match:
                            header_row_dates = idx
                            break
                if header_row_dates != -1:
                    header_row_metrics = header_row_dates + 1
                    break
                    
            if header_row_dates == -1:
                raise ValueError("Could not find the date headers row.")
                
            # Extract main titles for metadata (strictly rows before the table headers)
            for i in range(header_row_dates):
                row_vals = []
                for val in df_raw.iloc[i]:
                    if pd.notna(val) and isinstance(val, str) and val.strip():
                        val_str = val.strip()
                        # Avoid duplicates in merged cells and exclude date headers
                        if val_str not in row_vals and not date_pattern.search(val_str):
                            row_vals.append(val_str)
                if row_vals:
                    metadata_dict["titles"].append(" ".join(row_vals))
            
            # Validate key_words presence
            if key_words:
                text_block = " ".join(metadata_dict["titles"]).lower()
                for i in range(min(10, len(df_raw))):
                    for val in df_raw.iloc[i]:
                        if pd.notna(val) and isinstance(val, str):
                            text_block += " " + val.lower()
                
                # Normalize accents for robust comparison
                normalized_text = unicodedata.normalize('NFKD', text_block).encode('ASCII', 'ignore').decode('utf-8')
                normalized_keywords = unicodedata.normalize('NFKD', key_words.lower()).encode('ASCII', 'ignore').decode('utf-8')
                
                if not all(kw.strip() in normalized_text for kw in normalized_keywords.split()):
                    raise ValueError(f"Key words '{key_words}' not found in the document.")
            
            date_columns = {}
            metric_columns = {}
                
            # Parse dates and map them to column indices
            for col_idx in range(2, len(df_raw.columns)):
                cell = df_raw.iloc[header_row_dates, col_idx]
                if pd.notna(cell) and isinstance(cell, str):
                    match = date_pattern.search(cell.strip())
                    if match:
                        month_str = match.group(1).upper()
                        year_str = match.group(2)
                        month_int = month_map.get(month_str, 12)
                        year_int = 2000 + int(year_str)
                        last_day = calendar.monthrange(year_int, month_int)[1]
                        parsed_date = f"{year_int}-{month_int:02d}-{last_day:02d}"
                        
                        # Span the date across the 3 corresponding metric columns
                        date_columns[col_idx] = parsed_date
                        date_columns[col_idx + 1] = parsed_date
                        date_columns[col_idx + 2] = parsed_date
                        
            # Parse sub-headers (metrics like 'DEPOSITOS', '% DE PARTICIP.', 'LUGAR RANKING')
            for col_idx in range(2, len(df_raw.columns)):
                if col_idx in date_columns:
                    cell = df_raw.iloc[header_row_metrics, col_idx]
                    if pd.notna(cell) and isinstance(cell, str):
                        metric_columns[col_idx] = cell.strip()
                        
            data = []
            current_nv1 = None
            
            start_data_row = header_row_metrics + 1
            for idx in range(start_data_row, len(df_raw)):
                entity_col = df_raw.iloc[idx, 1]
                
                # Skip empty rows based on entity description
                if pd.isna(entity_col) or str(entity_col).strip() == "":
                    continue
                    
                entity_val = str(entity_col).strip()
                
                # Prevent double counting: skip main total rows
                if "TOTAL" in entity_val.upper() and entity_val.upper() != "SUB-TOTAL":
                    continue
                
                # State machine: Identify section headers (nv1)
                # A row is a section header if it has no valid numeric data in metric columns
                has_numeric = False
                for col_idx in metric_columns.keys():
                    if col_idx < len(df_raw.columns):
                        raw_cell = df_raw.iloc[idx, col_idx]
                        if pd.notna(raw_cell):
                            val_str = str(raw_cell).strip().upper()
                            if val_str and val_str not in ["-", "---", "NAN", "NULL", "NONE"]:
                                has_numeric = True
                                break
                
                if not has_numeric:
                    current_nv1 = entity_val
                    continue
                    
                current_nv2 = entity_val
                
                # Extract horizontal data for each metric and date
                for col_idx, metric in metric_columns.items():
                    if col_idx >= len(df_raw.columns):
                        continue
                        
                    raw_val = df_raw.iloc[idx, col_idx]
                    
                    if pd.isna(raw_val) or str(raw_val).strip() in ["", "---", "-"]:
                        continue
                        
                    date_str = date_columns.get(col_idx)
                    if not date_str:
                        continue
                        
                    data.append({
                        "nv1": current_nv1,
                        "nv2": current_nv2,
                        "nv3": metric,
                        "fecha": date_str,
                        "valor": raw_val
                    })
                    
            df_melted = pd.DataFrame(data)
            
            if not df_melted.empty:
                if "nv4" in df_melted.columns:
                    df_melted = df_melted.drop(columns=["nv4"])
                    
                df_melted = df_melted[["nv1", "nv2", "nv3", "fecha", "valor"]]
                
                # Isolate strings and apply to_numeric_datax only to them
                is_str = df_melted["valor"].apply(lambda x: isinstance(x, str))
                if is_str.any():
                    df_melted.loc[is_str, "valor"] = to_numeric_datax(df_melted.loc[is_str, "valor"], decimal_separator=",")
                
                # Force everything to numeric to clear invalid data and unify types
                df_melted["valor"] = pd.to_numeric(df_melted["valor"], errors='coerce')
                
                # Drop rows that became NaN after conversion
                df_melted = df_melted.dropna(subset=["valor"])
                
                # Apply positional formatting
                df_melted["valor"] = df_melted["valor"].apply(
                    lambda x: np.format_float_positional(x, trim='-') if pd.notna(x) else x
                )
            else:
                df_melted = pd.DataFrame(columns=["nv1", "nv2", "nv3", "fecha", "valor"])

            return metadata_dict, df_melted

        except Exception as error:
            print(f"Could not extract report from {file_path}: {error}")
            traceback.print_exc()
            return ""

    def validate_data_results(self, dataframe: pd.DataFrame, decimal_separator: str = ",", TOLERANCE: float = 6.0) -> bool:
        """
        Validates mathematical consistency of the extracted data.
        Returns False if validation passes, True if there are discrepancies.
        """
        try:
            if dataframe.empty:
                return False
                
            df_val = dataframe.copy()
            df_val["valor"] = df_val["valor"].astype(str).str.replace(decimal_separator, ".")
            df_val["valor"] = pd.to_numeric(df_val["valor"], errors='coerce').fillna(0.0)
            
            has_error = False
            
            dates = df_val["fecha"].unique()
            metrics = df_val["nv3"].unique()
            
            for date_str in dates:
                for metric in metrics:
                    # Ranks and percentages cannot be mathematically summed
                    if "RANKING" in str(metric).upper() or "%" in str(metric).upper():
                        continue
                        
                    df_filtered = df_val[(df_val["fecha"] == date_str) & (df_val["nv3"] == metric)]
                    
                    for nv1 in df_filtered["nv1"].unique():
                        df_nv1 = df_filtered[df_filtered["nv1"] == nv1]
                        
                        sub_total_row = df_nv1[df_nv1["nv2"].str.upper() == "SUB-TOTAL"]
                        if not sub_total_row.empty:
                            sub_total_val = sub_total_row["valor"].sum()
                            
                            banks_sum = df_nv1[df_nv1["nv2"].str.upper() != "SUB-TOTAL"]["valor"].sum()
                            
                            if abs(sub_total_val - banks_sum) > TOLERANCE:
                                print(f"Validation error in {nv1} on {date_str} for {metric}: SUB-TOTAL {sub_total_val} != Sum of banks {banks_sum}")
                                has_error = True

            return has_error

        except Exception as error:
            print(f"Validation error: {error}")
            traceback.print_exc()
            return True

Executor_D_BO_000000300_01 = D_BO_000000300_01
Robot = D_BO_000000300_01
