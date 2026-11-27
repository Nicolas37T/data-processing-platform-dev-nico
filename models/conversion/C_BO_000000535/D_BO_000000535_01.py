from models.conversion.Conversion_Base import Conversion_Base
import pandas as pd
import os
from datetime import datetime
from models.conversion.tools.conversion_tools import to_numeric_datax,get_xlsx_report_dataframe

class D_BO_000000535_01(Conversion_Base):

    def extraction(self, file_path: str, key_words: str, template_path: str, page_number: int, format: str = "%Y-%m-%d"):
        """
            Extract banking data from Excel file and convert to required format.
            You need install xlrd -> pip install xlrd 

            Parameters:
                file_path (str): Path to the Excel file to be processed.
                key_words (str): Keywords to identify relevant sections in the document.
                template_path (str): Path to the Excel template used for validation.
                page_number (int): Page number to process from the Excel file.
                format (str): Date format to use when converting dates (default: '%Y-%m-%d').

            Returns:
                tuple: A tuple containing metadata dict and DataFrame, or empty string if fails.

        """
        try:
            file_name = os.path.basename(file_path)
            
            # Get the worksheet read excel 
            raw_df = pd.read_excel(file_path, header=None, engine='xlrd' if file_path.endswith('.xls') else None)

            # Clean empty rows and sparse columns
            raw_df = raw_df.dropna(how='all', axis=0).reset_index(drop=True)
            threshold = len(raw_df) * 0.1
            raw_df = raw_df.dropna(thresh=threshold, axis=1)

            # Extract titles from first 3 rows
            titles = []
            for i in range(min(3, len(raw_df))):
                if raw_df.iloc[i].dropna().any():
                    title = ' '.join(
                        str(x) for x in raw_df.iloc[i].dropna() if str(x).strip())
                    if title.strip():
                        titles.append(title.strip())

            # Data starts after titles
            data_df = raw_df.iloc[3:].reset_index(drop=True)

            # Get date and semana rows
            dates_row = data_df.iloc[0]
            semana_row = data_df.iloc[1]

            # Process date and semana mappings
            date_mapping = {}
            semana_mapping = {}

            for col_idx, (date_val, semana_val) in enumerate(zip(dates_row, semana_row)):
                if pd.notna(date_val):
                    if isinstance(date_val, datetime):
                        formatted_date = date_val.strftime(format)
                    else:
                        date_str = str(date_val)
                        if ' ' in date_str:
                            date_str = date_str.split(' ')[0]
                        try:
                            parsed_date = pd.to_datetime(date_str)
                            formatted_date = parsed_date.strftime(format)
                        except:
                            formatted_date = date_str
                    date_mapping[col_idx] = formatted_date

                if pd.notna(semana_val):
                    semana_mapping[col_idx] = str(semana_val)

            # Extract data records from row 2 onwards
            final_rows = []

            for row_idx in range(2, len(data_df)):
                row_data = data_df.iloc[row_idx]

                # Find municipio/agente name 
                municipio_name = None
                for value in row_data:
                    if pd.notna(value) and str(value).strip():
                        municipio_name = str(value).strip()
                        break

                if municipio_name is None:
                    continue

                # Extract values for each date/semana
                for col_idx in date_mapping.keys():
                    if col_idx < len(row_data):
                        valor = row_data.iloc[col_idx]
                        semana_val = semana_mapping.get(col_idx, '')

                        if pd.notna(valor) and str(valor).strip():
                            valor_str = str(valor).strip()

                            # Exclude metadata values
                            if (valor_str.lower() != municipio_name.lower()):
                                record = {
                                    'nv1': municipio_name,
                                    'nv2': semana_val,
                                    'fecha': date_mapping[col_idx],
                                    'valor': valor  # Keep original value
                                }
                                final_rows.append(record)

            # Create final DataFrame
            df_final = pd.DataFrame(final_rows)
            # Create metadata
            metadata = {
                "file_name": file_name,
                "titles": titles,
                "page_number": page_number
            }

            return (metadata, df_final)

        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"Error in extraction: {e}")
            return ""

    def validate_data_results(self, dataframe: pd.DataFrame, decimal_separator: str, TOLERANCE: float = 6.0) -> bool:
        """
        Validate extracted data for consistency and numeric integrity.
            
        Parameters:
            dataframe (pd.DataFrame): DataFrame structured according to DATAX Conversion Manual.
            decimal_separator (str): Character representing decimal separator ('.' or ',').
            TOLERANCE (float): Acceptable error margin for validations (default: 6.0).
            
        Returns:
            bool: True if validation failed, False if passed or no validations to perform.
        """
        try:
            if dataframe.empty:
                print("DataFrame is empty - no validation needed")
                return False

            # Identify value column
            valor_col = 'valor' if 'valor' in dataframe.columns else dataframe.columns[-1]

            if valor_col not in dataframe.columns:
                print("No value column found for validation")
                return False

            # Convert values to numeric
            numeric_values = to_numeric_datax(
                dataframe[valor_col], decimal_separator)

            # Check for non-numeric values
            non_numeric_mask = numeric_values.isna() & dataframe[valor_col].notna()
            non_numeric_values = dataframe.loc[non_numeric_mask, valor_col]

            if not non_numeric_values.empty:
                print(
                    f"Warning: Found non-numeric values in {valor_col} column:")
                print(non_numeric_values.tolist())
                return True

            return False

        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"Error in validate_data_results: {e}")
            return True

Executor_D_BO_000000535_01 = D_BO_000000535_01
Robot = D_BO_000000535_01
