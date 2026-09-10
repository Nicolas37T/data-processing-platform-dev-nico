import os
import re
import traceback
import numpy as np
import pandas as pd

from models.conversion.Conversion_Base import Conversion_Base


class D_BO_000000418_01(Conversion_Base):
    """
    Type III Conversion Robot for Ticket D_BO_000000418_01.
    Processes Interbank Rates (Tasas Interbancarias), transforming a specific 
    table into a strict vertical (melted) structure following DATAX rules.
    """

    def extraction(
        self, 
        file_path: str, 
        key_words: str, 
        template_path: str = "", 
        page_number: int = 1, 
        format: str = '%Y-%m-%d'
    ) -> tuple:
        """
        Reads the source file, dynamically locates the 'Promedio ponderado' row,
        extracts MN and ME values, and formats them into the DATAX hierarchy.
        """
        del template_path
        try:
            file_name = os.path.basename(file_path)

            # 1. Extract date from filename or content
            match = re.search(r'(\d{4}-\d{2}-\d{2})', file_name)
            if match:
                fecha = match.group(1)
            else:
                match = re.search(r'(\d{8})', file_name)
                if match:
                    raw_date = match.group(1)
                    fecha = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
                else:
                    fecha = pd.Timestamp.now().strftime(format)

            # 2. Read the raw file
            found_page = int(page_number) if page_number else 1
            try:
                excel_file = pd.ExcelFile(file_path)
                sheet_names = excel_file.sheet_names
                sheet_name = 0
                for idx, s in enumerate(sheet_names):
                    if s.strip().upper() == 'ACT':
                        sheet_name = s
                        found_page = idx + 1
                        break
                df_raw = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
            except Exception:
                from models.conversion.tools.conversion_tools import extract_pdf_table_fitz
                df_raw = extract_pdf_table_fitz(file_path, page_number)

            # Fallback date extraction from sheet content if not found in filename
            if not match:
                month_map = {
                    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5,
                    "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9,
                    "octubre": 10, "noviembre": 11, "diciembre": 12
                }
                for _, row in df_raw.iloc[:10].iterrows():
                    combined = " ".join(str(c).strip() for c in row if pd.notna(c))
                    m_date = re.search(r"al\s+(\d{1,2})\s+de\s+([A-Za-zÀ-ÿ]+)\s+de\s+(\d{4})", combined, re.IGNORECASE)
                    if m_date:
                        d_val = int(m_date.group(1))
                        m_str = m_date.group(2).lower()
                        y_val = int(m_date.group(3))
                        if m_str in month_map:
                            fecha = f"{y_val:04d}-{month_map[m_str]:02d}-{d_val:02d}"
                            break

            # 3. Dynamically locate "Promedio ponderado" and extract values
            mn_val = pd.NA
            me_val = pd.NA
            
            for i in range(len(df_raw)):
                row_values = [str(val).strip().lower() if pd.notna(val) else "" for val in df_raw.iloc[i]]
                row_text = " ".join(row_values)
                
                if "promedio ponderado" in row_text:
                    col_idx = -1
                    for j, val in enumerate(row_values):
                        if "promedio ponderado" in val:
                            col_idx = j
                            break
                    
                    if col_idx != -1:
                        target_row = i + 1 if (i + 1) < len(df_raw) else i
                        mn_raw = str(df_raw.iloc[target_row, col_idx + 1]).strip() if (col_idx + 1) < df_raw.shape[1] else ""
                        me_raw = str(df_raw.iloc[target_row, col_idx + 2]).strip() if (col_idx + 2) < df_raw.shape[1] else ""
                        
                        mn_val = pd.NA if mn_raw in ['-', '', 'nan', 'none', 'None', '<NA>'] else mn_raw
                        me_val = pd.NA if me_raw in ['-', '', 'nan', 'none', 'None', '<NA>'] else me_raw
                    break

            # 4. Construct standard DATAX DataFrame
            rows_list = [
                {
                    "nv1": "Tasas interbancarias",
                    "nv2": "Promedio ponderado",
                    "nv3": "MN",
                    "fecha": fecha,
                    "valor": mn_val
                },
                {
                    "nv1": "Tasas interbancarias",
                    "nv2": "Promedio ponderado",
                    "nv3": "ME",
                    "fecha": fecha,
                    "valor": me_val
                }
            ]

            df_melted = pd.DataFrame(rows_list)

            # 5. Clean 'valor' column
            df_melted['valor'] = pd.to_numeric(df_melted['valor'], errors='coerce')

            # 6. Build metadata dictionary
            metadata_dict = {
                "file_name": file_name,
                "titles": ["Tasas Interbancarias"],
                "page_number": found_page
            }

            return metadata_dict, df_melted

        except Exception as error:
            print(f"Could not extract report from {file_path}: {error}")
            traceback.print_exc()
            return "", pd.DataFrame()

    def validate_data_results(
        self, 
        dataframe: pd.DataFrame, 
        decimal_separator: str = ",", 
        TOLERANCE: float = 6.0
    ) -> bool:
        """
        Validates the integrity of extracted numerical data.
        Returns False as there are no printed totals to validate against.
        """
        del decimal_separator, TOLERANCE
        try:
            return False
        except Exception as error:
            print(f"Validation error: {error}")
            traceback.print_exc()
            return True


Robot = D_BO_000000418_01
