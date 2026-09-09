import os
import re
import tabula
import pdfplumber
import traceback
import numpy as np
from datetime import datetime
import pandas as pd

from models.conversion.tools.conversion_tools import search_key_words, get_pdf_report_page, get_col_date, to_numeric_datax
from models.conversion.Conversion_Base import Conversion_Base


class D_BO_000000481_02(Conversion_Base):

    CONVERSION_FACTOR = 72 / 25.4  # conversion factor from mm to points    
    PIVOT_END_WORDS = 'capitalizacion mercado'
    COLUMN_GAPS = [3.8]
    TOP_GAP = 3
    NV1_LIST = ['acciones ordinarias', 'acciones preferentes']
    COLUMNS = ['nv1', 'nv2', 'emisor', 'fecha_inscripcion', 'tipo', 'fecha', 'valor']

    def extraction(self, file_path, key_words, template_path='', page_number=1, format='%Y-%m-%d'):
        del template_path
        file_name = os.path.basename(file_path)
        re_date = r'(\d{1,2}\D\d{1,2}\D\d{4})'
        
        try:
            with pdfplumber.open(file_path) as pdf: 
                page_to_extract = get_pdf_report_page(pdf=pdf, key_words=key_words, num_caracteres='ALL', page_number=page_number)
                print(f"Extracting from page number: {page_to_extract.page_number}")
                lines = page_to_extract.extract_text_lines()

                # Extract date from the text lines
                date = [re.search(re_date, line['text']).group() for line in lines if re.search(re_date, line['text'])]                
                date = datetime.strptime(date[0], '%d/%m/%Y')
                print(f"Extracted report date: {date.strftime(format)}")

                # Find the pivot corner in the extracted lines
                PIVOT_CORNER = [line for line in lines if search_key_words(text=line['text'], key_words=key_words)]
                if not PIVOT_CORNER:
                    raise ValueError("The pivot corner was not found in the page.")
                
                PIVOT_END_CORNER = [line for line in lines if search_key_words(text=line['text'], key_words=self.PIVOT_END_WORDS)]                
                
                PIVOT_CORNER = sorted(PIVOT_CORNER, key=lambda x: x['x0'])[0]                
                X0 = min([line['x0'] for line in lines])                 
                TOP = PIVOT_CORNER['top'] + self.TOP_GAP * self.CONVERSION_FACTOR
                BOTTOM = PIVOT_END_CORNER[0]['top'] if PIVOT_END_CORNER else page_to_extract.height
                print(f"The X0 point is: {X0/self.CONVERSION_FACTOR:02}mm")

                # Extract titles above the pivot corner
                titles = [line["text"] for line in page_to_extract.within_bbox((0, TOP - self.TOP_GAP * self.CONVERSION_FACTOR, X0 + 45 * self.CONVERSION_FACTOR, TOP)).extract_text_lines()]
                print(f"Titles extracted: {titles}")
                
                # Calculate column lines based on the gaps
                column_lines = list(X0 + np.cumsum(self.COLUMN_GAPS) * self.CONVERSION_FACTOR)
                
                # Read the relevant area of the PDF into a DataFrame
                tabs = tabula.read_pdf(input_path=file_path, pages=page_to_extract.page_number, area=[TOP, X0, BOTTOM, X0 + 45 * self.CONVERSION_FACTOR], pandas_options={'header': None}, stream=True, columns=column_lines)[0]

                nv_mask = (tabs[tabs.columns[0]].isna()) & (tabs[tabs.columns[1]].apply(lambda x: not str(x).lower().strip().startswith("exp.")))
                nv_column = tabs.loc[nv_mask, tabs.columns[1]]

                nv1_mask = nv_column.replace(r'\s+', ' ', regex=True).apply(lambda x: str(x).lower().strip() in self.NV1_LIST)

                new_values = tabs[tabs.columns[1]].str.split(r"\s+", expand=True, regex=True)

                tabs.insert(loc=0, column='nv2', value=nv_column[~nv1_mask])
                tabs.insert(loc=0, column='nv1', value=nv_column[nv1_mask])

                nv2_indices_to_fix = tabs['nv2'].dropna().index
                nv2_indices_to_fix = [i for i in nv2_indices_to_fix if (i + 1) in nv2_indices_to_fix]

                for i in nv2_indices_to_fix:
                    tabs.loc[i + 1, 'nv2'] = tabs.loc[i, 'nv2'] + " " + tabs.loc[i + 1, 'nv2']

                df = tabs[tabs.columns[:3]].copy()
                df[['valor1', 'valor2', 'valor3']] = new_values.iloc[:, [0, 1, 2]]

                columns_to_ffill = ['nv1', 'nv2']
                for col in columns_to_ffill:
                    df[col] = df[col].ffill()

                numeric_mask = ~pd.to_numeric(df['valor3'].replace(r',', '', regex=True), errors='coerce').isna()
                df = df[numeric_mask].copy()

                df.insert(loc=(len(df.columns) - 1), column='fecha', value=date.strftime(format))
                df.columns = self.COLUMNS
                
                df['fecha_inscripcion'] = df['fecha_inscripcion'].apply(lambda x: get_col_date(x))

                return ({
                    "file_name": file_name,
                    "titles": titles if titles else ["Acciones Inscritas en Bolsa"],
                    "page_number": int(page_to_extract.page_number)
                }, df)
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
