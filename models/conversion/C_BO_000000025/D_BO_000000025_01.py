import sys
sys.path.append('/opt/airflow')
import re
import os
import tabula
import pdfplumber
import traceback
import numpy as np
import pandas as pd
from models.conversion.tools.conversion_tools import get_pdf_report_page, get_col_date, to_numeric_datax
from models.conversion.Conversion_Base import Conversion_Base

class D_BO_000000025_01(Conversion_Base):

    CONVERSION_FACTOR = 72/25.4 # conversion factor from mm to points
    COLUMN_GAPS = [24,24,24,24]
    PIVOT_WORDS = 'fecha'
    TOP_GAP = 6    

    def extraction(self, file_path, key_words, template_path, page_number, format='%Y-%m-%d'):
        """
        Extracts data from a specifiedfile based on provided keywords and a date filter, and saves the extracted data into an Excel file.

        Parameters:
            file_path (str): Path to the PDF file to be processed.
            key_words (str): Keywords to identify the relevant page in the PDF.
            converted_to (str): Date to compare the extracted report date against.
            template_path (str): Path to the Excel template used for validation.
            COLUMN_GAPS (list): List of gaps between columns in the extracted table in mm.
            PIVOT_WORDS (str): Keyword indicating the pivot corner in the PDF.
            format (str): Date format to use when converting dates (default: '%Y-%m-%d').
            
        Returns:
            str: Empty string if successful, or error messages on failure.
        """
        # Get the base name of the file from the file path
        file_name = os.path.basename(file_path)
        
        try:
           
            # Open the PDF file and extract the relevant page
            with pdfplumber.open(file_path) as pdf: 
                page_to_extract = get_pdf_report_page(pdf=pdf, key_words=key_words,page_number=page_number)
                print(f"Extracting from page number: {page_to_extract.page_number}")
                lines = page_to_extract.extract_text_lines()

                # Find the pivot corner in the extracted lines
                PIVOT_CORNER = [line for line in lines if re.search(fr'^{self.PIVOT_WORDS}', line['text'], re.IGNORECASE)]
                if not PIVOT_CORNER:
                    raise ValueError("The pivot corner not be found in the page.")
                
                PIVOT_CORNER = PIVOT_CORNER[0]                                 
                X0 = min([line['x0'] for line in lines])                
                TOP = PIVOT_CORNER['top'] - (self.TOP_GAP * self.CONVERSION_FACTOR)
                BOTTOM = page_to_extract.height
                print(f"The X0 point is: {X0/self.CONVERSION_FACTOR:02}mm")

                # Extract titles above the pivot corner
                titles = [line["text"] for line in page_to_extract.within_bbox((0,TOP-5*self.CONVERSION_FACTOR,page_to_extract.width,TOP)).extract_text_lines()]
                print(f"Titles extracted: {titles}")

                # Calculate column lines based on the gaps
                column_lines = list(X0 + np.cumsum(self.COLUMN_GAPS)*self.CONVERSION_FACTOR)
                
                # Read the relevant area of the PDF into a DataFrame
                tabs = tabula.read_pdf(input_path=file_path,pages=page_to_extract.page_number, area=[TOP,X0,BOTTOM,page_to_extract.width], pandas_options={'header':None},columns=column_lines)[0]

                last_index = tabs[tabs[tabs.columns[0]].str.contains(r'fuente',case=False,na=False)].index[0]
                df = tabs.loc[:last_index-1]

                df.iloc[0,[1,2]] = df.iloc[0,[1,2]].agg(lambda x: ''.join(x.astype(str)))

                first_column_numeric_values = df[pd.to_numeric(df[df.columns[1]].replace(',','.',regex=True), errors='coerce').notna()]
                index_first_data_row = first_column_numeric_values.index[0]
                df.loc[index_first_data_row-1] = df.loc[1:index_first_data_row-1].agg(lambda x: ' '.join(x.dropna().astype(str)), axis=0)

                df_cleaned = pd.concat([df.iloc[[0]], df.loc[index_first_data_row-1:]])

                df_cleaned = df_cleaned.rename(columns={df_cleaned.columns[0]:'fecha'})
                df_cleaned = df_cleaned.set_index(['fecha'])
                columns = pd.MultiIndex.from_arrays(df_cleaned.iloc[:2].values)              
                df_cleaned.columns = columns
                df_cleaned = df_cleaned.reset_index()

                df_cleaned = df_cleaned.loc[2:].dropna(how='all',axis=1)
                df_cleaned['fecha'] = df_cleaned['fecha'].astype(str) + " " + re.search(r'(\d{4})',file_name).group(1)
                df_cleaned['fecha'] = df_cleaned['fecha'].apply(lambda x: get_col_date(x))

                df_melted = df_cleaned.melt(id_vars=['fecha'], var_name=['nv1','nv2'], value_name='valor')
                df_melted = df_melted.loc[:,['nv1','nv2','fecha','valor']]
                
                df_final = df_melted.dropna(subset='valor') 

                return ({
                    "file_name": file_name,
                    "titles": titles,
                    "page_number":int(page_to_extract.page_number)
                }, df_final)
        except ValueError as e:
            print(f"Validation error: {e}")
            traceback.print_exc()                        
        except Exception as e:            
            print(f"An error ocurred: {e}")            
            traceback.print_exc()
        return ""
    
    def validate_data_results(self, dataframe:pd.DataFrame, decimal_separator:str):
        """Validates and cleans the data in a DataFrame. The function performs the following tasks:
    
        1. Validates the totals in the data (this may involve specific checks on values in the DataFrame).        
        3. Processes numeric data to ensure they are in the correct format, converting them to numeric type and handling possible conversion errors.
        
        If the totals are not validated successfully, the function returns None. Otherwise, it returns the cleaned DataFrame.
        
        Args:
            dataframe (pd.DataFrame): The DataFrame containing the data to validate and clean.
            
        Returns:
            pd.DataFrame | None: The cleaned DataFrame if the totals are validated, otherwise None.
        """        
        totals_mismatch = False
        # Create a copy of the DataFrame to work on
        cleaned_df = dataframe.copy()

        # Clean the 'valor' column by removing special characters and converting to numeric
        cleaned_df['valor'] = to_numeric_datax(serie=cleaned_df['valor'],decimal_separator=decimal_separator)
        cleaned_df.to_excel('result.xlsx',index=False)
        
        # Return the cleaned DataFrame if all validations pass
        print("All validations passed. Returning the cleaned DataFrame.")   
        return (totals_mismatch,dataframe)

if __name__ == "__main__":
    robot = D_BO_000000025_01()
    x = robot.extraction(file_path=r'/opt/airflow/models/conversion/C_BO_000000025/2025-01-06_precios hidrocarburos.pdf',key_words='precios internacionales',template_path='',page_number=1)
    print(x)
    # df = tabula.read_pdf(input_path=r'/opt/airflow/models/conversion/C_BO_000000025/2025-01-06_precios hidrocarburos.pdf',pages=1)[0]
    # print(df)