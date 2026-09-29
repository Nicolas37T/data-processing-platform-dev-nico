import os
import re
import pdfplumber
import traceback
from datetime import datetime
from rapidfuzz import fuzz
import pandas as pd

from models.conversion.tools.conversion_tools import search_key_words, get_pdf_report_page, to_numeric_datax, verify_values, isLevel
from models.conversion.tools.text_normalization import Text_Normalization
from models.conversion.Conversion_Base import Conversion_Base


class D_BO_000000481_06(Conversion_Base):

    COLS = [
        ('compra venta', 'monto'), ('compra venta', 'part %'),
        ('reporto', 'monto'), ('reporto', 'part %'),
        ('total', 'monto'), ('total', 'part %')
    ]

    VALID_NV2 = ['TOTAL', 'Renta Fija', 'Renta Variable', '% Participacion Mes']
    VALID_NV3 = ['compra venta', 'reporto', 'total']
    VALID_NV4 = ['monto', 'part %']

    def extraction(self, file_path, key_words, template_path='', page_number=1, format='%Y-%m-%d'):
        del template_path
        file_name = os.path.basename(file_path)
        re_date = r'(\d{1,2}\D\d{1,2}\D\d{4})'

        try:
            with pdfplumber.open(file_path) as pdf:
                page_to_extract = get_pdf_report_page(pdf=pdf, key_words=key_words, num_caracteres='ALL', page_number=page_number)
                lines = page_to_extract.extract_text_lines()

                date_matches = [re.search(re_date, line['text']).group() for line in lines if re.search(re_date, line['text'])]
                date = datetime.strptime(date_matches[0], '%d/%m/%Y') if date_matches else datetime.now()
                date_str = date.strftime(format)

                report_line = [line for line in lines if search_key_words(text=line['text'], key_words=key_words)][0]
                TOP = report_line['top'] - 10
                BOTTOM = [line['bottom'] for line in lines if search_key_words(text=line['text'], key_words='resumen anual')][0] + 5

                cropped = page_to_extract.crop((230, TOP, page_to_extract.width, BOTTOM))
                text = cropped.extract_text() or ''
                text_lines = [l.strip() for l in text.split('\n') if l.strip()]

                rows = []
                current_nv1 = 'MES'

                for l in text_lines:
                    if any(h in l for h in ['MONTOS NEGOCIADOS', 'Expresado', 'COMPRA VENTA', 'Monto Part %', '% Participacion Dia']):
                        continue
                    if 'RESUMEN ANUAL' in l:
                        break

                    parts = l.split()
                    if not parts:
                        continue

                    if parts[0] == 'MES':
                        current_nv1 = 'MES'
                        vals = parts[1:]
                        for (nv3, nv4), val in zip(self.COLS, vals):
                            rows.append({'nv1': current_nv1, 'nv2': 'TOTAL', 'nv3': nv3, 'nv4': nv4, 'fecha': date_str, 'valor': val})
                    elif parts[0] == 'Renta' and len(parts) > 1 and parts[1] == 'Fija':
                        vals = parts[2:]
                        for (nv3, nv4), val in zip(self.COLS, vals):
                            rows.append({'nv1': current_nv1, 'nv2': 'Renta Fija', 'nv3': nv3, 'nv4': nv4, 'fecha': date_str, 'valor': val})
                    elif parts[0] == 'Renta' and len(parts) > 1 and parts[1] == 'Variable':
                        vals = parts[2:]
                        for (nv3, nv4), val in zip(self.COLS, vals):
                            rows.append({'nv1': current_nv1, 'nv2': 'Renta Variable', 'nv3': nv3, 'nv4': nv4, 'fecha': date_str, 'valor': val})
                    elif parts[0] == '%' and len(parts) > 1 and parts[1] == 'Participacion':
                        vals = parts[3:]
                        pct_cols = [('compra venta', 'part %'), ('reporto', 'part %'), ('total', 'part %')]
                        for (nv3, nv4), val in zip(pct_cols, vals):
                            rows.append({'nv1': current_nv1, 'nv2': '% Participacion Mes', 'nv3': nv3, 'nv4': nv4, 'fecha': date_str, 'valor': val})

                df_final = pd.DataFrame(rows)
                # Strip '%' from valor values (e.g. '100.00%' -> '100.00')
                df_final['valor'] = df_final['valor'].apply(
                    lambda x: x.replace('%', '').strip() if isinstance(x, str) else x
                )
                # Drop empty rows
                df_final = df_final.dropna(subset=['valor'])

                titles = ['MONTOS NEGOCIADOS EN BOLSA - RESUMEN MENSUAL', 'Expresado en USD']

                return ({
                    "file_name": file_name,
                    "titles": titles,
                    "page_number": int(page_to_extract.page_number)
                }, df_final)

        except Exception as e:
            print(f"An error occurred: {e}")
            traceback.print_exc()
            return ""

    def structure_review(self, data_file: str, last_conversion_path: str):
        """
        Verifies structure against template.
        For nv2, checks against VALID_NV2 so reappearing 'Renta Variable'
        rows do not trigger false-positive structure-change alerts.
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
                if column == 'nv2':
                    valid_levels = self.VALID_NV2
                elif column == 'nv3':
                    valid_levels = self.VALID_NV3
                elif column == 'nv4':
                    valid_levels = self.VALID_NV4
                else:
                    valid_levels = last_conversion_df[column].dropna().unique().tolist()

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

            valid_nv2_lower = {v.lower() for v in self.VALID_NV2}
            invalid_nv2 = cleaned_df[~cleaned_df['nv2'].str.lower().str.strip().isin(valid_nv2_lower)]['nv2'].dropna()
            if not invalid_nv2.empty:
                print(f"Validation failed: unexpected nv2 values: {invalid_nv2.unique().tolist()}")
                return True

            valid_nv3_lower = {v.lower() for v in self.VALID_NV3}
            invalid_nv3 = cleaned_df[~cleaned_df['nv3'].str.lower().str.strip().isin(valid_nv3_lower)]['nv3'].dropna()
            if not invalid_nv3.empty:
                print(f"Validation failed: unexpected nv3 values: {invalid_nv3.unique().tolist()}")
                return True

            valid_nv4_lower = {v.lower() for v in self.VALID_NV4}
            invalid_nv4 = cleaned_df[~cleaned_df['nv4'].str.lower().str.strip().isin(valid_nv4_lower)]['nv4'].dropna()
            if not invalid_nv4.empty:
                print(f"Validation failed: unexpected nv4 values: {invalid_nv4.unique().tolist()}")
                return True

            print("All validations passed.")
            return False

        except Exception as e:
            print(f"Validation failed: {e}")
            traceback.print_exc()
            return True


Robot = D_BO_000000481_06
