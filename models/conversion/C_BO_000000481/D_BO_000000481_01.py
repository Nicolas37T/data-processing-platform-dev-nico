import re
import os
import tabula
import pdfplumber
import traceback
import numpy as np
import pandas as pd
from models.conversion.tools.conversion_tools import search_key_words, get_pdf_report_page, isLevel, to_numeric_datax
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number
from models.conversion.Conversion_Base import Conversion_Base

class D_BO_000000481_01(Conversion_Base):

    CONVERSION_FACTOR = 72/25.4 # conversion factor from mm to points
    PIVOT_WORDS = 'fondo inversion'
    COLUMN_GAPS = [38.8,6,6.7,13.3,13.1,9.1,10.8,11,11.6,11.7,10.2,10.4]
    TOP_GAP = 10

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

        # Regex pattern for matching dates in the PDF titles
        re_date = r'(\d{1,2})((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))(\d{4})'
        try:
            # Load the template Excel file and extract unique values from 'nv1' column            
            nv1 = ['fondo de inversion abierto', 'fondo de inversion cerrado']
            nv2 = ['fondos de inversion abiertos en bolivianos', 'fondos de inversion abiertos en ufv', 'fondos de inversion abiertos en dolares', 'fondos de inversion cerrados en bolivianos','fondos de inversion cerrados en ufv', 'fondos de inversion cerrados en dolares', 'total', 'tasa promedio ponderada']

            # Open the PDF file and extract the relevant page
            with pdfplumber.open(file_path) as pdf: 
                page_to_extract = get_pdf_report_page(pdf=pdf, key_words=key_words, num_caracteres='ALL',page_number=page_number)
                print(f"Extracting from page number: {page_to_extract.page_number}")
                lines = page_to_extract.extract_text_lines()

                # Find the pivot corner in the extracted lines
                PIVOT_CORNER = [line for line in lines if search_key_words(text=line['text'], key_words=self.PIVOT_WORDS)]
                if not PIVOT_CORNER:
                    raise ValueError("The pivot corner not be found in the page.")
                
                PIVOT_CORNER = sorted(PIVOT_CORNER,key=lambda x: x['x0'])[0]                
                X0 = PIVOT_CORNER['x0']                 
                TOP = PIVOT_CORNER['top'] 
                BOTTOM = page_to_extract.height
                print(f"The X0 point is: {X0/self.CONVERSION_FACTOR:02}mm")

                # Extract titles above the pivot corner
                titles = [line["text"] for line in page_to_extract.within_bbox((0,TOP-self.TOP_GAP*self.CONVERSION_FACTOR,page_to_extract.width,TOP)).extract_text_lines()]
                print(f"Titles extracted: {titles}")

                # Extract and format the date from titles
                date = [date_match.group(1,2,3) for title in titles if (date_match:= re.search(re_date,title, re.IGNORECASE))][0]                
                year = int(date[2])
                month = month_conv if(month_conv:=month_to_number(month=date[1])) else month_abr_to_number(date[1])
                day = date[0]
                formated_date = format_date(f'{year}-{month}-{day}')

                # Calculate column lines based on the gaps
                column_lines = list(X0 + np.cumsum(self.COLUMN_GAPS)*self.CONVERSION_FACTOR)
                print("PAGE NUMBER",page_to_extract.page_number)
                # Read the relevant area of the PDF into a DataFrame
                dataframes = []
                for page in pdf.pages[page_to_extract.page_number-1:]:
                    text = page.extract_text()
                    if not search_key_words(text=text,key_words=key_words):
                        continue
                    tabs = tabula.read_pdf(input_path=file_path,pages=page.page_number, area=[TOP,X0,BOTTOM,page_to_extract.width], pandas_options={'header':None}, columns=column_lines)[0]

                    page_df = tabs.iloc[1:].drop_duplicates()
                    dataframes.append(page_df)
                
                df = pd.concat(dataframes,ignore_index=True)

                total_mask = df.iloc[:,2].apply(lambda x: str(x).strip().lower().startswith('total'))
                promedio_mask = df.iloc[:,4].apply(lambda x: str(x).strip().lower().startswith('tasa'))
                df = df.rename(columns={df.columns[0]:"fondo"})
                nv2_mask = df.loc[:,'fondo'].apply(lambda x: isLevel(nv=nv2, text=x, percentage_simliraty=90))
                
                df.insert(loc=0, column='nv2', value=df.loc[nv2_mask,'fondo'])
                df.loc[total_mask,'nv2'] = df.loc[total_mask,df.columns[3]] 
                df.loc[promedio_mask,'nv2'] = df.loc[promedio_mask,df.columns[5:7]].agg(lambda x: " ".join(x),axis=1)

                df.loc[total_mask,df.columns[3]] = np.nan
                df.loc[promedio_mask,df.columns[5:7]] = np.nan  
                
                nv1_mask = df.loc[:,'fondo'].apply(lambda x: isLevel(nv=nv1, text=x, percentage_simliraty=95))
                df.insert(loc=0, column='nv1', value=df.loc[nv1_mask,'fondo'])
                
                nan_mask = df[df.columns[3:]].isnull().all(axis=1)
                nan_indices = df[nan_mask].index.to_list()
                print(nan_indices)
                for nan_index in nan_indices:
                    if nan_index>1:                    
                        df.loc[nan_index-1,'fondo'] = str(df.loc[nan_index-1,'fondo']) + " " + str(df.loc[nan_index,'fondo'])
                
                columns_to_ffill = ['nv1','nv2']

                for col in columns_to_ffill:
                    df[col] = df[col].ffill()                
                
                df.iloc[1,:3] = df.columns[:3]
                df.columns = df.iloc[1]

                df = df[~nan_mask]
                df = df[~nv1_mask]
                df = df[~nv2_mask]
                numeric_mask = df.iloc[:,5:].astype(str).replace(r'[,%]','',regex=True).map(lambda x: pd.to_numeric(x,errors='coerce')).notna().any(axis=1)
                df = df.loc[numeric_mask]                

                fondo_code_mask = df['fondo'].notna()
                fondo_code = df['fondo'].apply(lambda x: str(x).split(' '))
                df.insert(2,column='nv3', value=fondo_code.apply(lambda x: x[0]).replace('nan',np.nan))
                df.loc[fondo_code_mask,'fondo'] = fondo_code.loc[fondo_code_mask].apply(lambda x: ' '.join(x[1:]))

                # Insert the extracted date into the melted DataFrame
                var_columns = df.columns[:6].to_list()
                df_melted = df.melt(id_vars=var_columns, var_name='nv4', value_name='valor')
                df_melted = df_melted.dropna(subset='valor')                
                df_melted.insert(len(df_melted.columns)-1,column="fecha",value=formated_date.strftime(format))                

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
        
        # Create a copy of the DataFrame to work on
        cleaned_df = dataframe.copy()
        # Clean the 'valor' column by removing special characters and converting to numeric
        cleaned_df['valor'] = to_numeric_datax(serie=cleaned_df['valor'],decimal_separator=decimal_separator)
        cleaned_df = cleaned_df.dropna(subset='valor')

        # Totals validation
        totals_pivot_df = pd.pivot_table(cleaned_df, values='valor', columns='nv4', index='nv2', aggfunc='sum',sort=False)
        print(totals_pivot_df)
        mean_mask = totals_pivot_df.index.str.contains('promedio',case=False,regex=True)
        totals_pivot_df = totals_pivot_df[~mean_mask]

        total_mask = totals_pivot_df.index.str.contains('total',case=False,regex=True)
        total_row = totals_pivot_df[total_mask].iloc[0]
        totals_pivot_df[total_mask] = -totals_pivot_df[total_mask]

        non_nan_columns = total_row[total_row.notna()].index.tolist()
        
        totals_validation = abs(totals_pivot_df.loc[:,non_nan_columns].agg('sum',axis=0))
        print(f'Totals validation:\n{totals_validation}\n')

        totals_validation = totals_validation.between(0,ERROR_TOLERANCE_VALUE).all()

        if not totals_validation:
            print(f"Totals validation failed.")
            totals_mismatch = True
        
        # AVG validation
        mean_pivot_df = cleaned_df.copy()
        mean_mask = mean_pivot_df['nv2'].str.contains('promedio',case=False,regex=True)
        mean_rows = mean_pivot_df[mean_mask].index
        for index in mean_rows:
            mean_pivot_df.loc[index,'nv2'] = mean_pivot_df.loc[index,'nv2'] + "_" + mean_pivot_df.loc[index-1,'nv2']
        
        mean_pivot_df = pd.pivot_table(mean_pivot_df, values='valor', columns='nv4', index='nv2', aggfunc='mean',sort=False)

        total_mask = mean_pivot_df.index.str.contains('total',case=False,regex=True)
        mean_pivot_df = mean_pivot_df[~total_mask]

        mean_mask = mean_pivot_df.index.str.contains('promedio',case=False,regex=True)
        mean_row = mean_pivot_df[mean_mask].iloc[0]
        mean_pivot_df[mean_mask] = -mean_pivot_df[mean_mask]

        non_nan_columns = mean_row[mean_row.notna()].index.tolist()
        print(mean_pivot_df.loc[:,non_nan_columns])
        mean_validation = abs(mean_pivot_df.loc[:,non_nan_columns].agg('sum',axis=0))
        print(f'Average validation:\n{mean_validation}\n')

        mean_validation = mean_validation.between(0,ERROR_TOLERANCE_VALUE).all()

        if not mean_validation:
            print(f"Average validation failed.")
            totals_mismatch = True
        # Return the cleaned DataFrame if all validations pass
        if not totals_mismatch:
            print("All validations passed. Returning the cleaned DataFrame.") 
        return totals_mismatch
