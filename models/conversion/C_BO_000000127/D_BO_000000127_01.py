import calendar
import os
import re
from typing import Tuple
import openpyxl
import pandas as pd

from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import to_numeric_datax


class D_BO_000000127_01(Conversion_Base):
    """Robot de conversión para Financiamiento Concedido por el Resto del Sistema Financiero al Sector Privado (D_BO_000000127_01)."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> Tuple[dict, pd.DataFrame]:
        file_name = os.path.basename(file_path)

        # 1. Determinar corte temporal desde el nombre de archivo o defecto
        date_str = "2026-09-30"
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", file_name)
        if date_match:
            date_str = date_match.group(1)

        # 2. Cargar Excel y seleccionar la pestaña objetivo
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet_name = "NO BANCOS" if "NO BANCOS" in wb.sheetnames else wb.sheetnames[0]
        ws = wb[sheet_name]
        actual_page_number = wb.sheetnames.index(sheet_name) + 1

        # 3. Extraer títulos superiores (filas 1 a 6)
        titles = []
        for r in range(1, 7):
            row_texts = []
            for c in range(1, ws.max_column + 1):
                val = ws.cell(r, c).value
                if val is not None:
                    txt = str(val).strip()
                    if txt and txt not in row_texts:
                        row_texts.append(txt)
            for txt in row_texts:
                if txt and txt not in titles:
                    titles.append(txt)

        # 4. Construir los encabezados de columnas (nv3) combinando filas 7 y 8
        col_headers = {}
        header_row_main = 7
        header_row_sub = 8

        for col_idx in range(3, ws.max_column + 1):
            val7 = str(ws.cell(header_row_main, col_idx).value or "").strip()
            val8 = str(ws.cell(header_row_sub, col_idx).value or "").strip()

            if not val7 and not val8:
                continue

            if val7.endswith("-"):
                combined = val7[:-1] + val8
            elif val7 and val8:
                combined = f"{val7} {val8}"
            else:
                combined = val7 or val8

            combined = re.sub(r"\s+", " ", combined).strip()

            if combined == "%":
                combined = "Participación %"

            if combined:
                col_headers[col_idx] = combined

        # 5. Iterar filas y construir registros des-pivotados
        records = []
        current_nv1 = None

        for r in range(9, ws.max_row + 1):
            cell_a = ws.cell(r, 1)
            val_a = cell_a.value
            if val_a is None:
                continue

            text_a = re.sub(r"\s+", " ", str(val_a)).strip()
            if not text_a:
                continue

            text_a_lower = text_a.lower()
            if text_a_lower.startswith(("nota", "fuente", "elaboraci", "(1)", "(2)", "p/")):
                break

            # Comprobar si la fila tiene datos numéricos/valores en las columnas de encabezado
            has_data = False
            for col_idx in col_headers.keys():
                cell_val = ws.cell(r, col_idx).value
                if cell_val is not None and str(cell_val).strip() != "":
                    has_data = True
                    break

            # Si no tiene datos numéricos, es un encabezado de categoría principal (nv1)
            if not has_data:
                current_nv1 = text_a
                continue

            # Determinar nv1 y nv2 según si es una fila Total o Entidad
            if text_a_lower.startswith("total"):
                nv1_val = text_a
                nv2_val = None
            else:
                nv1_val = current_nv1
                nv2_val = text_a

            # Generar registros para cada columna
            for col_idx, nv3_val in col_headers.items():
                raw_val = ws.cell(r, col_idx).value
                records.append({
                    "nv1": str(nv1_val) if nv1_val is not None else None,
                    "nv2": str(nv2_val) if nv2_val is not None else None,
                    "nv3": str(nv3_val) if nv3_val is not None else None,
                    "fecha": date_str,
                    "valor": raw_val,
                })

        df_melted = pd.DataFrame(records)

        # Asegurar estructura aunque el DF esté vacío
        expected_cols = ["nv1", "nv2", "nv3", "fecha", "valor"]
        for col in expected_cols:
            if col not in df_melted.columns:
                df_melted[col] = None

        df_melted = df_melted[expected_cols]

        # Convertir columna valor a numérico vectorizado
        df_melted["valor"] = to_numeric_datax(df_melted["valor"], decimal_separator=",")
        df_melted = df_melted.dropna(subset=["valor"]).reset_index(drop=True)

        # Garantizar tipos str o None en columnas de niveles
        for col in ["nv1", "nv2", "nv3", "fecha"]:
            df_melted[col] = df_melted[col].apply(
                lambda x: str(x).strip() if pd.notna(x) and str(x).strip() != "" else None
            )

        metadata_dict = {
            "file_name": file_name,
            "titles": titles,
            "page_number": int(actual_page_number),
        }

        return metadata_dict, df_melted

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str = ",",
        TOLERANCE: float = 6.0,
    ) -> bool:
        """
        Valida que los resultados no estén vacíos y sean consistentes.
        Retorna False si los datos son válidos (sin error) y True si hay error.
        """
        if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
            return True

        req_cols = ["fecha", "valor"]
        if not all(col in dataframe.columns for col in req_cols):
            return True

        df = dataframe.copy()
        df["valor_num"] = to_numeric_datax(df["valor"], decimal_separator)

        if df["valor_num"].isna().all():
            return True

        return False


Robot = D_BO_000000127_01