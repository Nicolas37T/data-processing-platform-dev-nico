from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import traceback
import pandas as pd
from datetime import datetime
from models.download.tools.download_tools import read_excel
from models.conversion.tools.conversion_tools import format_date, to_numeric_datax


class D_BO_000000486_01(Conversion_Base):

    def extraction(self, file_path: str, key_words: str, template_path: str = "", page_number: int = 1, format: str = "%Y-%m-%d") -> tuple:
        """
        Extracts tabular data from CNDC Despacho de Carga Realizado Excel report.

        Parameters:
            file_path (str): Path to the report file.
            key_words (str): Search keywords (unused for direct Excel).
            template_path (str, optional): Path to template file. Defaults to "".
            page_number (int, optional): Page reference number. Defaults to 1.
            format (str, optional): Date format for the output. Defaults to '%Y-%m-%d'.

        Returns:
            tuple: (metadata_dict, df_melted)
        """
        file_name = os.path.basename(file_path)

        try:
            # Extract date from file_name (YYYY-MM-DD or DD-MM-YYYY)
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", file_name)
            if date_match:
                formated_date = format_date(date_match.group(1))
            elif (date_match := re.search(r"(\d{2})[-_](\d{2})[-_](\d{4})", file_name)):
                d = date_match.groups()
                formated_date = format_date(f"{d[2]}-{d[1]}-{d[0]}")
            else:
                formated_date = format_date(datetime.today().strftime("%Y-%m-%d"))

            # Read Excel file and remove entirely empty rows/columns
            df = read_excel(file_name=file_path)
            df = df.dropna(how='all').dropna(axis=1, how='all').reset_index(drop=True)

            # Locate header row containing hours or tecnología
            header_row = 0
            for idx, row in df.iterrows():
                row_strs = [str(x).lower() for x in row.dropna()]
                if any('01:00' in x for x in row_strs) or any('tecnolog' in x for x in row_strs):
                    header_row = idx
                    break

            df.columns = df.iloc[header_row]
            df = df.iloc[header_row + 1:].reset_index(drop=True)

            col_tec = df.columns[0]
            col_uni = df.columns[1]

            # Identify hourly columns (01:00 to 24:00)
            hour_cols = [c for c in df.columns[2:] if re.search(r'\d{1,2}:\d{2}', str(c))]

            df_clean = df[[col_tec, col_uni] + hour_cols].copy()
            df_clean = df_clean.rename(columns={col_tec: 'nv1', col_uni: 'nv2'})
            df_clean = df_clean.dropna(subset=['nv1', 'nv2'], how='all')

            # Unpivot hourly data to long format
            df_melted = df_clean.melt(
                id_vars=['nv1', 'nv2'],
                value_vars=hour_cols,
                var_name='hora',
                value_name='valor'
            )

            # Standardize hora (preserve 24:00 properly)
            df_melted['hora'] = df_melted['hora'].apply(
                lambda h: '24:00' if str(h).strip().startswith('24:00')
                else (pd.to_datetime(h, format='%H:%M', errors='coerce').strftime('%H:%M') if pd.notna(h) else str(h))
            )

            # Ensure numeric valor
            df_melted['valor'] = to_numeric_datax(serie=df_melted['valor'], decimal_separator=".")
            df_melted = df_melted.dropna(subset=['valor'])

            # Add fecha as the penultimate column
            df_melted.insert(len(df_melted.columns) - 1, column='fecha', value=formated_date.strftime(format))

            titles = ["DESPACHO DE CARGA REALIZADO (MW)"]

            return ({
                "file_name": file_name,
                "titles": titles,
                "page_number": int(page_number)
            }, df_melted)

        except Exception as e:
            print(f"An error occurred during extraction: {e}")
            traceback.print_exc()
            return ()

    def validate_data_results(self, dataframe: pd.DataFrame, decimal_separator: str = ".", TOLERANCE: float = 6.0) -> bool:
        """
        Validates mathematical consistency:
        Sum of technology subtotals (HIDRO + EOLICO + SOLAR + TERMO) == TOTAL.

        Returns:
            bool: False if validation succeeds (no errors), True if inconsistent.
        """
        try:
            df = dataframe.copy()
            df['valor'] = to_numeric_datax(serie=df['valor'], decimal_separator=decimal_separator)

            totals = df[df['nv2'].astype(str).str.upper() == 'TOTAL']
            subtotals = df[df['nv2'].astype(str).str.contains(r'SUBTOTAL (?:HIDRO|EOLICO|SOLAR|TERMO)', case=False, regex=True)]

            if totals.empty or subtotals.empty:
                print("No total or subtotals found for validation.")
                return False

            piv_tot = totals.pivot_table(index='hora', values='valor', aggfunc='sum')
            piv_sub = subtotals.pivot_table(index='hora', values='valor', aggfunc='sum')

            diff = (piv_sub['valor'] - piv_tot['valor']).abs()
            max_diff = diff.max()
            print(f"Max validation difference across hours: {max_diff:.6f}")

            if max_diff > TOLERANCE:
                print(f"Validation failed: discrepancy {max_diff} exceeds tolerance {TOLERANCE}")
                return True

            print("All totals validated: no discrepancies found.")
            return False

        except Exception as e:
            print(f"Validation error: {e}")
            traceback.print_exc()
            return True


Executor_D_BO_000000486_01 = D_BO_000000486_01
Robot = D_BO_000000486_01
