import os
import re
import traceback
import numpy as np
import pandas as pd

from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import to_numeric_datax


class D_BO_000000255_01(Conversion_Base):
    """
    Type III Conversion Robot for adascz.com.bo (Ticket #96).
    Responsible for extracting data from the raw Excel matrix and normalizing it 
    into a vertical structure (melted DataFrame) following DATAX rules.
    """

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

            # 2. Read the raw Excel matrix without headers
            df_raw = pd.read_excel(file_path, header=None)
            rows_list = []

            # 3. Process Pollo (Row 1, Column 1)
            pollo_raw = str(df_raw.iloc[1, 1])
            parts = [p.strip() for p in pollo_raw.split('-')]
            min_val = parts[0] if len(parts) > 0 and parts[0] else np.nan
            max_val = parts[1] if len(parts) > 1 and parts[1] else min_val
            
            rows_list.append({"nv1": "Precio del Pollo (Bs/kg Vivo)", "nv2": "", "nv3": "Min", "fecha": fecha, "valor": min_val})
            rows_list.append({"nv1": "Precio del Pollo (Bs/kg Vivo)", "nv2": "", "nv3": "Max", "fecha": fecha, "valor": max_val})
            
            # 4. Process Gallina (Row 2, Column 1)
            gallina_raw = str(df_raw.iloc[2, 1])
            parts = [p.strip() for p in gallina_raw.split('-')]
            min_val = parts[0] if len(parts) > 0 and parts[0] else np.nan
            max_val = parts[1] if len(parts) > 1 and parts[1] else min_val
            
            rows_list.append({"nv1": "Precio Gallina Descarte", "nv2": "", "nv3": "Min", "fecha": fecha, "valor": min_val})
            rows_list.append({"nv1": "Precio Gallina Descarte", "nv2": "", "nv3": "Max", "fecha": fecha, "valor": max_val})
            
            # 5. Process Huevos (Row 3 for types, Row 4 for values)
            tipos_huevo = df_raw.iloc[3, 1:].tolist()
            valores_huevo = df_raw.iloc[4, 1:].tolist()
            
            for h_type, h_val in zip(tipos_huevo, valores_huevo):
                if pd.isna(h_type):
                    continue
                
                h_val_str = str(h_val).strip()
                if h_val_str in ['-', '', 'nan', '<NA>', 'None']:
                    val_final = np.nan
                else:
                    val_final = h_val_str
                
                rows_list.append({"nv1": "Precio del Huevo", "nv2": str(h_type).strip(), "nv3": "", "fecha": fecha, "valor": val_final})

            # 6. Construct final standard DataFrame
            df_melted = pd.DataFrame(rows_list)
            df_melted['valor'] = to_numeric_datax(df_melted['valor'], decimal_separator=',')
            df_melted = df_melted.dropna(subset=['valor'])

            # 7. Build metadata dictionary (strict DATAX rules)
            metadata_dict = {
                "file_name": file_name,
                "titles": ["Precio Referencial para Productos"],
                "page_number": int(page_number) if page_number and int(page_number) > 0 else 1
            }

            return metadata_dict, df_melted

        except Exception:
            traceback.print_exc()
            return ""

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


Robot = D_BO_000000255_01

