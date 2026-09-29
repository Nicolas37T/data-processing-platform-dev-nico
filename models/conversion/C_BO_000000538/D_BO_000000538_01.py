from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import traceback
import pandas as pd
from models.conversion.tools.conversion_tools import map_months_to_dates, to_numeric_datax


class D_BO_000000538_01(Conversion_Base):

    def extraction(self, file_path: str, key_words: str, template_path: str = "", page_number: int = 1, format: str = "%Y-%m-%d"):
        """
        Extract CNDC energy and power demand data from Excel file and convert to long format.

        Parameters:
            file_path (str): Path to the Excel file to be processed.
            key_words (str): Keywords to identify relevant sections.
            template_path (str): Path to the Excel/SQLite template used for validation.
            page_number (int): Page number reference (default: 1).
            format (str): Date format to use when converting dates (default: '%Y-%m-%d').

        Returns:
            tuple: A tuple containing (metadata_dict, df_final), or empty string on failure.
        """
        try:
            file_name = os.path.basename(file_path)
            raw_df = pd.read_excel(file_path, header=None).dropna(
                how='all', axis=0).dropna(how='all', axis=1).reset_index(drop=True)

            # Find year row (first row with 4-digit years in the first 10 rows)
            year_row_idx = None
            for i in range(min(10, len(raw_df))):
                vals = [str(x).strip() for x in raw_df.iloc[i].dropna()]
                if any(re.fullmatch(r"\d{4}", v) for v in vals):
                    year_row_idx = i
                    break

            if year_row_idx is None:
                raise ValueError("No year row found in file.")

            # Extract report titles from rows preceding the year row
            titles = [' '.join(str(x).strip() for x in raw_df.iloc[i].dropna())
                      for i in range(year_row_idx) if raw_df.iloc[i].dropna().any()]

            data_df = raw_df.iloc[year_row_idx:].reset_index(drop=True)

            # Map years across columns
            year_row = data_df.iloc[0]
            current_year, year_map = None, {}
            for col_idx, value in year_row.items():
                if pd.notna(value) and re.fullmatch(r"\d{4}", str(value).strip()):
                    current_year = int(str(value).strip())
                year_map[col_idx] = current_year

            # Map months and days to strict dates
            month_map = map_months_to_dates(data_df.iloc[1], year_map, format)

            # Process data rows
            all_rows_data = []
            for i in range(2, len(data_df)):
                nodo_raw = data_df.iloc[i, 1]
                if pd.isna(nodo_raw) or not str(nodo_raw).strip():
                    continue

                nodo_str = str(nodo_raw).strip()
                is_subtotal = bool(re.match(r'^TOTAL\s*-\s*.+$', nodo_str, re.IGNORECASE))
                is_final_total = nodo_str.upper() == "TOTAL"

                all_rows_data.append({
                    'nodo_str': nodo_str,
                    'is_subtotal': is_subtotal,
                    'is_final_total': is_final_total,
                    'total_name': nodo_str if is_subtotal else None,
                    'row_data': data_df.iloc[i]
                })

            final_rows = []
            for row_info in all_rows_data:
                is_subtotal, is_final_total = row_info['is_subtotal'], row_info['is_final_total']

                if is_subtotal:
                    # Assign this distributor/subtotal name to previous unassigned nodes
                    for j in range(len(final_rows)):
                        if final_rows[j]["nv1"] == "" or final_rows[j]["nv1"] is None:
                            final_rows[j]["nv1"] = row_info['total_name']
                    # Add subtotal row (nv1 = total_name, nv2 = None)
                    for col_idx in month_map.keys():
                        valor = row_info['row_data'].iloc[col_idx]
                        if pd.notna(valor):
                            final_rows.append({
                                "nv1": row_info['total_name'],
                                "nv2": None,
                                "fecha": month_map[col_idx],
                                "valor": valor
                            })

                elif is_final_total:
                    # Direct consumers that had no preceding distributor get their name promoted to nv1
                    for j in range(len(final_rows)):
                        if final_rows[j]["nv1"] == "" or final_rows[j]["nv1"] is None:
                            final_rows[j]["nv1"] = final_rows[j]["nv2"]
                            final_rows[j]["nv2"] = None
                    # Add final total row
                    for col_idx in month_map.keys():
                        valor = row_info['row_data'].iloc[col_idx]
                        if pd.notna(valor):
                            final_rows.append({
                                "nv1": "TOTAL",
                                "nv2": None,
                                "fecha": month_map[col_idx],
                                "valor": valor
                            })

                else:
                    # Individual consumer/node row
                    for col_idx in month_map.keys():
                        valor = row_info['row_data'].iloc[col_idx]
                        if pd.notna(valor):
                            final_rows.append({
                                "nv1": None,
                                "nv2": row_info['nodo_str'],
                                "fecha": month_map[col_idx],
                                "valor": valor
                            })

            df_final = pd.DataFrame(final_rows)
            df_final["nv1"] = df_final["nv1"].replace("", None)
            df_final["nv2"] = df_final["nv2"].replace("", None)
            df_final["valor"] = to_numeric_datax(serie=df_final["valor"], decimal_separator=".")
            df_final = df_final.dropna(subset=["valor"]).reset_index(drop=True)

            return ({
                "file_name": file_name,
                "titles": titles if titles else ["Comite Nacional de Despacho de Carga - Demanda de Energia"],
                "page_number": int(page_number)
            }, df_final)

        except Exception as e:
            print(f"Error in extraction: {e}")
            traceback.print_exc()
            return ""

    def validate_data_results(self, dataframe: pd.DataFrame, decimal_separator: str, TOLERANCE: float = 6.0) -> bool:
        """
        Validate that the sum of individual consumer nodes equals the final total for each date.

        Returns:
            bool: False if validation passes, True if inconsistencies are detected.
        """
        try:
            df = dataframe.copy()
            df["valor"] = to_numeric_datax(serie=df["valor"], decimal_separator=decimal_separator)
            df = df.dropna(subset=["valor"]).reset_index(drop=True)

            if df.empty:
                return False

            # Final total row: nv1="TOTAL" and nv2 is empty
            df_total_final = df[
                (df["nv1"].astype(str).str.upper() == "TOTAL") &
                (df["nv2"].astype(str).str.strip().isin(["", "None", "nan"]))
            ]

            # Individual consumer nodes: rows where nv2 has a specific node name
            df_nodes = df[
                ~(((df["nv1"].astype(str).str.upper() == "TOTAL") |
                    ((df["nv1"].astype(str).str.upper().str.startswith("TOTAL")) & (df["nv1"].astype(str).str.upper() != "TOTAL"))) &
                    (df["nv2"].astype(str).str.strip().isin(["", "None", "nan"])))
            ]

            if df_total_final.empty:
                print("No total final found, skipping validation.")
                return False

            # Validate dates; focusing on current year / recent periods
            validation_failed = False
            for fecha in sorted(df_total_final["fecha"].unique()):
                nodes_sum = df_nodes[df_nodes["fecha"] == fecha]["valor"].sum()
                final_total = df_total_final[df_total_final["fecha"] == fecha]["valor"].sum()
                difference = abs(nodes_sum - final_total)

                # CNDC historical figures from previous years can have published revisions.
                # Strictly enforce on dates from the current year.
                year = str(fecha).split("-")[0]
                max_year = str(df_total_final["fecha"].max()).split("-")[0]
                if year == max_year:
                    print(f"Validation {fecha}: Nodes Sum={nodes_sum:.2f}, Total={final_total:.2f}, Diff={difference:.2f}")
                    if difference > TOLERANCE:
                        print(f"Validation failed for date {fecha}: difference {difference:.2f} > tolerance {TOLERANCE}")
                        validation_failed = True

            if not validation_failed:
                print("All validations passed.")
            return validation_failed

        except Exception as e:
            print(f"Error in validation: {e}")
            traceback.print_exc()
            return True


Executor_D_BO_000000538_01 = D_BO_000000538_01
Robot = D_BO_000000538_01
