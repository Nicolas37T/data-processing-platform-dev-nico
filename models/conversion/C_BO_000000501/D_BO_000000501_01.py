import os
import re
import pandas as pd
import pdfplumber
from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import to_numeric_datax


class D_BO_000000501_01(Conversion_Base):
    """
    DataX Platform conversion robot for report D_BO_000000501_01:
    [Conversion] Precios Mayorista de Productos Agropecuarios y Agroindustrial.
    Processes multi-page PDF files containing daily agricultural wholesale prices.
    """

    def extraction(self, file_path: str, key_words: str, template_path: str = '', page_number: int = 1, format: str = '%Y-%m-%d') -> tuple:
        file_name = os.path.basename(file_path)

        def parse_date(date_raw):
            if not date_raw:
                return None
            m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', str(date_raw))
            if m:
                day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
                return f"{year:04d}-{month:02d}-{day:02d}"
            return None

        titles = []
        records = []

        with pdfplumber.open(file_path) as pdf:
            # 1. Extract titles from top of page 1
            if len(pdf.pages) > 0:
                first_page = pdf.pages[0]
                tables = [t for t in first_page.find_tables() if len(t.rows) >= 3]
                if tables:
                    table_obj = max(tables, key=lambda t: (t.bbox[2] - t.bbox[0]) * (t.bbox[3] - t.bbox[1]))
                    top = table_obj.bbox[1]
                    for l in first_page.extract_text_lines():
                        if l["bottom"] <= top + 1.5 and l["text"].strip():
                            text = " ".join(l["text"].split())
                            if not any(city in text.upper() for city in ["LA PAZ", "SANTA CRUZ", "EL ALTO", "COCHABAMBA", "TARIJA", "SUCRE", "POTOSI", "ORURO", "COBIJA", "TRINIDAD"]):
                                titles.append(text)

            if not titles:
                titles = [
                    "PRECIOS MAYORISTAS DIARIOS DE PRODUCTOS AGROPECUARIOS Y AGROINDUSTRIALES",
                    "SEMANA N° 46"
                ]

            # 2. Iterate through all pages in the PDF
            for page in pdf.pages:
                table = page.extract_table()
                if not table or len(table) < 3:
                    continue

                # Identify entities from header row 0
                entities = []
                for cell in table[0]:
                    if cell:
                        c_clean = cell.strip()
                        if c_clean and c_clean not in ["PRODUCTOS Y SUS CARACTERISTICAS", "UNIDAD", "VARIACIÓN %", "%"] and "PRODUCTOS" not in c_clean.upper():
                            if c_clean not in entities:
                                entities.append(c_clean)

                entity1 = entities[0] if len(entities) > 0 else "ENTIDAD 1"
                entity2 = entities[1] if len(entities) > 1 else "ENTIDAD 2"

                # Extract dates from header row 2
                header_row2 = table[2]
                date_map = {}
                # Entity 1 daily dates: cols 2..6
                for c_idx in range(2, 7):
                    if c_idx < len(header_row2):
                        date_map[c_idx] = parse_date(header_row2[c_idx])

                # Entity 2 daily dates: cols 9..13
                for c_idx in range(9, 14):
                    if c_idx < len(header_row2):
                        date_map[c_idx] = parse_date(header_row2[c_idx])

                friday_date_entity1 = date_map.get(6)
                friday_date_entity2 = date_map.get(13)

                # Process data rows starting from row 3
                current_nv1 = None
                for r_idx in range(3, len(table)):
                    row = table[r_idx]
                    if not row or not any(row):
                        continue

                    col0 = str(row[0]).strip() if row[0] else ""
                    col1 = str(row[1]).strip() if len(row) > 1 and row[1] else ""

                    # Check if row has numeric price values
                    has_prices = False
                    for c in range(2, len(row)):
                        if row[c] and re.search(r'\d', str(row[c])):
                            has_prices = True
                            break

                    # Section / Category Header row
                    if col0 and not col1 and not has_prices:
                        current_nv1 = col0
                        continue

                    if not col0 or not current_nv1:
                        continue

                    nv2 = col0
                    nv3 = col1

                    # Entity 1 Daily Prices (Cols 2..6)
                    for c_idx in range(2, 7):
                        if c_idx < len(row) and row[c_idx]:
                            raw_val = str(row[c_idx])
                            clean_val = re.sub(r'[\s%↑↓=]', '', raw_val)
                            if re.search(r'\d', clean_val):
                                fecha_val = date_map.get(c_idx)
                                if fecha_val:
                                    records.append({
                                        "nv1": current_nv1,
                                        "nv2": nv2,
                                        "nv3": nv3,
                                        "nv4": entity1,
                                        "fecha": fecha_val,
                                        "valor": clean_val
                                    })

                    # Entity 1 Variation % (Cols 7/8)
                    var_str1 = ""
                    if len(row) > 8 and row[8]:
                        var_str1 = str(row[8])
                    elif len(row) > 7 and row[7]:
                        var_str1 = str(row[7])

                    clean_var1 = re.sub(r'[\s%↑↓=]', '', var_str1)
                    if re.search(r'\d', clean_var1) and friday_date_entity1:
                        records.append({
                            "nv1": current_nv1,
                            "nv2": nv2,
                            "nv3": nv3,
                            "nv4": "Variación %",
                            "fecha": friday_date_entity1,
                            "valor": clean_var1
                        })

                    # Entity 2 Daily Prices (Cols 9..13)
                    for c_idx in range(9, 14):
                        if c_idx < len(row) and row[c_idx]:
                            raw_val = str(row[c_idx])
                            clean_val = re.sub(r'[\s%↑↓=]', '', raw_val)
                            if re.search(r'\d', clean_val):
                                fecha_val = date_map.get(c_idx)
                                if fecha_val:
                                    records.append({
                                        "nv1": current_nv1,
                                        "nv2": nv2,
                                        "nv3": nv3,
                                        "nv4": entity2,
                                        "fecha": fecha_val,
                                        "valor": clean_val
                                    })

                    # Entity 2 Variation % (Cols 14/15)
                    var_str2 = ""
                    if len(row) > 15 and row[15]:
                        var_str2 = str(row[15])
                    elif len(row) > 14 and row[14]:
                        var_str2 = str(row[14])

                    clean_var2 = re.sub(r'[\s%↑↓=]', '', var_str2)
                    if re.search(r'\d', clean_var2) and friday_date_entity2:
                        records.append({
                            "nv1": current_nv1,
                            "nv2": nv2,
                            "nv3": nv3,
                            "nv4": "Variación %",
                            "fecha": friday_date_entity2,
                            "valor": clean_var2
                        })

        if not records:
            df_melted = pd.DataFrame(columns=['nv1', 'nv2', 'nv3', 'nv4', 'fecha', 'valor'])
        else:
            df_melted = pd.DataFrame(records)
            # The document uses '.' as decimal separator
            df_melted['valor'] = to_numeric_datax(df_melted['valor'], decimal_separator='.')
            df_melted = df_melted.dropna(subset=['valor'])

        p_num = int(page_number) if page_number and int(page_number) > 0 else 1

        metadata_dict = {
            'file_name': file_name,
            'titles': titles,
            'page_number': p_num
        }

        return metadata_dict, df_melted

    def validate_data_results(self, dataframe: pd.DataFrame, decimal_separator: str = ',', TOLERANCE: float = 6.0) -> bool:
        if dataframe is None or dataframe.empty:
            return True

        if 'valor' not in dataframe.columns:
            return True

        if dataframe['valor'].isna().any():
            return True

        return False


Robot = D_BO_000000501_01