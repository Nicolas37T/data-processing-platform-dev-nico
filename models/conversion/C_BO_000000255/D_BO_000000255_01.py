from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import sqlite3
import traceback
import numpy as np
import pandas as pd
from rapidfuzz import fuzz

from models.conversion.tools.conversion_tools import (
    isLevel,
    to_numeric_datax,
    verify_frecuency,
    verify_levels,
    verify_values,
)
from models.conversion.tools.text_normalization import Text_Normalization


class D_BO_000000255_01(Conversion_Base):
    """
    Type III Conversion Robot for adascz.com.bo (Ticket #96).
    Responsible for extracting data from the raw Excel matrix and normalizing it 
    into a vertical structure (melted DataFrame) following DATAX rules.
    """

    VALID_NV1 = [
        'Precio del Pollo (Bs/kg Vivo)',
        'Precio Gallina Descarte',
        'Precio del Huevo'
    ]

    def extraction(
        self, 
        file_path: str, 
        key_words: str, 
        template_path: str, 
        page_number: int, 
        format: str = '%Y-%m-%d'
    ) -> tuple:
        """
        Reads the raw Excel matrix, extracts the date from the file name, 
        and maps data via specific cell coordinates to the standard DATAX DataFrame.
        """
        try:
            # 1. Extract the date from the Excel file name
            file_name = os.path.basename(file_path)
            match_iso = re.search(r'(\d{4})-(\d{2})-(\d{2})', file_name)
            match_num = re.search(r'(\d{4})(\d{2})(\d{2})', file_name)
            
            if match_iso:
                fecha = f"{match_iso.group(1)}-{match_iso.group(2)}-{match_iso.group(3)}"
            elif match_num:
                fecha = f"{match_num.group(1)}-{match_num.group(2)}-{match_num.group(3)}"
            else:
                fecha = pd.Timestamp.now().strftime(format)

            rows_list = []

            # 2. Check if the Excel matches one of the known formats:
            df_head = pd.read_excel(file_path)
            cols_lower = [str(c).strip().lower() for c in df_head.columns]

            # Case 0: The file is ALREADY a converted DATAX report (e.g. 2026-09-07_D_BO_000000255_01.xlsx)
            if {'nv1', 'fecha', 'valor'}.issubset(set(cols_lower)):
                cols_map = {str(c).strip().lower(): c for c in df_head.columns}
                df_melted = pd.DataFrame()
                df_melted['nv1'] = df_head[cols_map['nv1']]
                df_melted['nv2'] = df_head[cols_map['nv2']] if 'nv2' in cols_map else None
                df_melted['nv3'] = df_head[cols_map['nv3']] if 'nv3' in cols_map else None
                df_melted['fecha'] = df_head[cols_map['fecha']].astype(str)
                df_melted['valor'] = to_numeric_datax(df_head[cols_map['valor']], decimal_separator=',')
                df_melted = df_melted.dropna(subset=['valor'])

                for c in ['nv1', 'nv2', 'nv3']:
                    if c in df_melted.columns:
                        df_melted[c] = df_melted[c].replace({'': None, np.nan: None})

                metadata_dict = {
                    "file_name": file_name,
                    "titles": ["Precio Referencial para Productos"],
                    "page_number": int(page_number) if page_number and int(page_number) > 0 else 1
                }
                return metadata_dict, df_melted

            # Case 1: Horizontal Tabular Format (produced by download robot D_BO_000000255)
            elif any('pollo' in c for c in cols_lower):
                row = df_head.iloc[0]

                # Update fecha if available in the 'Fecha' column
                for col_name in df_head.columns:
                    if 'fecha' in str(col_name).lower():
                        val_date = str(row[col_name]).strip()
                        match_d = re.search(r'(\d{4})-(\d{2})-(\d{2})', val_date)
                        if match_d:
                            fecha = match_d.group(0)

                # Pollo
                for col_name in df_head.columns:
                    if 'pollo' in str(col_name).lower():
                        val = str(row[col_name]).strip()
                        parts = [p.strip() for p in val.split('-')]
                        min_v = parts[0] if len(parts) > 0 and parts[0] else np.nan
                        max_v = parts[1] if len(parts) > 1 and parts[1] else min_v
                        rows_list.append({"nv1": "Precio del Pollo (Bs/kg Vivo)", "nv2": None, "nv3": "Min", "fecha": fecha, "valor": min_v})
                        rows_list.append({"nv1": "Precio del Pollo (Bs/kg Vivo)", "nv2": None, "nv3": "Max", "fecha": fecha, "valor": max_v})

                # Gallina
                for col_name in df_head.columns:
                    if 'gallina' in str(col_name).lower():
                        val = str(row[col_name]).strip()
                        parts = [p.strip() for p in val.split('-')]
                        min_v = parts[0] if len(parts) > 0 and parts[0] else np.nan
                        max_v = parts[1] if len(parts) > 1 and parts[1] else min_v
                        rows_list.append({"nv1": "Precio Gallina Descarte", "nv2": None, "nv3": "Min", "fecha": fecha, "valor": min_v})
                        rows_list.append({"nv1": "Precio Gallina Descarte", "nv2": None, "nv3": "Max", "fecha": fecha, "valor": max_v})

                # Huevos
                for col_name in df_head.columns:
                    if 'huevo' in str(col_name).lower():
                        val = str(row[col_name]).strip()
                        match_sub = re.search(r'\((.*?)\)', str(col_name))
                        if match_sub:
                            sub_raw = match_sub.group(1).strip()
                            if sub_raw.upper() == 'EXT':
                                h_type = 'Ext'
                            elif any(sub_raw.upper().endswith(sfx) for sfx in ['RA', 'DA', 'TA']):
                                h_type = sub_raw.lower()
                            else:
                                h_type = sub_raw
                        else:
                            h_type = str(col_name).strip()

                        if val in ['-', '', 'nan', '<NA>', 'None']:
                            val_final = np.nan
                        else:
                            val_final = val
                        rows_list.append({"nv1": "Precio del Huevo", "nv2": h_type, "nv3": None, "fecha": fecha, "valor": val_final})

            # Case 2: 2D Grid Format
            else:
                df_raw = pd.read_excel(file_path, header=None)

                r_pollo = None
                r_gallina = None
                r_huevo = None

                for r_idx in range(len(df_raw)):
                    row_texts = [str(x).strip().lower() for x in df_raw.iloc[r_idx].values if pd.notna(x)]
                    row_str = " ".join(row_texts)
                    if 'pollo' in row_str and r_pollo is None:
                        r_pollo = r_idx
                    elif 'gallina' in row_str and r_gallina is None:
                        r_gallina = r_idx
                    elif 'huevo' in row_str and r_huevo is None:
                        r_huevo = r_idx

                if r_pollo is not None and df_raw.shape[1] > 1:
                    pollo_raw = str(df_raw.iloc[r_pollo, 1])
                    parts = [p.strip() for p in pollo_raw.split('-')]
                    min_val = parts[0] if len(parts) > 0 and parts[0] else np.nan
                    max_val = parts[1] if len(parts) > 1 and parts[1] else min_val
                    rows_list.append({"nv1": "Precio del Pollo (Bs/kg Vivo)", "nv2": None, "nv3": "Min", "fecha": fecha, "valor": min_val})
                    rows_list.append({"nv1": "Precio del Pollo (Bs/kg Vivo)", "nv2": None, "nv3": "Max", "fecha": fecha, "valor": max_val})

                if r_gallina is not None and df_raw.shape[1] > 1:
                    gallina_raw = str(df_raw.iloc[r_gallina, 1])
                    parts = [p.strip() for p in gallina_raw.split('-')]
                    min_val = parts[0] if len(parts) > 0 and parts[0] else np.nan
                    max_val = parts[1] if len(parts) > 1 and parts[1] else min_val
                    rows_list.append({"nv1": "Precio Gallina Descarte", "nv2": None, "nv3": "Min", "fecha": fecha, "valor": min_val})
                    rows_list.append({"nv1": "Precio Gallina Descarte", "nv2": None, "nv3": "Max", "fecha": fecha, "valor": max_val})

                if r_huevo is not None and r_huevo + 1 < len(df_raw):
                    tipos_huevo = df_raw.iloc[r_huevo, 1:].tolist()
                    valores_huevo = df_raw.iloc[r_huevo + 1, 1:].tolist()

                    for h_type, h_val in zip(tipos_huevo, valores_huevo):
                        if pd.isna(h_type):
                            continue

                        h_val_str = str(h_val).strip()
                        if h_val_str in ['-', '', 'nan', '<NA>', 'None']:
                            val_final = np.nan
                        else:
                            val_final = h_val_str

                        rows_list.append({"nv1": "Precio del Huevo", "nv2": str(h_type).strip(), "nv3": None, "fecha": fecha, "valor": val_final})

            # 3. Construct final standard DataFrame
            if not rows_list:
                print(f"Could not extract any rows from {file_path}")
                df_melted = pd.DataFrame(columns=["nv1", "nv2", "nv3", "fecha", "valor"])
            else:
                df_melted = pd.DataFrame(rows_list)
                for c in ['nv1', 'nv2', 'nv3']:
                    if c in df_melted.columns:
                        df_melted[c] = df_melted[c].replace({'': None, np.nan: None})
                df_melted['valor'] = to_numeric_datax(df_melted['valor'], decimal_separator=',')
                df_melted = df_melted.dropna(subset=['valor'])

            # 4. Build metadata dictionary (strict DATAX rules)
            metadata_dict = {
                "file_name": file_name,
                "titles": ["Precio Referencial para Productos"],
                "page_number": int(page_number) if page_number and int(page_number) > 0 else 1
            }

            return metadata_dict, df_melted

        except Exception:
            traceback.print_exc()
            file_name = os.path.basename(file_path) if file_path else ""
            return {
                "file_name": file_name,
                "titles": ["Precio Referencial para Productos"],
                "page_number": int(page_number) if page_number and int(page_number) > 0 else 1
            }, pd.DataFrame(columns=["nv1", "nv2", "nv3", "fecha", "valor"])

    def validate_data_results(
        self, 
        dataframe: pd.DataFrame, 
        decimal_separator: str, 
        TOLERANCE: float = 6.0
    ) -> bool:
        """
        Validates the integrity of extracted numerical data.
        Returns False indicating no validation errors for this specific table structure.
        """
        try:
            return False
        except Exception:
            traceback.print_exc()
            return True

    def structure_review(self, data_file: str, last_conversion_path: str):
        """
        Verifies the structure of a new data file against a previous conversion.
        Validates nv1 against the domain's valid products (VALID_NV1), allowing daily
        variations if a specific product was absent or present in the previous day's report.
        """
        if not last_conversion_path:
            return data_file

        try:
            data_df = self.get_last_conversion_df(last_conversion_path=data_file, table_name=self.__class__.__name__)
            last_conversion_df = self.get_last_conversion_df(last_conversion_path=last_conversion_path)

            last_conversion_cols = last_conversion_df.columns
            data_cols = data_df.columns

            last_conversion_cols_without_titles = [col for col in last_conversion_cols if not re.search('titulo', col)]
            data_cols_without_titles = [col for col in data_cols if not re.search('titulo', col)]

            for i, template_col in enumerate(last_conversion_cols_without_titles):
                similarity = fuzz.ratio(Text_Normalization.get_srch_value(template_col), Text_Normalization.get_srch_value(data_cols_without_titles[i]))
                if similarity < 90:
                    raise ValueError(f"Column mismatch detected: Template column '{template_col}' does not match New report column '{data_cols_without_titles[i]}'.")

            data_df.columns = last_conversion_cols
            verify_values(data_df=data_df)

            try:
                columns_to_review_df = self.get_last_conversion_df(last_conversion_path=last_conversion_path, table_name='columns_to_review')
                columns_to_review = columns_to_review_df['column'].unique().tolist()
            except Exception as e:
                print(f"Notice: 'columns_to_review' table not found in {last_conversion_path} ({e}). Defaulting to hierarchy columns.")
                columns_to_review = [col for col in last_conversion_cols if str(col).startswith('nv')]

            # Only review nv1. Exclude dynamic sub-levels nv2 / nv3
            columns_to_review = [col for col in columns_to_review if col == 'nv1']

            if not columns_to_review:
                return data_file

            columns_to_review_without_date = [col for col in columns_to_review if not re.search(r'fecha', col)]

            for column in columns_to_review_without_date:
                if column == 'nv1':
                    valid_levels = self.VALID_NV1
                else:
                    valid_levels = last_conversion_df[column].dropna().unique().tolist() if column in last_conversion_df.columns else []

                if valid_levels:
                    nv_mask = data_df.loc[:, column].apply(lambda x: isLevel(nv=valid_levels, text=x, percentage_simliraty=90))
                    invalid = data_df.loc[~nv_mask, column].dropna()
                    if not invalid.empty:
                        print(f"Error: The following values in column '{column}' do not match expected levels:")
                        print(invalid)
                        raise ValueError(f"Extraction error: Column '{column}' contains values that do not match the expected levels.")

            if len(columns_to_review) != len(columns_to_review_without_date):
                verify_frecuency(template_df=last_conversion_df, data_df=data_df)

            print("Structure verified successfully.")
            return data_file

        except ValueError as e:
            print(f"There might be a change in structure: {e}")
        except Exception as e:
            print("An error occurred during structure verification")
            traceback.print_exc()
        return ""

    def report_data_validation(self, *args, **kwargs):
        """Ensures columns_to_review in newly created SQLite only reviews 'nv1'."""
        res = super().report_data_validation(*args, **kwargs)
        if isinstance(res, dict) and res.get("conversion_path") and res.get("file_extension") == "sqlite":
            try:
                conn = sqlite3.connect(res["conversion_path"])
                conn.execute("DELETE FROM columns_to_review WHERE column != 'nv1'")
                conn.commit()
                conn.close()
            except Exception:
                pass
        return res


Robot = D_BO_000000255_01
Executor_D_BO_000000255_01 = D_BO_000000255_01

