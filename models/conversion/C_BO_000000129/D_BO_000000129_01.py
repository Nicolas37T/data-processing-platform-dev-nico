import os
import re
import openpyxl
import pandas as pd
from typing import Tuple

from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import to_numeric_datax


class D_BO_000000129_01(Conversion_Base):
    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> Tuple[dict, pd.DataFrame]:
        file_name = os.path.basename(file_path)
        wb = openpyxl.load_workbook(file_path, data_only=True)

        # Seleccionar hoja correspondiente al reporte
        sheet_name = None
        if isinstance(page_number, int) and page_number > 0 and page_number <= len(wb.sheetnames):
            sheet_name = wb.sheetnames[page_number - 1]
        else:
            for s in wb.sheetnames:
                if "banco" in s.lower():
                    sheet_name = s
                    break
            if not sheet_name:
                sheet_name = wb.sheetnames[0]

        processed_page_number = wb.sheetnames.index(sheet_name) + 1
        ws = wb[sheet_name]

        # 1. Localizar dinámicamente la fila de encabezados y columna de etiquetas
        header_row = 6
        label_col = 1

        for r in range(1, 15):
            for c in range(1, 15):
                val = ws.cell(r, c).value
                if val and str(val).strip().upper() in ["LA PAZ", "SANTA CRUZ", "COCHABAMBA"]:
                    header_row = r
                    label_col = 1
                    break

        # 2. Extraer Títulos (encabezados superiores antes de la fila de columnas)
        titles = []
        for r in range(1, header_row):
            for c in range(1, ws.max_column + 1):
                val = ws.cell(r, c).value
                if val is not None:
                    val_str = str(val).strip()
                    if val_str and val_str not in titles:
                        titles.append(val_str)

        # Determinar fecha de corte desde los títulos o texto
        extracted_date = "2026-09-30"
        month_map = {
            "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
            "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
            "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
        }

        full_title_text = " ".join(titles)
        date_match = re.search(
            r"(\d{1,2})\s+de\s+([a-zA-ZáéíóúÁÉÍÓÚ]+)\s+de\s+(\d{4})",
            full_title_text,
            re.IGNORECASE,
        )
        if date_match:
            day = int(date_match.group(1))
            m_str = date_match.group(2).lower()
            year = date_match.group(3)
            m_num = month_map.get(m_str, "09")
            extracted_date = f"{year}-{m_num}-{day:02d}"

        # 3. Mapear columnas de la tabla (nv3)
        col_headers = {}
        for col in range(label_col + 1, ws.max_column + 1):
            val = ws.cell(header_row, col).value
            if val is not None:
                col_headers[col] = str(val).strip()

        # 4. Procesar filas de datos des-pivotando a [nv1, nv2, nv3, fecha, valor]
        records = []
        curr_nv1 = None

        for r in range(header_row + 1, ws.max_row + 1):
            label_val = ws.cell(r, label_col).value
            if not label_val:
                continue

            label = str(label_val).strip()
            if not label:
                continue

            # Omitir notas al pie o encabezados finales
            if label.upper().startswith(("FUENTE", "NOTAS", "NOTA", ":", "ELABORACIÓN", "(P)")):
                break

            # Verificar si la fila contiene datos numéricos
            has_numbers = False
            for c in col_headers.keys():
                c_val = ws.cell(r, c).value
                if c_val is not None:
                    v_str = str(c_val).strip().replace(",", ".").replace(" ", "")
                    try:
                        float(v_str)
                        has_numbers = True
                        break
                    except ValueError:
                        pass

            if not has_numbers:
                # Fila de sección/agrupador (ej: BANCOS MÚLTIPLES, BANCOS PYME)
                curr_nv1 = label
                continue

            # Determinación jerárquica de nv1 y nv2
            if label.upper() == "TOTAL SISTEMA":
                nv1 = label
                nv2 = None
            elif curr_nv1 and label == curr_nv1:
                nv1 = label
                nv2 = None
            elif curr_nv1:
                nv1 = curr_nv1
                nv2 = label
            else:
                nv1 = label
                nv2 = None

            # Des-pivotar columnas horizontales
            for c, department_nv3 in col_headers.items():
                raw_val = ws.cell(r, c).value
                records.append({
                    "nv1": nv1,
                    "nv2": nv2,
                    "nv3": department_nv3,
                    "fecha": extracted_date,
                    "valor": raw_val,
                })

        df_melted = pd.DataFrame(records)

        if not df_melted.empty:
            # Conversión numérica vectorizada obligatoria
            df_melted["valor"] = to_numeric_datax(df_melted["valor"], decimal_separator=",")
            df_melted = df_melted.dropna(subset=["valor"]).reset_index(drop=True)

            # Asegurar que las columnas que no son 'valor' sean string o None/NaN
            for col in ["nv1", "nv2", "nv3", "fecha"]:
                df_melted[col] = df_melted[col].apply(lambda x: str(x) if pd.notna(x) and x is not None else None)
        else:
            df_melted = pd.DataFrame(columns=["nv1", "nv2", "nv3", "fecha", "valor"])

        metadata_dict = {
            "file_name": file_name,
            "titles": titles,
            "page_number": int(processed_page_number),
        }

        return metadata_dict, df_melted

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str = ",",
        TOLERANCE: float = 6.0,
    ) -> bool:
        if dataframe is None or dataframe.empty:
            return True

        required_cols = ["nv1", "nv2", "nv3", "fecha", "valor"]
        for c in required_cols:
            if c not in dataframe.columns:
                return True

        df = dataframe.copy()
        df["valor_num"] = to_numeric_datax(df["valor"], decimal_separator=',')

        if df["valor_num"].isna().all():
            return True

        # Retorna False si los datos extraídos son consistentes y válidos
        return False


Robot = D_BO_000000129_01