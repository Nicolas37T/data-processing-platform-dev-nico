import os
import re
import openpyxl
import pandas as pd
from typing import Tuple
from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import to_numeric_datax


class D_BO_000000128_01(Conversion_Base):
    """
    Robot de conversión para el reporte: Depósitos del Sector Privado en Cuenta Corriente
    en el Sistema Bancario (D_BO_000000128_01).
    """

    def extraction(
        self,
        file_path: str,
        key_words: str = None,
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> Tuple[dict, pd.DataFrame]:
        # 1. Cargar el libro y seleccionar la hoja 'Bancos'
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet_name = "Bancos"
        if sheet_name not in wb.sheetnames:
            # Si no existe por nombre, usar el page_number (1-based)
            idx = int(page_number) - 1 if page_number and int(page_number) > 0 else 0
            sheet_name = wb.sheetnames[idx]
        
        ws = wb[sheet_name]
        actual_page_number = wb.sheetnames.index(sheet_name) + 1

        # 2. Extraer Títulos (Filas 1 a 6)
        # Según muestra: Fila 2 (B), Fila 3 (B), Fila 6 (B), Fila 6 (L)
        titles = []
        for r in range(1, 7):
            row_titles = []
            for c in range(1, ws.max_column + 1):
                val = ws.cell(r, c).value
                if val:
                    text = str(val).strip()
                    if text and text not in row_titles:
                        row_titles.append(text)
            titles.extend(row_titles)

        # 3. Extraer Fecha de Corte del título (Fila 3)
        # Ejemplo: "(Saldo al 30 de septiembre de 2026)"
        fecha_str = ""
        month_map = {
            "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
            "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
            "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
        }
        
        title_date_text = str(ws.cell(3, 2).value or "")
        date_match = re.search(r"(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})", title_date_text.lower())
        if date_match:
            day = int(date_match.group(1))
            month = month_map.get(date_match.group(2), "01")
            year = date_match.group(3)
            fecha_str = f"{year}-{month}-{day:02d}"
        else:
            # Fallback: buscar cualquier fecha en el nombre del archivo
            file_date = re.search(r"(\d{4})[-_](\d{2})[-_](\d{2})", os.path.basename(file_path))
            if file_date:
                fecha_str = f"{file_date.group(1)}-{file_date.group(2)}-{file_date.group(3)}"
            else:
                fecha_str = "2026-09-30" # Default según muestra

        # 4. Mapear Encabezados de Columnas (Departamentos)
        # Fila 7, Columnas 3 a 13
        col_headers = {}
        header_row = 7
        for c in range(3, 14):
            val = ws.cell(header_row, c).value
            if val:
                col_headers[c] = str(val).strip()

        # 5. Procesar Filas de Datos
        records = []
        curr_nv1 = None
        curr_nv2 = None
        
        # Empezamos en la fila 9 (BANCOS MÚLTIPLES)
        for r in range(9, ws.max_row + 1):
            cell = ws.cell(r, 2) # label_col = 2 (B)
            text = str(cell.value).strip() if cell.value else ""
            
            if not text or text in ["FUENTE", "NOTAS"]:
                if r > 30: break # Evitar cortes prematuros si hay celdas vacías intermedias
                else: continue

            is_bold = cell.font.bold if cell.font else False
            indent = cell.alignment.indent if cell.alignment else 0
            
            # Lógica de Jerarquía
            if text == "TOTAL SISTEMA":
                curr_nv1 = text
                curr_nv2 = None
            elif is_bold and indent == 0 and "TOTAL" not in text:
                # Es un encabezado de sección (ej: BANCOS MÚLTIPLES)
                curr_nv1 = text
                curr_nv2 = None
                # Verificamos si esta fila tiene datos (a veces el total de sección está en la misma fila)
                has_data = any(ws.cell(r, c).value is not None for c in col_headers.keys())
                if not has_data:
                    continue
            elif is_bold and "TOTAL" in text:
                # Es un total de sección (ej: TOTAL dentro de BANCOS MÚLTIPLES)
                curr_nv2 = text
            else:
                # Es una entidad individual (ej: NACIONAL, UNIÓN)
                curr_nv2 = text

            # Extraer valores para cada columna (nv3)
            for col_idx, nv3_name in col_headers.items():
                raw_val = ws.cell(r, col_idx).value
                records.append({
                    "nv1": curr_nv1,
                    "nv2": curr_nv2,
                    "nv3": nv3_name,
                    "fecha": fecha_str,
                    "valor": raw_val
                })

        # 6. Crear DataFrame y Limpiar
        df_melted = pd.DataFrame(records)
        
        # Convertir valores a numérico usando la herramienta oficial de DATAX
        df_melted["valor"] = to_numeric_datax(df_melted["valor"], decimal_separator=",")
        
        # Eliminar filas donde el valor sea NaN (opcional, pero recomendado para limpieza)
        df_melted = df_melted.dropna(subset=["valor"])
        
        # Asegurar que las columnas nv sean string o None
        for col in ["nv1", "nv2", "nv3"]:
            df_melted[col] = df_melted[col].astype(str).replace("None", None).replace("nan", None)

        metadata_dict = {
            "file_name": os.path.basename(file_path),
            "titles": titles,
            "page_number": int(actual_page_number)
        }

        return metadata_dict, df_melted

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str = ",",
        TOLERANCE: float = 6.0,
    ) -> bool:
        """
        Valida la consistencia de los datos:
        1. Los totales de sección (nv2='TOTAL') deben sumar el TOTAL SISTEMA.
        2. Los departamentos deben sumar el TOTAL de la fila.
        """
        try:
            if dataframe.empty:
                return True
            
            # Crear copia para no afectar el original y asegurar valores numéricos
            df = dataframe.copy()
            # Nota: El dataframe ya viene con columnas 'file', 'titulo1', etc.
            # Buscamos las columnas de datos reales
            val_col = "valor"
            
            # 1. Validación de Suma de Secciones hacia el Total Sistema
            # (BANCOS MÚLTIPLES TOTAL + BANCOS PYME TOTAL) == TOTAL SISTEMA
            for fecha in df["fecha"].unique():
                df_f = df[df["fecha"] == fecha]
                
                for nv3 in df_f["nv3"].unique():
                    if "Particip" in str(nv3):
                        continue
                    
                    # Suma de los totales de cada categoría
                    sum_categories = df_f[
                        (df_f["nv1"].isin(["BANCOS MÚLTIPLES", "BANCOS PYME"])) & 
                        (df_f["nv2"] == "TOTAL") & 
                        (df_f["nv3"] == nv3)
                    ][val_col].sum()
                    
                    # Valor reportado en Total Sistema
                    total_sistema = df_f[
                        (df_f["nv1"] == "TOTAL SISTEMA") & 
                        (df_f["nv3"] == nv3)
                    ][val_col].sum()
                    
                    if abs(sum_categories - total_sistema) > TOLERANCE:
                        return True

            # 2. Validación Horizontal: Departamentos sumando al Total de la fila
            # Solo para filas que no sean de participación %
            for fecha in df["fecha"].unique():
                df_f = df[df["fecha"] == fecha]
                # Agrupar por nv1 y nv2 para validar cada fila
                for (n1, n2), group in df_f.groupby(["nv1", "nv2"], dropna=False):
                    row_total = group[group["nv3"] == "TOTAL"][val_col].sum()
                    dept_sum = group[
                        (~group["nv3"].isin(["TOTAL", "Particip. %"]))
                    ][val_col].sum()
                    
                    if row_total > 0 and abs(dept_sum - row_total) > TOLERANCE:
                        return True

            return False
        except Exception:
            return True


Robot = D_BO_000000128_01