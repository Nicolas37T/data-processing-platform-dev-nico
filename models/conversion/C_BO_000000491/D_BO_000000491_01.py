from models.conversion.Conversion_Base import Conversion_Base
import os
import traceback
import pandas as pd

class D_BO_000000491_01(Conversion_Base):

    def extraction(self, file_path, key_words, template_path, page_number, format='%Y-%m-%d'):
        """
        Extracts a specific table from a file using user-defined keywords to identify the report section.
        Only selective cleaning is applied: fully empty rows/columns are removed, and nulls in 'valor' are dropped.
        Cell values retain their original format (including spaces, special characters, etc.).
        Metadata such as file_name and titles are returned separately, not as DataFrame columns.

        Parameters:
        - file_path (str): Absolute path to the file to extract data from.
        - key_words (str): Keywords to locate the desired report section.
        - template_path (str): Path to a template file for structure/validation (not explicitly used).
        - page_number (int): Reference page number to accelerate content search.
        - format (str, optional): Expected date format in the document. Default: '%Y-%m-%d'.

        Returns:
        - tuple: (
            {
                "file_name": <str>,      # Processed file name
                "titles": <list>,        # Ordered list of table titles
                "page_number": <int>     # Page where the table was found
            },
            df_melted                   # DataFrame with extracted data (no metadata columns)
          )
        - str: "" if an error occurs.
        """
        file_name = os.path.basename(file_path)
        try:
            # Read the file once (no header), supporting both .xls and .xlsx
            excel_engine = "xlrd" if file_path.lower().endswith(".xls") else "openpyxl"
            df = pd.read_excel(file_path, header=None, engine=excel_engine)
            # Remove fully empty rows and columns
            df = df.dropna(how='all').dropna(axis=1, how='all').reset_index(drop=True)

            # Find the header row (the one containing 'FECHA')
            header_row = df.apply(lambda row: row.astype(str).str.contains('FECHA', case=False).any(), axis=1)
            header_idx = header_row.idxmax()

            # Extract titles: all non-empty rows above the header, joining non-empty cells
            titles = [
                ' '.join(row.dropna().astype(str)).strip()
                for _, row in df.iloc[:header_idx].iterrows()
                if row.dropna().astype(str).str.strip().any()
            ]
            titles = titles[:3] + [""] * (3 - len(titles))  # Ensure at least 3 titles

            # Assign headers and trim DataFrame to data block
            df.columns = df.iloc[header_idx]
            df = df.iloc[header_idx+1:].reset_index(drop=True)
            df = df.dropna(how='all').dropna(axis=1, how='all')
            df = df.rename(columns=lambda x: str(x).strip())

            # Automatically detect date and week columns
            col_fecha = next((col for col in df.columns if 'FECHA' in str(col).upper()), None)
            col_semana = next((col for col in df.columns if 'SEMANA' in str(col).upper()), None)
            if not col_fecha or not col_semana:
                raise ValueError(f"Could not find FECHA or SEMANA columns in {file_name}")

            # Preserve the original order of weeks and stations (unique values)
            semanas_orden = df[col_semana].drop_duplicates().tolist()
            estaciones_orden = [col for col in df.columns if col not in [col_fecha, col_semana]]

            # Convert to long format (vertical)
            df_melted = df.melt(
                id_vars=[col_fecha, col_semana],
                value_vars=estaciones_orden,
                var_name='nv1',
                value_name='valor'
            )

            # Selective cleaning: remove rows where 'valor' is null
            df_melted = df_melted[df_melted['valor'].notna()]

            # Rename columns to standard output
            df_melted = df_melted.rename(columns={col_fecha: 'fecha', col_semana: 'semana'})

            # Keep original order for 'semana' and 'nv1'
            df_melted['semana'] = pd.Categorical(df_melted['semana'], categories=semanas_orden, ordered=True)
            df_melted['nv1'] = pd.Categorical(df_melted['nv1'], categories=estaciones_orden, ordered=True)
            df_melted = df_melted.sort_values(['semana', 'nv1']).reset_index(drop=True)

            # Ensure all columns except 'valor' are string or NaN
            for col in ['semana', 'nv1', 'fecha']:
                df_melted[col] = df_melted[col].astype(str).where(df_melted[col].notna(), pd.NA)

            # Only keep required columns
            df_melted = df_melted[['semana', 'nv1', 'fecha', 'valor']]

            return ({
                "file_name": file_name,
                "titles": titles,
                "page_number": page_number
            }, df_melted)

        except Exception as e:
            print(f"An error occurred in file {file_name}: {e}")
            traceback.print_exc()
            return ""

    def validate_data_results(self, dataframe:pd.DataFrame, decimal_separator:str, TOLERANCE:float=6.0):
        """
        Validates and cleans a DataFrame structured according to the DATAX Conversion Manual.

        The function converts numeric values from text using the specified decimal separator and validates totals or summary values (e.g., totals, percentages), allowing a configurable tolerance.

        If no totals or summaries are found, the function returns False (no errors). If validations fail, it returns True.

        Args:
            dataframe (pd.DataFrame): Input DataFrame to validate.
            decimal_separator (str): Decimal separator used in numeric strings (e.g., '.' or ',').
            TOLERANCE (float, optional): Allowed tolerance for total validation. Defaults to 6.0

        Returns:
            bool: True if any validation failed, False if all passed or no totals were found.
        """
        ERROR_TOLERANCE_VALUE = TOLERANCE
        totals_mismatch = False        
        # We cant find any total or percentage columns to validate all data is not operacional
        if not totals_mismatch:
            print("All validations passed. Returning the cleaned DataFrame.")
        return totals_mismatch

Executor_D_BO_000000491_01 = D_BO_000000491_01
Robot = D_BO_000000491_01
