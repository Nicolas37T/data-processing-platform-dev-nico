from models.conversion.Conversion_Base import Conversion_Base
import pandas as pd
import os
import re
from typing import Tuple, Union
from models.conversion.tools.conversion_tools import get_xlsx_report_dataframe, to_numeric_datax, get_col_date

class D_BO_000000500_01(Conversion_Base):

    def extraction(self, file_path: str, key_words: str, template_path: str, page_number: int, format: str = "%Y-%m-%d") -> Union[Tuple[dict, pd.DataFrame], str]:
        """
        Extracts and processes data from an Excel file based on keywords.

        Parameters:
            file_path (str): Path to the Excel file
            key_words (str): Keywords to search for the start of the data
            template_path (str): Path to the template (currently unused)
            page_number (int): Page/sheet number
            format (str): Output date format

        Returns:
            tuple: (metadata, dataframe) or an empty string in case of an error
        """
        try:
            file_name = os.path.basename(file_path)

            # Get the worksheet using conversion_tools
            result = get_xlsx_report_dataframe(
                file_path, key_words, page_number)
            if not result:
                raise ValueError("Could not get worksheet from file.")

            raw_df, actual_page = result
            raw_df = raw_df.dropna(how='all', axis=0).dropna(
                how='all', axis=1).reset_index(drop=True)

            if raw_df.empty:
                raise ValueError("Extracted worksheet DataFrame is empty.")

            # Find hour row (row containing HORA or time patterns)
            hour_row_idx = None
            for i in range(len(raw_df)):
                row_strs = [str(val).strip().upper() for val in raw_df.iloc[i].dropna()]
                if any('HORA' in val for val in row_strs) or any(re.search(r'\d{1,2}:\d{2}', val) for val in row_strs):
                    hour_row_idx = i
                    break

            if hour_row_idx is None:
                raise ValueError("Hour row not found in the data.")

            # Extract titles from all rows before the hour row
            titles = []
            for i in range(hour_row_idx):
                title_row = raw_df.iloc[i].dropna().astype(str)
                if not title_row.empty:
                    title = ' '.join(title_row.values).strip()
                    if title:
                        titles.append(title)

            # Extract the date from filename or titles
            file_date_match = re.search(r'(\d{4}-\d{2}-\d{2})', file_name)
            if file_date_match:
                fecha = file_date_match.group(1)
            elif titles:
                fecha = get_col_date(titles[-1])
            else:
                raise ValueError("No titles or filename date found to extract the date.")

            # Extract hour columns - EXTRACT AS STRING WITHOUT CLEANING
            hour_row = raw_df.iloc[hour_row_idx]
            hour_columns = {}
            for col_idx, value in hour_row.items():
                if pd.notna(value):
                    value_str = str(value).strip()
                    # Look for time patterns in the strings (even if they have dates before)
                    has_time = re.search(
                        r'\d{1,2}:\d{2}(?::\d{2})?', value_str)
                    has_hour_number = re.match(
                        r'^\d{1,2}$', value_str) and value_str.isdigit() and 0 <= int(value_str) <= 24
                    if has_time or has_hour_number:
                        # Store the original string
                        hour_columns[col_idx] = value_str

            data_rows = raw_df.iloc[hour_row_idx + 1:].reset_index(drop=True)

            # Find special rows (3 rows before GENERACION TOTAL)
            total_row_indices = [i for i, row in data_rows.iterrows()
                                 if "GENERACION TOTAL" in str(row.iloc[0]).upper()]
            special_row_indices = set()
            for total_idx in total_row_indices:
                for offset in range(1, 4):
                    if total_idx - offset >= 0:
                        special_row_indices.add(total_idx - offset)

            final_data = []
            current_nv1 = ""

            for i, row in data_rows.iterrows():
                first_col_value = str(row.iloc[0]).strip(
                ) if pd.notna(row.iloc[0]) else ""

                if not first_col_value or first_col_value.lower() == 'nan':
                    continue

                is_region = False
                if len(row) > 1:
                    second_col_value = str(row.iloc[1]).strip(
                    ) if pd.notna(row.iloc[1]) else ""
                    if first_col_value and (not second_col_value or second_col_value.lower() == 'nan'):
                        is_region = True

                if is_region:
                    current_nv1 = first_col_value
                    continue

                # Check if this should go to nv1 (totals, perdidas, or special rows)
                is_total_or_perdidas = any(keyword in first_col_value.upper()
                                           for keyword in ['TOTAL', 'PERDIDAS'])
                is_special_generation = i in special_row_indices

                if is_total_or_perdidas or is_special_generation:
                    nv1_value, nv2_value = first_col_value, None
                else:
                    nv1_value, nv2_value = current_nv1, first_col_value

                # Extract values for each hour
                for col_idx, hora in hour_columns.items():
                    if col_idx < len(row):
                        valor = row.iloc[col_idx]

                        final_data.append({
                            'nv1': nv1_value,
                            'nv2': nv2_value,
                            'Hora': hora,
                            'fecha': fecha,
                            'valor': valor
                        })

            df_res = pd.DataFrame(final_data)
            df_res['nv1'] = df_res['nv1'].replace(r'^\s*$', None, regex=True)
            df_res['nv2'] = df_res['nv2'].replace(r'^\s*$', None, regex=True)

            return ({
                "file_name": file_name,
                "titles": titles,
                "page_number": actual_page
            }, df_res)

        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"Error in extraction: {e}")
            return ""

    def validate_data_results(self, dataframe: pd.DataFrame, decimal_separator: str, TOLERANCE: float = 1.0) -> bool:
        """
        Validate data integrity and coherence according to DATAX Conversion Manual.

        Parameters:
            dataframe (pd.DataFrame): DataFrame structured according to DATAX 
            decimal_separator: Character representing decimal separator (e.g., '.' or ',')

        Returns:
            bool: True if any validation failed or inconsistencies detected,
                  False if all validations successful
        """
        try:
            # Convert values to numeric using specified decimal separator
            numeric_values = to_numeric_datax(
                dataframe['valor'], decimal_separator)

            # Verify all values are numeric
            if numeric_values.isna().any():
                return True

            return False

        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"Error during validation: {e}")
            return True

Executor_D_BO_000000500_01 = D_BO_000000500_01
Robot = D_BO_000000500_01
