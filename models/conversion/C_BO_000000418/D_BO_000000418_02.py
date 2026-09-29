from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import traceback
import fitz
import pandas as pd

from models.conversion.tools.conversion_tools import search_key_words, to_numeric_datax


class D_BO_000000418_02(Conversion_Base):

    def extraction(self, file_path, key_words, template_path="", page_number=1, format='%Y-%m-%d'):
        del template_path
        try:
            def normalize_text(value):
                if value is None or pd.isna(value):
                    return ""
                return str(value).strip()

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            file_name = os.path.basename(file_path)

            def clean_numeric_value(raw_value):
                if raw_value is None or pd.isna(raw_value):
                    return "0"
                value_str = str(raw_value).strip().replace(',', '.')
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
                    import traceback; traceback.print_exc()
                    return value_str

            def parse_report_date(df, text_context=""):
                m_fn = re.search(r'(\d{4}-\d{2}-\d{2})', file_name)
                if m_fn:
                    return m_fn.group(1)
                m_fn8 = re.search(r'(\d{8})', file_name)
                if m_fn8:
                    raw_date = m_fn8.group(1)
                    return f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"

                combined = text_context
                if df is not None and not df.empty:
                    combined += " " + " ".join(
                        " ".join(normalize_text(cell) for cell in row.tolist() if normalize_text(cell))
                        for _, row in df.iloc[:15].iterrows()
                    )
                match = re.search(r"al\s+(\d{1,2})\s+de\s+([A-Za-zÀ-ÿ]+)\s+de\s+(\d{4})", combined, flags=re.IGNORECASE)
                if match:
                    day = int(match.group(1))
                    month_name = match.group(2).lower()
                    year = int(match.group(3))
                    month_map = {
                        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5,
                        "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9,
                        "octubre": 10, "noviembre": 11, "diciembre": 12,
                    }
                    month = month_map.get(month_name)
                    if month:
                        return f"{year:04d}-{month:02d}-{day:02d}"
                return pd.Timestamp.now().strftime(format)

            def find_companion_pdf(src_file):
                if src_file.lower().endswith('.pdf') and os.path.exists(src_file):
                    return src_file

                candidates = []
                base_no_ext, _ = os.path.splitext(src_file)
                candidates.append(base_no_ext + '.pdf')

                file_dir = os.path.dirname(src_file) or '.'
                if os.path.exists(file_dir):
                    for f in os.listdir(file_dir):
                        if f.lower().endswith('.pdf'):
                            candidates.append(os.path.join(file_dir, f))

                mod_dir = os.path.dirname(__file__)
                if os.path.exists(mod_dir):
                    for f in os.listdir(mod_dir):
                        if f.lower().endswith('.pdf'):
                            candidates.append(os.path.join(mod_dir, f))

                base_fname = os.path.basename(src_file)
                m_date = re.search(r'(\d{4}-\d{2}-\d{2})', base_fname)
                dl_bases = ['/mnt/datos1/downloaded_files/BO/D_BO_000000418', r'\\10.0.0.16\downloaded_files\BO\D_BO_000000418']
                if 'data_process' in src_file:
                    dl_bases.append(re.sub(r'data_process.*', 'downloaded_files/BO/D_BO_000000418', src_file))

                for dl_base in dl_bases:
                    if os.path.exists(dl_base):
                        if m_date:
                            dt = m_date.group(1)
                            year, ym = dt[:4], dt[:7]
                            candidates.append(os.path.join(dl_base, year, ym, f"{dt}_tasas interbancarias.pdf"))
                            candidates.append(os.path.join(dl_base, year, ym, f"{dt}_tasas_interbancarias.pdf"))
                        for root, _, files in os.walk(dl_base):
                            for f in files:
                                if f.lower().endswith('.pdf'):
                                    if m_date and m_date.group(1) in f:
                                        candidates.append(os.path.join(root, f))
                                    elif 'actypas' in f.lower():
                                        candidates.append(os.path.join(root, f))

                for c in candidates:
                    if os.path.exists(c):
                        return c
                return None

            def identify_group(text):
                t = text.strip().upper()
                if 'MICROFINANZAS' in t:
                    return 'Entidades Especializadas en Microfinanzas'
                elif 'VIVIENDA' in t:
                    return 'Entidades Financieras de Vivienda'
                elif 'PYME' in t:
                    return 'Bancos PYME'
                elif 'COOPERATIVA' in t:
                    return 'Cooperativas'
                elif 'DESAR' in t:
                    return 'Instituciones Financieras de Desarrollo'
                elif 'BANCO' in t:
                    return 'Bancos Múltiples'
                return None

            raw_df = None
            resolved_page = int(page_number)
            is_pdf = file_path.lower().endswith('.pdf')
            pdf_page_text = ""

            if not is_pdf:
                excel = pd.ExcelFile(file_path)
                sheet_names = excel.sheet_names
                normalized_sheet_names = {str(name).upper(): name for name in sheet_names}
                preferred_sheet = normalized_sheet_names.get("PAS")
                if preferred_sheet is not None:
                    raw_df = pd.read_excel(file_path, sheet_name=preferred_sheet, header=None)
                    resolved_page = sheet_names.index(preferred_sheet) + 1
                elif key_words and str(key_words).strip():
                    for idx, sheet_name in enumerate(sheet_names):
                        df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
                        text = " ".join(str(value) for value in df.to_numpy().ravel() if str(value).strip())
                        if search_key_words(text=text, key_words=key_words) and "PASIVAS" in text.upper():
                            raw_df = df
                            resolved_page = idx + 1
                            break

                if raw_df is None:
                    # Excel has no PAS sheet. Fall back to companion PDF
                    companion_pdf = find_companion_pdf(file_path)
                    if companion_pdf:
                        is_pdf = True
                        file_path = companion_pdf
                    else:
                        target_index = max(0, min(int(page_number) - 1, len(sheet_names) - 1))
                        raw_df = pd.read_excel(file_path, sheet_name=sheet_names[target_index], header=None)
                        resolved_page = target_index + 1

            if is_pdf:
                doc = fitz.open(file_path)
                # Tasas Pasivas is on Page 2 (index 1)
                p_idx = 1 if len(doc) >= 2 else 0
                page_obj = doc[p_idx]
                pdf_page_text = page_obj.get_text()
                tables = page_obj.find_tables().tables
                if not tables:
                    raise ValueError(f"No tables found on page {p_idx + 1} of {file_path}")
                raw_df = tables[0].to_pandas()
                if raw_df.shape[1] == 22:
                    raw_df = raw_df.drop(columns=[raw_df.columns[1]])
                resolved_page = p_idx + 1

            report_date = parse_report_date(raw_df, pdf_page_text)

            titles = []
            if is_pdf:
                week_match = re.search(r"Semana\s+del.*", pdf_page_text, re.IGNORECASE)
                week_title = week_match.group(0).strip() if week_match else f"Semana al {report_date}"
                titles = [
                    "BANCO CENTRAL DE BOLIVIA",
                    "INFORMACIÓN SOBRE EL INTERÉS QUE PERCIBEN LOS AHORRISTAS POR SUS DEPÓSITOS",
                    week_title,
                    "TASAS PASIVAS EFECTIVAS*"
                ]
            else:
                for _, row in raw_df.iterrows():
                    text = " ".join(normalize_text(cell) for cell in row.tolist() if normalize_text(cell))
                    if not text:
                        continue
                    if any(token in text.upper() for token in ["BANCO CENTRAL", "INFORMACIÓN SOBRE", "TASAS PASIVAS", "SEMANA DEL", "INTERÉS QUE PERCIBEN"]):
                        titles.append(text)
                    if "BANCOS MÚLTIPLES" in text.upper() or "BANCOS MULTIPLES" in text.upper():
                        break
                if len(titles) < 4:
                    titles = [
                        "BANCO CENTRAL DE BOLIVIA",
                        "INFORMACIÓN SOBRE EL INTERÉS QUE PERCIBEN LOS AHORRISTAS POR SUS DEPÓSITOS",
                        f"Semana al {report_date}",
                        "TASAS PASIVAS*"
                    ]

            periods = ["30", "60", "90", "180", "360", "720", "1080", "Mayor"]
            footer_markers = (
                "VIGENTE DESDE", "PROMEDIOS PONDERADOS", "FUENTE", "TASAS EFECTIVAS",
                "CAPITALIZACIONES", "ELABORACIÓN", "BANCO CENTRAL"
            )
            records = []
            current_group = "Bancos Múltiples"

            for idx in range(len(raw_df)):
                row = raw_df.iloc[idx].tolist()
                first = normalize_text(row[0])
                if not first:
                    continue
                upper_first = first.upper()

                if any(token in upper_first for token in ["BANCO CENTRAL", "INFORMACIÓN SOBRE", "TASAS PASIVAS", "SEMANA DEL", "INTERÉS QUE PERCIBEN", "MONEDA NACIONAL", "MONEDA EXTRANJERA", "CAJA DE AHORRO", "DEPOSITOS A PLAZO"]):
                    continue
                if any(marker in upper_first for marker in footer_markers):
                    continue
                if upper_first in {"ENTIDADES", "ENTIDAD", "30", "60", "90", "180", "360", "720", "1080", "MAYOR"} or re.fullmatch(r"\d+", upper_first):
                    continue

                grp = identify_group(first)
                if grp:
                    if grp == "Bancos Múltiples" and current_group == "Entidades Especializadas en Microfinanzas":
                        pass
                    else:
                        current_group = grp
                        continue

                numeric_values = []
                for pos, value in enumerate(row[1:], start=1):
                    if value is None or pd.isna(value):
                        continue
                    clean = str(value).strip().replace(',', '.')
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
                    if pos > 18:
                        continue
                    if pos <= 9:
                        currency_name = "Moneda Nacional"
                        if pos == 1:
                            nv4 = "Caja de Ahorro"
                            nv5 = "Sin Plazo"
                        else:
                            nv4 = "Depósitos a Plazo Fijo (Días)"
                            period_index = pos - 2
                            nv5 = periods[min(period_index, len(periods) - 1)]
                    elif pos <= 18:
                        currency_name = "Moneda Extranjera"
                        if pos == 10:
                            nv4 = "Caja de Ahorro"
                            nv5 = "Sin Plazo"
                        else:
                            nv4 = "Depósitos a Plazo Fijo (Días)"
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

Executor_D_BO_000000418_02 = D_BO_000000418_02
Robot = D_BO_000000418_02
