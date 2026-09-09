import os
import re
import tabula
import pdfplumber
import traceback
from datetime import datetime
import pandas as pd

from models.conversion.tools.conversion_tools import get_pdf_report_page, to_numeric_datax
from models.conversion.Conversion_Base import Conversion_Base


class D_BO_000000481_03(Conversion_Base):

    NV4_LIST = ['compra venta', 'reporto']
    TEMPLATE_DF_HEADERS = [
        ['1-15', '16-30', '31-45', '46-90', '91-135', '136-180', '181-270', '271-360', '361-540', '541-720', '721-1080', '1081-mas'],
        ['1-7', '8-15', '16-22', '23-30', '31-37', '38-45']
    ]

    def extraction(self, file_path, key_words, template_path='', page_number=1, format='%Y-%m-%d'):
        del template_path
        file_name = os.path.basename(file_path)
        re_date = r'(\d{1,2}\D\d{1,2}\D\d{4})'

        try:
            with pdfplumber.open(file_path) as pdf:
                page_to_extract = get_pdf_report_page(pdf=pdf, key_words=key_words, num_caracteres='ALL', page_number=page_number)              
                PIVOT_CORNER = [line for line in page_to_extract.extract_words() if re.search(r'rango', line['text'], re.IGNORECASE)]
                if not PIVOT_CORNER:
                    raise ValueError("The pivot corner was not found in the page.")
                PIVOT_CORNER = PIVOT_CORNER[0] 
                
                XO = ((PIVOT_CORNER['x0'] // 10) * 10) - 110
                TOP = PIVOT_CORNER['top']

                titles = [line["text"] for line in page_to_extract.within_bbox((XO, TOP - 10, page_to_extract.width, TOP + 15)).extract_text_lines()]
                print(f"Titles extracted: {titles}")

                date_matches = [date_match.group() for title in titles if (date_match := re.search(re_date, title, re.IGNORECASE))]                
                date_val = datetime.strptime(date_matches[0], '%d/%m/%Y') if date_matches else datetime.now()
                formated_date_str = date_val.strftime(format)
                
                tabs = tabula.read_pdf(input_path=file_path, pages=page_to_extract.page_number, area=[TOP, XO, page_to_extract.height, page_to_extract.width], pandas_options={'header': None})[0]
                if tabs.iloc[:, 0].isna().all():
                    tabs.drop(columns=tabs.columns[0], inplace=True)

                df = tabs.rename(columns={tabs.columns[0]: "nv1", tabs.columns[1]: "nv2", tabs.columns[2]: "nv3"})
                nv4_mask = df.iloc[:, 0].apply(lambda x: str(x).lower().strip() in self.NV4_LIST)
                nv5_mask = df.apply(lambda x: ''.join(x.dropna().astype(str)), axis=1).str.contains(r'^\d+-\d+', regex=True)
                df.insert(loc=3, column='nv4', value=df.loc[nv4_mask, "nv1"])

                df['nv4'] = df['nv4'].ffill()
                df = df.loc[(~nv4_mask) & (~nv5_mask)].copy()

                df['nv1'] = df['nv1'].ffill()
                df['nv2'] = df['nv2'].ffill()
                
                compra_venta_df = df[df['nv4'].str.lower().str.strip() == 'compra venta'].copy()
                reporto_df = df[df['nv4'].str.lower().str.strip() == 'reporto'].copy()

                compra_venta_headers = ['nv1', 'nv2', 'nv3', 'nv4'] + self.TEMPLATE_DF_HEADERS[0]
                compra_venta_df = compra_venta_df.iloc[:, :len(compra_venta_headers)]
                compra_venta_df.columns = compra_venta_headers
                compra_venta_df = compra_venta_df.melt(id_vars=['nv1', 'nv2', 'nv3', 'nv4'], value_name='valor', var_name='nv5') 

                reporto_headers = ['nv1', 'nv2', 'nv3', 'nv4'] + self.TEMPLATE_DF_HEADERS[1]
                reporto_df = reporto_df.iloc[:, :len(reporto_headers)]
                reporto_df.columns = reporto_headers 
                reporto_df = reporto_df.melt(id_vars=['nv1', 'nv2', 'nv3', 'nv4'], value_name='valor', var_name='nv5')                

                df_combined = pd.concat([compra_venta_df, reporto_df], axis=0)
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
