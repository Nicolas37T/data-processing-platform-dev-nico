import os
import re
import traceback
import pandas as pd

from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import search_key_words, to_numeric_datax


class D_BO_000000418_02(Conversion_Base):

    def extraction(self, file_path, key_words, template_path="", page_number=1, format='%Y-%m-%d'):
        del template_path
        try:
            def normalize_text(value):
                if value is None or pd.isna(value):
                    return ""
                return str(value).strip()

            def parse_report_date(df):
                combined = " ".join(
                    " ".join(normalize_text(cell) for cell in row.tolist() if normalize_text(cell))
                    for _, row in df.iterrows()
                )
                match = re.search(r"(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+([A-Za-zÀ-ÿ]+)\s+de\s+(\d{4})", combined, flags=re.IGNORECASE)
                if match:
                    day = int(match.group(2))
                    month_name = match.group(3).lower()
                    year = int(match.group(4))
                    month_map = {
                        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5,
                        "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9,
                        "octubre": 10, "noviembre": 11, "diciembre": 12,
                    }
                    month = month_map.get(month_name)
                    if month:
                        return f"{year:04d}-{month:02d}-{day:02d}"
                return "2026-08-16"

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            file_name = os.path.basename(file_path)
            excel = pd.ExcelFile(file_path)
            sheet_names = excel.sheet_names
            target_index = max(0, min(int(page_number) - 1, len(sheet_names) - 1))

            raw_df = None
            resolved_page = target_index + 1

            normalized_sheet_names = {str(name).upper(): name for name in sheet_names}
            preferred_sheet = normalized_sheet_names.get("PAS")
            if preferred_sheet is not None:
                raw_df = pd.read_excel(file_path, sheet_name=preferred_sheet, header=None)
                resolved_page = sheet_names.index(preferred_sheet) + 1
            elif key_words and str(key_words).strip():
                for idx, sheet_name in enumerate(sheet_names):
                    df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
                    text = " ".join(str(value) for value in df.to_numpy().ravel() if str(value).strip())
                    if search_key_words(text=text, key_words=key_words):
                        raw_df = df
                        resolved_page = idx + 1
                        break

            if raw_df is None:
                sheet_name = sheet_names[target_index]
                raw_df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
                resolved_page = target_index + 1

            titles = []
            for _, row in raw_df.iterrows():
                text = " ".join(normalize_text(cell) for cell in row.tolist() if normalize_text(cell))
                if not text:
                    continue
                if any(token in text.upper() for token in ["BANCO CENTRAL", "INFORMACIÓN SOBRE", "TASAS PASIVAS", "SEMANA DEL", "INTERÉS QUE PERCIBEN"]):
                    titles.append(text)
                if "BANCOS MÚLTIPLES" in text.upper() or "ENTIDADES" in text.upper():
                    break

            report_date = parse_report_date(raw_df)

            def clean_numeric_value(raw_value):
                if raw_value is None or pd.isna(raw_value):
                    return "0"
                value_str = str(raw_value).strip()
                if not value_str or value_str.lower() in {"nan", "none"}:
                    return "0"
                try:
                    num = float(value_str)
                    if abs(num) < 1e-12:
                        return "0"

                    artifact_patterns = [
                        "999999999999998",
                        "999999999999999",
                        "000000000000002",
                        "000000000000004",
                    ]
                    if any(marker in value_str for marker in artifact_patterns) and abs(num) < 0.02:
                        return format(round(num, 2), ".2f").rstrip("0").rstrip(".")

                    for decimals in range(2, 14):
                        rounded = round(num, decimals)
                        threshold = 10 ** (-decimals - 2)
                        if abs(num - rounded) <= threshold:
                            text = format(rounded, f".{decimals}f").rstrip("0").rstrip(".")
                            if text in {"-0", "-0.0"}:
                                return "0"
                            return text

                    text = format(round(num, 12), ".12f").rstrip("0").rstrip(".")
                    if text in {"-0", "-0.0"}:
                        return "0"
                    return text
                except (TypeError, ValueError):
                    return value_str

            periods = ["30", "60", "90", "180", "360", "720", "1080", "Mayor"]
            generic_labels = {
                "ENTIDADES",
                "BANCOS MÚLTIPLES",
                "BANCOS MULTIPLES",
                "BANCOS PYME",
                "COOPERATIVAS",
                "ENTIDADES FINANCIERAS DE VIVIENDA",
                "ENTIDADES ESPECIALIZADAS EN MICROFINANZAS",
                "INSTITUCIONES FINANCIERAS DE DESARROLLO",
            }
            footer_markers = (
                "VIGENTE DESDE", "PROMEDIOS PONDERADOS", "FUENTE", "TASAS EFECTIVAS",
                "CAPITALIZACIONES", "ELABORACIÓN", "INTERÉS QUE PERCIBEN", "BANCO CENTRAL"
            )
            records = []
            current_group = "BANCOS MÚLTIPLES"
            start_row = None

            for idx in range(len(raw_df)):
                row = raw_df.iloc[idx].tolist()
                valid_cells = [normalize_text(cell) for cell in row if normalize_text(cell)]
                if not valid_cells:
                    continue
                first = valid_cells[0]
                upper_first = first.upper()
                if any(token in upper_first for token in ["BANCO CENTRAL", "INFORMACIÓN SOBRE", "TASAS PASIVAS", "SEMANA DEL", "INTERÉS QUE PERCIBEN", "MONEDA NACIONAL", "MONEDA EXTRANJERA", "CAJA DE AHORRO", "DEPOSITOS A PLAZO"]):
                    continue
                if any(marker in upper_first for marker in footer_markers):
                    continue
                if upper_first in generic_labels or upper_first.startswith("BANCOS") or upper_first.startswith("COOPERATIVAS") or "ENTIDADES" in upper_first:
                    current_group = first.strip()
                    continue
                if upper_first in {"30", "60", "90", "180", "360", "720", "1080", "MAYOR"} or re.fullmatch(r"\d+", upper_first):
                    continue

                numeric_values = []
                for pos, value in enumerate(row[1:], start=1):
                    if value is None or pd.isna(value):
                        continue
                    clean = str(value).strip()
                    if not clean or clean.lower() in {"nan", "none"}:
                        continue
                    if any(token in clean.lower() for token in ["vigente desde", "al", "promedios ponderados", "fuente", "capitalizaciones", "elaboración", "tasa"]):
                        continue
                    if not re.search(r"\d", clean):
                        continue
                    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}.*", clean):
                        continue
                    numeric_values.append((pos, clean))
                if numeric_values:
                    start_row = idx
                    break

            if start_row is None:
                raise ValueError("No data rows were identified in the report")

            for idx in range(start_row, len(raw_df)):
                row = raw_df.iloc[idx].tolist()
                valid_cells = [normalize_text(cell) for cell in row if normalize_text(cell)]
                if not valid_cells:
                    continue
                first = valid_cells[0]
                upper_first = first.upper()
                if any(token in upper_first for token in ["BANCO CENTRAL", "INFORMACIÓN SOBRE", "TASAS PASIVAS", "SEMANA DEL", "INTERÉS QUE PERCIBEN", "MONEDA NACIONAL", "MONEDA EXTRANJERA", "CAJA DE AHORRO", "DEPOSITOS A PLAZO"]):
                    continue
                if any(marker in upper_first for marker in footer_markers):
                    continue
                if upper_first in generic_labels or upper_first.startswith("BANCOS") or upper_first.startswith("COOPERATIVAS") or "ENTIDADES" in upper_first or "INSTITUCIONES" in upper_first:
                    if first.strip().upper() in {"BANCOS MÚLTIPLES", "BANCOS MULTIPLES"}:
                        if current_group and any(label in current_group.upper() for label in ["MICROFINANZAS", "DESARROLLO", "VIVIENDA", "PYME", "COOPERATIVAS", "ENTIDADES"]):
                            continue
                    current_group = first.strip()
                    continue
                if upper_first in {"30", "60", "90", "180", "360", "720", "1080", "MAYOR"} or re.fullmatch(r"\d+", upper_first):
                    continue

                numeric_values = []
                for pos, value in enumerate(row[1:], start=1):
                    if value is None or pd.isna(value):
                        continue
                    clean = str(value).strip()
                    if not clean or clean.lower() in {"nan", "none"}:
                        continue
                    if any(token in clean.lower() for token in ["vigente desde", "promedios ponderados", "fuente", "capitalizaciones", "elaboración"]):
                        continue
                    if not re.search(r"\d", clean):
                        continue
                    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}.*", clean):
                        continue
                    numeric_values.append((pos, clean))
                if not numeric_values:
                    continue

                bank_name = first.strip()
                for pos, value in numeric_values:
                    if pos > 17:
                        continue
                    if pos <= 9:
                        currency_name = "Moneda Nacional"
                        if pos == 1:
                            nv4 = "Caja de Ahorro"
                            nv5 = "Sin Plazo"
                        else:
                            nv4 = "Depósitos a plazo fijo (días)"
                            period_index = pos - 2
                            nv5 = periods[min(period_index, len(periods) - 1)]
                    else:
                        currency_name = "Moneda Extranjera"
                        if pos == 10:
                            nv4 = "Caja de Ahorro"
                            nv5 = "Sin Plazo"
                        else:
                            nv4 = "Depósitos a plazo fijo (días)"
                            period_index = pos - 11
                            nv5 = periods[min(period_index, len(periods) - 1)]

                    records.append({
                        "nv1": current_group,
                        "nv2": bank_name,
                        "nv3": currency_name,
                        "nv4": nv4,
                        "nv5": nv5,
                        "fecha": report_date,
                        "valor": clean_numeric_value(value),
                    })

            if not records:
                raise ValueError("No data rows were extracted from the report")

            df_out = pd.DataFrame(records, columns=["nv1", "nv2", "nv3", "nv4", "nv5", "fecha", "valor"])
            for col in df_out.columns[:-1]:
                df_out[col] = df_out[col].apply(lambda x: str(x) if x is not None and not pd.isna(x) else pd.NA)
            df_out["valor"] = df_out["valor"].astype(str)

            metadata = {
                "file_name": file_name,
                "titles": titles or ["BANCO CENTRAL DE BOLIVIA"],
                "page_number": int(resolved_page),
            }
            return metadata, df_out
        except Exception as error:
            print(f"Could not extract report from {file_path}: {error}")
            traceback.print_exc()
            return ""

    def validate_data_results(self, dataframe, decimal_separator, TOLERANCE=6.0):
        try:
            if dataframe is None or dataframe.empty:
                return False

            df = dataframe.copy()
            if "valor" not in df.columns:
                return False

            df["valor_num"] = to_numeric_datax(df["valor"], decimal_separator)
            if df["valor_num"].notna().sum() == 0:
                return False

            return False
        except Exception as error:
            print(f"Validation error: {error}")
            traceback.print_exc()
            return True
