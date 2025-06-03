import os
import tabula
import pdfplumber
import traceback
import numpy as np
import pandas as pd
from models.conversion.tools.conversion_tools import search_key_words, get_pdf_report_page, get_col_date, to_numeric_datax
from models.download.tools.download_tools import format_date
from models.conversion.Conversion_Base import Conversion_Base

class D_BO_000000025_03(Conversion_Base):

    CONVERSION_FACTOR = 72/25.4 # conversion factor from mm to points
    COLUMN_GAPS = [30.4,16.3,16.3,16.3,16]
    TOP_GAP = 6.8    

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
                page_to_extract = get_pdf_report_page(pdf=pdf, key_words=key_words, num_caracteres='ALL',page_number=page_number)
                print(f"Extracting from page number: {page_to_extract.page_number}")
                lines = page_to_extract.extract_text_lines()

                # Find the pivot corner in the extracted lines
                PIVOT_CORNER = [line for line in lines if search_key_words(text=line['text'], key_words=key_words)]
                if not PIVOT_CORNER:
                    raise ValueError("The pivot corner not be found in the page.")
                
                PIVOT_CORNER = PIVOT_CORNER[0]                                 
                X0 = min([line['x0'] for line in lines])                
                TOP = PIVOT_CORNER['top'] + (self.TOP_GAP * self.CONVERSION_FACTOR)
                BOTTOM = page_to_extract.height
                print(f"The X0 point is: {X0/self.CONVERSION_FACTOR:02}mm")

                # Extract titles above the pivot corner
                titles = [line["text"] for line in page_to_extract.within_bbox((0,TOP-self.TOP_GAP*self.CONVERSION_FACTOR,page_to_extract.width,TOP)).extract_text_lines()]
                print(f"Titles extracted: {titles}")

                # Calculate column lines based on the gaps
                column_lines = list(X0 + np.cumsum(self.COLUMN_GAPS)*self.CONVERSION_FACTOR)
                
                # Read the relevant area of the PDF into a DataFrame
                tabs = tabula.read_pdf(input_path=file_path,pages=page_to_extract.page_number, area=[TOP,X0,BOTTOM,page_to_extract.width], pandas_options={'header':None},columns=column_lines)[0]

                df = tabs[tabs.columns[:-1]]
                first_column_numeric_values = df[pd.to_numeric(df[df.columns[1]].replace(',','.',regex=True), errors='coerce').notna()]
                index_first_data_row = first_column_numeric_values.index[0]
                index_last_data_row = first_column_numeric_values.index[-1]

                df.loc[index_first_data_row-1] = df.loc[:index_first_data_row-1].agg(lambda x: ' '.join(x.dropna().astype(str)), axis=0)

                df.columns = df.loc[index_first_data_row-1]

                df_cleaned = df.loc[index_first_data_row:index_last_data_row]

                df_cleaned = df_cleaned.dropna(subset=df_cleaned.columns[1:], how='all')

                df_cleaned = df_cleaned.rename(columns={df_cleaned.columns[0]: "fecha"})

                df_melted = df_cleaned.melt(id_vars=['fecha'], var_name='nv1', value_name='precio')
                df_melted = df_melted.loc[:,['nv1','fecha','precio']]

                promedio_mask = df_melted['fecha'].str.contains('promedio',case=False,na=False,regex=True)

                df_melted['promedio'] = df_melted.loc[promedio_mask,'precio']

                df_melted.loc[promedio_mask,'precio'] = np.nan

                df_melted["fecha"] = df_melted["fecha"].astype(str).str.replace(r'[^a-zA-Z0-9\-]', '', regex=True,case=False).apply(lambda x: get_col_date(x))                

                data_dates =df_melted.loc[~promedio_mask,'fecha'].dropna().apply(lambda x: format_date(str(x))).sort_values(ascending=True).unique().tolist()
                
                formated_date = data_dates[-1]  
                
                df_melted.loc[promedio_mask,'fecha'] = df_melted.loc[promedio_mask,'fecha'].apply(lambda x: formated_date.strftime(format) if format_date(x).year == formated_date.year else x)

                df_melted = df_melted.melt(id_vars=['nv1','fecha'], var_name='nv2', value_name='valor')
                promedio_mask = df_melted['nv2'] == 'promedio'
                df_melted.loc[promedio_mask,'nv2'] = df_melted.loc[promedio_mask].apply(lambda x: f'promedio {x["fecha"].split("-")[0]}',axis=1)
                df_melted.loc[promedio_mask,'fecha'] = '-'
                df_melted = df_melted.dropna(subset='valor')
                df_melted = df_melted.loc[:,['nv1','nv2','fecha','valor']]

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
        ERROR_TOLERANCE_VALUE = 0.1
        totals_mismatch = False

        # Create a copy of the DataFrame to work on
        cleaned_df = dataframe.copy()

        # Clean the 'valor' column by removing special characters and converting to numeric
        cleaned_df['valor'] = to_numeric_datax(serie=cleaned_df['valor'],decimal_separator=decimal_separator)
        cleaned_df = cleaned_df.dropna(subset='valor')  

        df_to_validate = cleaned_df.copy()
        df_to_validate['fecha'] = pd.to_datetime(df_to_validate['fecha'],errors='coerce')
        avg = df_to_validate[df_to_validate['nv2'].str.contains(r'promedio',case=False,regex=True)]
        data = df_to_validate[~df_to_validate['nv2'].str.contains(r'promedio',case=False,regex=True)]
        pivot_avg = pd.pivot_table(avg,values='valor', columns='nv1', index='nv2', aggfunc='sum')
        pivot_data = pd.pivot_table(data,values='valor', columns='nv1', index='fecha', aggfunc='sum')
        pivot_data = pivot_data.groupby(pivot_data.index.year).agg('mean')        

        for year in pivot_data.index:
            print(f"Processing year: {year}")

            vertical_total_validation = pivot_data.loc[year] - pivot_avg.loc[pivot_avg.index.str.contains(str(year))]
            print(f'Vertical totals:\n{vertical_total_validation}')
            vertical_total_validation = abs(vertical_total_validation.iloc[0]).between(0,ERROR_TOLERANCE_VALUE).all()
            if not vertical_total_validation:
                print(f"Vertical totals validation failed for level: {year}.")
                totals_mismatch = True
                break

        # Return the cleaned DataFrame if all validations pass
        if not totals_mismatch:
            print("All validations passed. Returning the cleaned DataFrame.")   
        return (totals_mismatch,dataframe)