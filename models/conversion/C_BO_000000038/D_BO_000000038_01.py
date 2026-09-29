from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import tabula
import pdfplumber
import traceback
import pandas as pd
import numpy as np
from models.download.tools.download_tools import format_date
from models.conversion.tools.conversion_tools import search_value, get_pdf_report_page, to_numeric_datax

class D_BO_000000038_01(Conversion_Base):

    PIVOT_WORDS = 'cantidad'
    CONVERSION_FACTOR = 72/25.4
    COLUMN_GAPS = [19.9,15.5,49.1,19.6,19.4]

    def extraction(self, file_path: str, key_words: str, template_path: str = "", page_number: int = 1, format: str = "%Y-%m-%d") -> tuple:
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
        # Extract the file name from the given file path
        file_name = os.path.basename(file_path)

        # Regular expression pattern for matching dates 
        re_date = r'(\d{1,2}/\d{1,2}/\d{4})'
        
        try:
            # Open the PDF file using pdfplumber
            with pdfplumber.open(file_path) as pdf:
                page_to_extract = get_pdf_report_page(pdf=pdf,key_words=key_words,num_caracteres='ALL',page_number=page_number)
                print(f"Extracting from page number: {page_to_extract.page_number}")
                
                # Extract text lines from the identified page
                lines = page_to_extract.extract_text_lines()

                # Search for date patterns in the text lines
                date = [re.search(re_date,line['text']).group() for line in lines if re.search(re_date,line['text'])]                         
                date = format_date(date[0],format='%d/%m/%Y')
                
                PIVOT_CORNER = [line for line in lines if re.search(fr'^{self.PIVOT_WORDS}', line['text'], re.IGNORECASE)]
                if not PIVOT_CORNER:
                    raise ValueError("The pivot corner not be found in the page.")
                
                PIVOT_CORNER = PIVOT_CORNER[0]   
                # Define bounding box coordinates for extracting relevant data
                TOP = PIVOT_CORNER['top']
                X0 = PIVOT_CORNER['x0'] -(3*self.CONVERSION_FACTOR)

                titles = [line["text"] for line in page_to_extract.within_bbox((0.0,TOP-25*self.CONVERSION_FACTOR,page_to_extract.width,TOP)).extract_text_lines()]
                print(f"Titles extracted: {titles}")        

                monto_ofertado = [value for line in lines if (value:=search_value(text=line['text'],label='ofertada'))]
                serie = [value for line in lines if (value:=search_value(text=line['text'],label='serie'))]
                trn = [value for line in lines if (value:=search_value(text=line['text'],label='trn'))]                
                
                column_lines = list(X0 + np.cumsum(self.COLUMN_GAPS)*self.CONVERSION_FACTOR)

                tabs = tabula.read_pdf(input_path=file_path,pages=page_to_extract.page_number, area=[TOP,X0,page_to_extract.height,page_to_extract.width], columns=column_lines, pandas_options={'header':None})
                
                df = tabs[0]
                if len(df.columns) != len(self.COLUMN_GAPS):
                    df = df[df.columns[:len(self.COLUMN_GAPS)]]

                df.iloc[2] = df.iloc[[0,1,2]].astype(str).agg(lambda x: ''.join(x), axis=0).str.replace('nan',' ').str.strip()
                df.columns = df.iloc[2].to_list()
                print(df)                
                df = df.iloc[3:]
                df = df.dropna(subset=df.columns[0])                
                df = df.dropna(subset=df.columns[1:3].tolist(),how='all')
                
                emisor_col = df.columns[1]
                motivo_col = df.columns[-1]
                numeric_mask = pd.to_numeric(df[df.columns[0]], errors='coerce').notna()
                df.insert(0, "plazo", df.loc[~numeric_mask].astype(str).agg(lambda x: ''.join(x), axis=1).str.replace('nan',''))             
                plazo_mask = df['plazo'].astype(str).str.contains(r'\b\d+\b', regex=True)
                
                df['monto_ofertado'] = None
                df['serie'] = None
                df['trn'] = None

                df.loc[plazo_mask, 'monto_ofertado'] = monto_ofertado
                df.loc[plazo_mask, 'serie'] = serie
                df.loc[plazo_mask, 'trn'] = trn

                extracted_values_columns = ["plazo", "monto_ofertado", "serie", "trn"]
                df[extracted_values_columns] = df[extracted_values_columns].ffill()

                df_cleaned = df.loc[numeric_mask]
                df_cleaned = df_cleaned.dropna(subset=extracted_values_columns, how='all')
                
                var_columns = ['serie', 'plazo', emisor_col, motivo_col]
                df_melted = df_cleaned.melt(id_vars=var_columns, var_name='nv1', value_name='valor')

                df_melted = df_melted.dropna(subset='valor')

                # Insert the extracted date into the melted DataFrame
                df_melted.insert(len(df_melted.columns) - 1, column="fecha", value=date.strftime(format))
                
            return ({
                    "file_name": file_name,
                    "titles": titles,
                    "page_number":int(page_to_extract.page_number)
                }, df_melted)
        except ValueError as e:
            print(f"Validation error: {e}")                        
            traceback.print_exc()
        except Exception as e:            
            print(f"An error ocurred: {e}")            
            traceback.print_exc()
        return ""
    
    def validate_data_results(self, dataframe: pd.DataFrame, decimal_separator: str = ",", TOLERANCE: float = 6.0) -> bool:
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
        
        # Create a copy of the DataFrame to work on
        cleaned_df = dataframe.copy()
        # Clean the 'valor' column by removing special characters and converting to numeric
        cleaned_df['valor'] = to_numeric_datax(serie=cleaned_df['valor'], decimal_separator=decimal_separator)
        cleaned_df = cleaned_df.dropna(subset='valor')  
                
        pivot_df = cleaned_df.copy()
        emisor_col = 'Emisor' if 'Emisor' in pivot_df.columns else pivot_df.columns[6]
        total_mask = pivot_df[emisor_col].isna()
        pivot_df.loc[total_mask, 'valor'] = -pivot_df.loc[total_mask, 'valor']

        # Create a pivot table to aggregate values
        pivot_df = pd.pivot_table(pivot_df, values='valor', columns='nv1', index='serie', aggfunc='sum')
        cols_to_validate = [col for col in pivot_df.columns if any(term in str(col).lower() for term in ['demandada', 'adjudicada'])] 
        pivot_df = pivot_df[cols_to_validate] 
        print(pivot_df)   
        
        for index, row in pivot_df.iterrows():
            print(f"Processing serie: {index}")
            vertical_total_validation = abs(row)
            print(f'Validation:\n{vertical_total_validation}\n')
            vertical_total_validation = vertical_total_validation.between(0,ERROR_TOLERANCE_VALUE).all()

            if not vertical_total_validation:
                print(f"Vertical totals validation failed fer serie: {index}")
                totals_mismatch = True
                break
        # Return the cleaned DataFrame if all validations pass
        if not totals_mismatch:
            print("All validations passed. Returning the cleaned DataFrame.")   
        return totals_mismatch

Executor_D_BO_000000038_01 = D_BO_000000038_01
Robot = D_BO_000000038_01
