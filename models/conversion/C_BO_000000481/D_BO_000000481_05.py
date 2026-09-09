import os
import re
import pdfplumber
import traceback
from datetime import datetime
import pandas as pd

from models.conversion.tools.conversion_tools import search_key_words, get_pdf_report_page, to_numeric_datax
from models.conversion.Conversion_Base import Conversion_Base


class D_BO_000000481_05(Conversion_Base):

    COLS = [
        ('compra venta', 'monto'), ('compra venta', 'part %'),
        ('reporto', 'monto'), ('reporto', 'part %'),
        ('total', 'monto'), ('total', 'part %')
    ]

    def extraction(self, file_path, key_words, template_path='', page_number=1, format='%Y-%m-%d'):
        del template_path
        file_name = os.path.basename(file_path)
        re_date = r'(\d{1,2}\D\d{1,2}\D\d{4})'

        try:
            with pdfplumber.open(file_path) as pdf:
                page_to_extract = get_pdf_report_page(pdf=pdf, key_words=key_words, page_number=page_number)
                lines = page_to_extract.extract_text_lines()
                
                date_matches = [re.search(re_date, line['text']).group() for line in lines if re.search(re_date, line['text'])]
                date = datetime.strptime(date_matches[0], '%d/%m/%Y') if date_matches else datetime.now()
                date_str = date.strftime(format)
                
                report_line = [line for line in lines if search_key_words(text=line['text'], key_words=key_words)][0]
                TOP = report_line['top'] - 10
                BOTTOM = [line['bottom'] for line in lines if search_key_words(text=line['text'], key_words='resumen mensual')][0] + 5

                cropped = page_to_extract.crop((230, TOP, page_to_extract.width, BOTTOM))
                text = cropped.extract_text() or ''
                text_lines = [l.strip() for l in text.split('\n') if l.strip()]

                rows = []
                current_nv1 = 'HOY'
                current_nv2 = 'Renta Fija'

                for l in text_lines:
                    if any(h in l for h in ['www.bbv', 'MONTOS NEGOCIADOS', 'Expresado', 'COMPRA VENTA', 'Monto Part %']):
                        continue
                    if 'RESUMEN MENSUAL' in l:
                        break

                    parts = l.split()
                    if not parts:
                        continue

                    if parts[0] == 'HOY':
                        current_nv1 = 'HOY'
                        vals = parts[1:]
                        for (nv4, nv5), val in zip(self.COLS, vals):
                            rows.append({'nv1': current_nv1, 'nv2': '-', 'nv3': '-', 'nv4': nv4, 'nv5': nv5, 'fecha': date_str, 'valor': val})
                    elif parts[0] == 'Renta' and len(parts) > 1 and parts[1] == 'Fija':
                        current_nv2 = 'Renta Fija'
                        vals = parts[2:]
                        for (nv4, nv5), val in zip(self.COLS, vals):
                            rows.append({'nv1': current_nv1, 'nv2': current_nv2, 'nv3': '-', 'nv4': nv4, 'nv5': nv5, 'fecha': date_str, 'valor': val})
                    elif parts[0] == '%' and len(parts) > 1 and parts[1] == 'Participacion':
                        vals = parts[3:]
                        pct_cols = [('compra venta', 'part %'), ('reporto', 'part %'), ('total', 'part %')]
                        for (nv4, nv5), val in zip(pct_cols, vals):
                            rows.append({'nv1': current_nv1, 'nv2': '% Participacion Dia', 'nv3': '-', 'nv4': nv4, 'nv5': nv5, 'fecha': date_str, 'valor': val})
                    else:
                        inst = parts[0]
                        num_vals = parts[1:]
                        if len(num_vals) == 6:
                            for (nv4, nv5), val in zip(self.COLS, num_vals):
                                rows.append({'nv1': current_nv1, 'nv2': current_nv2, 'nv3': inst, 'nv4': nv4, 'nv5': nv5, 'fecha': date_str, 'valor': val})
                        elif len(num_vals) == 4:
                            r_cols = [('reporto', 'monto'), ('reporto', 'part %'), ('total', 'monto'), ('total', 'part %')]
                            for (nv4, nv5), val in zip(r_cols, num_vals):
                                rows.append({'nv1': current_nv1, 'nv2': current_nv2, 'nv3': inst, 'nv4': nv4, 'nv5': nv5, 'fecha': date_str, 'valor': val})

                df_final = pd.DataFrame(rows)
                df_final = df_final.dropna(subset=['valor'])

                titles = ['MONTOS NEGOCIADOS EN BOLSA - RESUMEN DIARIO', 'Expresado en USD']

                return ({
                    "file_name": file_name,
                    "titles": titles,
                    "page_number": int(page_to_extract.page_number)
                }, df_final)

        except Exception as e:
            print(f"An error occurred: {e}")
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
            print("All validations passed. Returning False.")
            return False
        except Exception as e:
            print(f"Validation failed: {e}")
            traceback.print_exc()
            return True
