from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import traceback
import sqlite3
from typing import Tuple
import pandas as pd
import pdfplumber
from rapidfuzz import fuzz

from models.conversion.tools.conversion_tools import to_numeric_datax, verify_levels, verify_values
from models.conversion.tools.text_normalization import Text_Normalization



class D_BO_000000038_01(Conversion_Base):
    """
    DATAX Conversion Robot for Report D_BO_000000038_01:
    Resultados de Subasta Bonos del Tesoro General de la Nacion (TGN) - BCB.
    """

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d"
    ) -> Tuple[dict, pd.DataFrame]:
        """
        Extracts auction results from the PDF into the official DATAX hierarchical DataFrame.

        Returns:
            Tuple[dict, pd.DataFrame]: (metadata_dict, df_melted)
        """
        try:
            file_name = os.path.basename(file_path)

            # 1. Read all text lines from PDF pages
            text_lines = []
            with pdfplumber.open(file_path) as pdf:
                page_idx = max(0, int(page_number) - 1) if page_number else 0
                pages_to_process = [pdf.pages[page_idx]] if page_idx < len(pdf.pages) else pdf.pages
                for p in pages_to_process:
                    for line_obj in p.extract_text_lines():
                        txt = line_obj.get("text", "").strip()
                        if txt:
                            text_lines.append(txt)

            if not text_lines:
                return {"file_name": file_name, "titles": [], "page_number": int(page_number)}, pd.DataFrame()

            # 2. Extract Header Titles and Metadata
            report_title = None
            for line in text_lines:
                if "RESULTADOS DE SUBASTA" in line.upper():
                    report_title = line
                    break

            titles = []
            if report_title:
                titles.append(report_title)
            else:
                titles.append("RESULTADOS DE SUBASTA BONOS TGN")

            # Additional title elements from header lines
            for line in text_lines[:12]:
                if any(tag in line.upper() for tag in ["MODALIDAD COMPETITIVA", "TGN", "(EN MILES)"]):
                    if line not in titles:
                        titles.append(line)

            # 3. Dynamic Resolution of Auction Cut Date
            cut_date = None
            for line in reversed(text_lines):
                m_date = re.search(r"Fecha:\s*(\d{1,2})/(\d{1,2})/(\d{4})", line, re.IGNORECASE)
                if m_date:
                    d, m, y = m_date.groups()
                    cut_date = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
                    break

            if not cut_date:
                m_file = re.search(r"(\d{4}-\d{2}-\d{2})", file_name)
                if m_file:
                    cut_date = m_file.group(1)
                else:
                    cut_date = pd.Timestamp.now().strftime(format)

            # 4. Dynamic Week and Year (semana_anio)
            semana_anio = None
            if report_title:
                m_week = re.search(r"(\d+)\s*/\s*(\d{4})", report_title)
                if m_week:
                    week_num, year_num = m_week.groups()
                    semana_anio = f"{year_num}-{week_num}"

            if not semana_anio:
                m_date_obj = pd.to_datetime(cut_date, errors="coerce")
                if pd.notna(m_date_obj):
                    iso_cal = m_date_obj.isocalendar()
                    semana_anio = f"{iso_cal.year}-{iso_cal.week}"
                else:
                    semana_anio = "2026-39"

            # 5. Currency Identification
            moneda = "MN"
            for line in text_lines[:15]:
                upper_line = line.upper()
                if "BOLIVIANOS" in upper_line:
                    moneda = "MN"
                    break
                elif "DOLARES" in upper_line or "DLARES" in upper_line or "USD" in upper_line:
                    moneda = "ME"
                    break
                elif "UFV" in upper_line:
                    moneda = "UFV"
                    break

            # 6. Parse Series Blocks and Bids
            records = []
            current_serie = None
            current_plazo = None
            current_trn = None
            current_ofertado = None
            reg_counter = 0

            for line in text_lines:
                # Stop parsing if footer / notes reached
                if any(marker in line for marker in ["Tasas promedio ponderada", "Motivo de rechazo", "Generado por", "SEOMA-"]):
                    current_serie = None
                    continue

                # Block Header 1: Cantidad Ofertada / Plazo
                m_of = re.search(r"Cantidad\s+Ofertada:\s*([\d\.,]+)\s+Plazo:\s*(\d+)", line, re.IGNORECASE)
                if m_of:
                    current_ofertado = m_of.group(1).strip()
                    current_plazo = f"{m_of.group(2).strip()} días"
                    reg_counter = 0
                    continue

                # Block Header 2: Serie / TRN
                m_se = re.search(r"Serie:\s*([A-Za-z0-9]+)(?:\s+TRN:\s*([\d\.,]+)\s*%)?", line, re.IGNORECASE)
                if m_se:
                    current_serie = m_se.group(1).strip()
                    current_trn = m_se.group(2).strip() if m_se.group(2) else None
                    continue

                if not current_serie:
                    continue

                # Case A: Regular bid line (Cantidad Demandada, Emisor, TRE(%), Cantidad Adjudicada, [Motivo Rechazo])
                m_bid = re.match(r"^([\d\.,]+)\s+([A-Za-z0-9]+)\s+([\d\.,]+)\s+([\d\.,]+)(?:\s+([A-Za-z0-9]+))?$", line)
                if m_bid:
                    reg_counter += 1
                    dem, emi, tr, adj, mot = m_bid.groups()
                    motivo = mot.strip() if mot else "N"
                    emisor = emi.strip()

                    # Emit standard hierarchical metric records
                    # 1. Monto Ofertado
                    records.append({
                        "nv1": moneda, "nv2": current_serie, "nv3": current_plazo, "nv4": semana_anio,
                        "nv5": emisor, "nv6": str(reg_counter), "nv7": motivo, "nv8": "Monto Ofertado",
                        "fecha": cut_date, "valor": current_ofertado
                    })
                    # 2. Monto Demandado
                    records.append({
                        "nv1": moneda, "nv2": current_serie, "nv3": current_plazo, "nv4": semana_anio,
                        "nv5": emisor, "nv6": str(reg_counter), "nv7": motivo, "nv8": "Monto Demandado",
                        "fecha": cut_date, "valor": dem
                    })
                    # 3. Tasa de Rendimiento (T.R. %)
                    records.append({
                        "nv1": moneda, "nv2": current_serie, "nv3": current_plazo, "nv4": semana_anio,
                        "nv5": emisor, "nv6": str(reg_counter), "nv7": motivo, "nv8": "T.R. %",
                        "fecha": cut_date, "valor": tr
                    })
                    # 4. Monto Adjudicado
                    records.append({
                        "nv1": moneda, "nv2": current_serie, "nv3": current_plazo, "nv4": semana_anio,
                        "nv5": emisor, "nv6": str(reg_counter), "nv7": motivo, "nv8": "Monto Adjudicado",
                        "fecha": cut_date, "valor": adj
                    })
                    # 5. TRN % (if present)
                    if current_trn:
                        records.append({
                            "nv1": moneda, "nv2": current_serie, "nv3": current_plazo, "nv4": semana_anio,
                            "nv5": emisor, "nv6": str(reg_counter), "nv7": motivo, "nv8": "TRN %",
                            "fecha": cut_date, "valor": current_trn
                        })
                    continue

                # Case B: Subtotal line: 1) 203.000 10,4500 3.000
                m_sub = re.match(r"^(?:1\)\s*)?([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)$", line)
                if m_sub:
                    dem_tot, tr_tot, adj_tot = m_sub.groups()
                    emisor = "TGN"

                    # Emit standard hierarchical total records
                    records.append({
                        "nv1": moneda, "nv2": current_serie, "nv3": current_plazo, "nv4": semana_anio,
                        "nv5": emisor, "nv6": "TOTAL", "nv7": "TOTAL", "nv8": "Monto Ofertado",
                        "fecha": cut_date, "valor": current_ofertado
                    })
                    records.append({
                        "nv1": moneda, "nv2": current_serie, "nv3": current_plazo, "nv4": semana_anio,
                        "nv5": emisor, "nv6": "TOTAL", "nv7": "TOTAL", "nv8": "Monto Demandado",
                        "fecha": cut_date, "valor": dem_tot
                    })
                    records.append({
                        "nv1": moneda, "nv2": current_serie, "nv3": current_plazo, "nv4": semana_anio,
                        "nv5": emisor, "nv6": "TOTAL", "nv7": "TOTAL", "nv8": "T.R. %",
                        "fecha": cut_date, "valor": tr_tot
                    })
                    records.append({
                        "nv1": moneda, "nv2": current_serie, "nv3": current_plazo, "nv4": semana_anio,
                        "nv5": emisor, "nv6": "TOTAL", "nv7": "TOTAL", "nv8": "Monto Adjudicado",
                        "fecha": cut_date, "valor": adj_tot
                    })
                    if current_trn:
                        records.append({
                            "nv1": moneda, "nv2": current_serie, "nv3": current_plazo, "nv4": semana_anio,
                            "nv5": emisor, "nv6": "TOTAL", "nv7": "TOTAL", "nv8": "TRN %",
                            "fecha": cut_date, "valor": current_trn
                        })

            if not records:
                return {"file_name": file_name, "titles": titles, "page_number": int(page_number)}, pd.DataFrame()

            df_melted = pd.DataFrame(records)

            # Ensure numeric conversion with standard decimal separator
            df_melted["valor"] = to_numeric_datax(df_melted["valor"], decimal_separator=",")

            # Ensure string or None data types for dimensional columns
            dim_columns = ["nv1", "nv2", "nv3", "nv4", "nv5", "nv6", "nv7", "nv8", "fecha"]
            for col in dim_columns:
                df_melted[col] = df_melted[col].where(df_melted[col].notna(), None).astype(str)

            metadata_dict = {
                "file_name": file_name,
                "titles": titles,
                "page_number": int(page_number)
            }

            return metadata_dict, df_melted

        except Exception as error:
            print(f"Error extracting report from {file_path}: {error}")
            traceback.print_exc()
            return "", pd.DataFrame()

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str = ",",
        TOLERANCE: float = 6.0
    ) -> bool:
        """
        Validates mathematical integrity and auction accounting consistency:
        1. Vertical Reconciliation for Monto Demandado:
           Sum of individual bids (nv6 != 'TOTAL') equals the serie TOTAL within TOLERANCE.
        2. Vertical Reconciliation for Monto Adjudicado:
           Sum of individual bids (nv6 != 'TOTAL') equals the serie TOTAL within TOLERANCE.
        3. Auction Ceiling Constraint:
           Total Adjudicated amount must not exceed Total Offered amount (within TOLERANCE).
        4. Numeric Completeness:
           Ensures that all extracted metric values are valid, finite numbers.

        Returns:
            False: Validation successful (clean, consistent data).
            True: Discrepancy detected.
        """
        try:
            if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return True
            if "valor" not in dataframe.columns or "fecha" not in dataframe.columns:
                return True

            df = dataframe.copy()
            if pd.api.types.is_numeric_dtype(df["valor"]):
                df["valor_num"] = df["valor"].astype(float)
            else:
                df["valor_num"] = to_numeric_datax(df["valor"], decimal_separator=decimal_separator)

            if df["valor_num"].isna().any():
                print("Validation failed: NaN values found in 'valor' column.")
                return True

            # Group by Serie (nv2) and Date (fecha)
            for (cut_date, serie), grp in df.groupby(["fecha", "nv2"]):
                # 1. Monto Demandado Reconciliation
                dem_bids = grp[(grp["nv8"] == "Monto Demandado") & (grp["nv6"] != "TOTAL")]
                dem_tot = grp[(grp["nv8"] == "Monto Demandado") & (grp["nv6"] == "TOTAL")]

                if not dem_bids.empty and not dem_tot.empty:
                    calc_dem = dem_bids["valor_num"].sum()
                    exp_dem = dem_tot["valor_num"].iloc[0]
                    diff_dem = abs(calc_dem - exp_dem)
                    if diff_dem > TOLERANCE:
                        print(
                            f"Validation error in serie '{serie}' ({cut_date}) - Monto Demandado: "
                            f"Sum of bids ({calc_dem:.2f}) != TOTAL ({exp_dem:.2f}), Diff={diff_dem:.2f}"
                        )
                        return True

                # 2. Monto Adjudicado Reconciliation
                adj_bids = grp[(grp["nv8"] == "Monto Adjudicado") & (grp["nv6"] != "TOTAL")]
                adj_tot = grp[(grp["nv8"] == "Monto Adjudicado") & (grp["nv6"] == "TOTAL")]

                if not adj_bids.empty and not adj_tot.empty:
                    calc_adj = adj_bids["valor_num"].sum()
                    exp_adj = adj_tot["valor_num"].iloc[0]
                    diff_adj = abs(calc_adj - exp_adj)
                    if diff_adj > TOLERANCE:
                        print(
                            f"Validation error in serie '{serie}' ({cut_date}) - Monto Adjudicado: "
                            f"Sum of bids ({calc_adj:.2f}) != TOTAL ({exp_adj:.2f}), Diff={diff_adj:.2f}"
                        )
                        return True

                # 3. Ceiling Constraint: Adjudicated <= Offered
                of_tot = grp[(grp["nv8"] == "Monto Ofertado") & (grp["nv6"] == "TOTAL")]
                if not adj_tot.empty and not of_tot.empty:
                    val_adj = adj_tot["valor_num"].iloc[0]
                    val_of = of_tot["valor_num"].iloc[0]
                    if val_adj > val_of + TOLERANCE:
                        print(
                            f"Validation error in serie '{serie}' ({cut_date}) - Ceiling violated: "
                            f"Adjudicated ({val_adj:.2f}) exceeds Offered ({val_of:.2f})"
                        )
                        return True

            return False

        except Exception as error:
            print(f"Validation exception occurred: {error}")
            traceback.print_exc()
            return True

    def structure_review(self, data_file: str, last_conversion_path: str) -> str:
        """Verify report structure against the last conversion, focusing on invariant dimensions nv1, nv5, nv8."""
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

            # Restrict verification to fixed structural levels (nv1: Moneda, nv5: Emisor, nv8: Métrica).
            # Dynamic levels (nv2: Serie, nv3: Plazo, nv4: Semana, nv6: Postura, nv7: Rechazo) vary each auction.
            columns_to_review = ['nv1', 'nv5', 'nv8']
            verify_levels(template_df=last_conversion_df, data_df=data_df, columns_to_review=columns_to_review)

            print("Structure verified successfully.")
            return data_file

        except ValueError as e:
            print(f"There might be a change in structure: {e}")
        except Exception as e:
            print("An error occurred during structure verification")
            traceback.print_exc()
        return ""

    def report_data_validation(self, *args, **kwargs):
        """Ensures columns_to_review in newly created SQLite only contains invariant structural levels nv1, nv5, nv8."""
        res = super().report_data_validation(*args, **kwargs)
        if isinstance(res, dict) and res.get("conversion_path") and res.get("file_extension") == "sqlite":
            try:
                conn = sqlite3.connect(res["conversion_path"])
                conn.execute("DELETE FROM columns_to_review WHERE column NOT IN ('nv1', 'nv5', 'nv8')")
                conn.commit()
                conn.close()
            except Exception:
                pass
        return res


Robot = D_BO_000000038_01
Executor_D_BO_000000038_01 = D_BO_000000038_01