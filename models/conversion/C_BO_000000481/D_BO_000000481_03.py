import os
import re
import pdfplumber
import traceback
from datetime import datetime
from rapidfuzz import fuzz
import pandas as pd

from models.conversion.tools.conversion_tools import get_pdf_report_page, to_numeric_datax, verify_values, isLevel
from models.conversion.tools.text_normalization import Text_Normalization
from models.conversion.Conversion_Base import Conversion_Base


class D_BO_000000481_03(Conversion_Base):

    NV4_LIST = ['compra venta', 'reporto']
    TEMPLATE_DF_HEADERS = [
        ['1-15', '16-30', '31-45', '46-90', '91-135', '136-180', '181-270', '271-360', '361-540', '541-720', '721-1080', '1081-mas'],
        ['1-7', '8-15', '16-22', '23-30', '31-37', '38-45']
    ]

    # All valid nv5 levels = union of both header lists.
    # Used in structure_review so it never triggers false-positive structure-change
    # alerts on days where new trading ranges appear (which were absent yesterday).
    VALID_NV5 = [
        '1-15', '16-30', '31-45', '46-90', '91-135', '136-180',
        '181-270', '271-360', '361-540', '541-720', '721-1080', '1081-mas', '1081-más',
        '1-7', '8-15', '16-22', '23-30', '31-37', '38-45'
    ]

    def _build_section_df(self, rows, headers, nv4_label):
        """Convert a list of raw table rows into a melted DataFrame for one section."""
        col_names = ['nv1', 'nv2', 'nv3'] + headers
        df = pd.DataFrame(rows, columns=col_names)
        for col in ['nv1', 'nv2', 'nv3']:
            if col in df.columns:
                df[col] = df[col].ffill()
        df.insert(3, 'nv4', nv4_label)
        df = df.melt(id_vars=['nv1', 'nv2', 'nv3', 'nv4'], value_name='valor', var_name='nv5')
        return df

    def extraction(self, file_path, key_words, template_path='', page_number=1, format='%Y-%m-%d'):
        del template_path
        file_name = os.path.basename(file_path)
        re_date = r'(\d{1,2}\D\d{1,2}\D\d{4})'

        try:
            with pdfplumber.open(file_path) as pdf:
                page_to_extract = get_pdf_report_page(pdf=pdf, key_words=key_words, num_caracteres='ALL', page_number=page_number)

                # Locate "Rango" to anchor the crop area
                pivot_words = [w for w in page_to_extract.extract_words() if re.search(r'rango', w['text'], re.IGNORECASE)]
                if not pivot_words:
                    raise ValueError("The pivot corner 'Rango' was not found in the page.")
                PIVOT_CORNER = pivot_words[0]

                XO = ((PIVOT_CORNER['x0'] // 10) * 10) - 110
                TOP = PIVOT_CORNER['top']

                # Extract date and titles from the band above the table
                titles = [line["text"] for line in page_to_extract.within_bbox(
                    (XO, TOP - 10, page_to_extract.width, TOP + 15)
                ).extract_text_lines()]
                print(f"Titles extracted: {titles}")

                date_matches = [date_match.group() for title in titles if (date_match := re.search(re_date, title, re.IGNORECASE))]
                date_val = datetime.strptime(date_matches[0], '%d/%m/%Y') if date_matches else datetime.now()
                formated_date_str = date_val.strftime(format)

                # Extract table with pdfplumber — no Java required
                cropped = page_to_extract.crop((XO, TOP, page_to_extract.width, page_to_extract.height))
                table_data = cropped.extract_table()
                if not table_data:
                    raise ValueError("No table data found in the cropped area.")

                # Identify section boundaries
                rep_row_idx = None
                rep_header_idx = None
                for i, r in enumerate(table_data):
                    first_cell = str(r[0] or '').strip().lower()
                    joined = ' '.join(str(c or '') for c in r)
                    if first_cell == 'reporto':
                        rep_row_idx = i
                    if '1-7' in joined and '8-15' in joined:
                        rep_header_idx = i

                if rep_row_idx is None:
                    # Fallback if first cell didn't have 'reporto' directly
                    for i, r in enumerate(table_data):
                        if any('reporto' in str(c or '').lower() for c in r):
                            rep_row_idx = i
                            break

                compra_venta_rows = []
                headers_cv = self.TEMPLATE_DF_HEADERS[0]
                # COMPRA VENTA data rows are between row 3 and rep_row_idx
                end_cv = rep_row_idx if rep_row_idx is not None else len(table_data)
                for i in range(3, end_cv):
                    r = table_data[i]
                    clean_row = [None if (c is None or str(c).strip() == '') else str(c).strip() for c in r]
                    compra_venta_rows.append(clean_row[:3 + len(headers_cv)])

                reporto_rows = []
                headers_rep = self.TEMPLATE_DF_HEADERS[1]
                if rep_header_idx is not None:
                    # Dynamically map REPORTO columns by their header positions to avoid empty column offset shifts
                    header_row = table_data[rep_header_idx]
                    rep_col_map = {}
                    for c_idx, cell in enumerate(header_row):
                        txt = str(cell or '').strip()
                        if txt in headers_rep:
                            rep_col_map[txt] = c_idx

                    for i in range(rep_header_idx + 1, len(table_data)):
                        r = table_data[i]
                        first_cell = str(r[0] or '').strip().lower()
                        if 'nota:' in first_cell or 'mecanismo' in first_cell:
                            continue
                        nv1 = None if (r[0] is None or str(r[0]).strip() == '') else str(r[0]).strip()
                        nv2 = None if (r[1] is None or str(r[1]).strip() == '') else str(r[1]).strip()
                        nv3 = None if (r[2] is None or str(r[2]).strip() == '') else str(r[2]).strip()
                        vals = [
                            str(r[rep_col_map[h]]).strip() if (
                                rep_col_map.get(h) is not None
                                and rep_col_map[h] < len(r)
                                and r[rep_col_map[h]] is not None
                                and str(r[rep_col_map[h]]).strip() != ''
                            ) else None
                            for h in headers_rep
                        ]
                        reporto_rows.append([nv1, nv2, nv3] + vals)

                dfs = []
                if compra_venta_rows:
                    dfs.append(self._build_section_df(compra_venta_rows, headers_cv, 'compra venta'))
                if reporto_rows:
                    dfs.append(self._build_section_df(reporto_rows, headers_rep, 'reporto'))

                if not dfs:
                    raise ValueError("No data extracted from table.")

                df_combined = pd.concat(dfs, axis=0, ignore_index=True)
                # Strip '%' from valor values (e.g. '7.00%' -> '7.00')
                df_combined['valor'] = df_combined['valor'].apply(
                    lambda x: x.replace('%', '').strip() if isinstance(x, str) else x
                )
                # Filter out empty rows (only keep rows with actual traded values)
                df_combined = df_combined.dropna(subset=['valor'])
                df_combined.insert(len(df_combined.columns) - 1, column="fecha", value=formated_date_str)

                return ({
                    "file_name": file_name,
                    "titles": titles if titles else ["Tasas de Rendimiento Rango de Plazos en Dias"],
                    "page_number": int(page_to_extract.page_number)
                }, df_combined)

        except Exception as e:
            print(f"An error occurred: {e}")
            traceback.print_exc()
            return ""

    VALID_NV1 = ['BOB', 'USD', 'UFV', 'DMV']

    def structure_review(self, data_file: str, last_conversion_path: str):
        """
        Verifies structure against the template.
        - Validates fixed structural columns:
          * nv1: checked against VALID_NV1 (currencies)
          * nv4: checked against NV4_LIST ('compra venta', 'reporto')
          * nv5: checked against VALID_NV5 (the 18 BBV maturity ranges)
        - For nv2 (instruments) and nv3 (issuers): allows dynamic market variations
          without false-positive structure change alerts when new issuers trade.
        - Safely handles cases where template SQLite lacks 'columns_to_review' table.
        """
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

            try:
                columns_to_review_df = self.get_last_conversion_df(last_conversion_path=last_conversion_path, table_name='columns_to_review')
                columns_to_review = columns_to_review_df['column'].unique().tolist()
            except Exception as e:
                print(f"Warning: could not load 'columns_to_review' table from {last_conversion_path}: {e}")
                columns_to_review = [col for col in last_conversion_cols if str(col).startswith('nv')]

            if not columns_to_review:
                return data_file

            columns_to_review_without_date = [col for col in columns_to_review if not re.search(r'fecha', col)]

            for column in columns_to_review_without_date:
                if column == 'nv5':
                    valid_levels = self.VALID_NV5
                elif column == 'nv4':
                    valid_levels = self.NV4_LIST
                elif column == 'nv1':
                    valid_levels = self.VALID_NV1
                elif column in ['nv2', 'nv3']:
                    # Instruments (nv2) and Issuers (nv3) vary daily with market trading activity.
                    # Ensure they contain non-empty data without forcing identity with yesterday's trades.
                    empty_mask = data_df[column].isna() | (data_df[column].astype(str).str.strip() == '')
                    if empty_mask.all():
                        raise ValueError(f"Extraction error: Column '{column}' is entirely empty.")
                    continue
                else:
                    valid_levels = last_conversion_df[column].dropna().unique().tolist() if column in last_conversion_df.columns else []

                nv_mask = data_df.loc[:, column].apply(lambda x: isLevel(nv=valid_levels, text=x, percentage_simliraty=90))
                invalid = data_df.loc[~nv_mask, column].dropna()
                if not invalid.empty:
                    print(f"Error: The following values in column '{column}' do not match expected levels:")
                    print(invalid)
                    raise ValueError(f"Extraction error: Column '{column}' contains values that do not match the expected levels.")

            print("Structure verified successfully.")
            return data_file

        except ValueError as e:
            print(f"There might be a change in structure: {e}")
        except Exception as e:
            print("An error occurred during structure verification")
            traceback.print_exc()
        return ""

    def validate_data_results(self, dataframe: pd.DataFrame, decimal_separator: str, TOLERANCE: float = 6.0):
        try:
            if dataframe is None or dataframe.empty:
                return False

            cleaned_df = dataframe.copy()
            value_col = cleaned_df.columns[-1]
            cleaned_df[value_col] = to_numeric_datax(serie=cleaned_df[value_col], decimal_separator=decimal_separator)
            cleaned_df = cleaned_df.dropna(subset=[value_col])

            valid_nv4 = {v.lower() for v in self.NV4_LIST}
            invalid_nv4 = cleaned_df[~cleaned_df['nv4'].str.lower().str.strip().isin(valid_nv4)]['nv4'].dropna()
            if not invalid_nv4.empty:
                print(f"Validation failed: unexpected nv4 values: {invalid_nv4.unique().tolist()}")
                return True

            valid_nv5_lower = {v.lower() for v in self.VALID_NV5}
            invalid_nv5 = cleaned_df[~cleaned_df['nv5'].str.lower().str.strip().isin(valid_nv5_lower)]['nv5'].dropna()
            if not invalid_nv5.empty:
                print(f"Validation failed: unexpected nv5 range values: {invalid_nv5.unique().tolist()}")
                return True

            print("All validations passed.")
            return False

        except Exception as e:
            print(f"Validation failed: {e}")
            traceback.print_exc()
            return True


Robot = D_BO_000000481_03
