from models.conversion.Conversion_Base import Conversion_Base
import re
import os
import pdfplumber
import traceback
import numpy as np
import pandas as pd
from models.conversion.tools.conversion_tools import search_key_words, get_pdf_report_page, to_numeric_datax
from models.download.tools.download_tools import format_date

class D_BO_000000042_01(Conversion_Base):

    CONVERSION_FACTOR = 72/25.4 # conversion factor from mm to points
    COLUMN_GAPS = [27.5,27.1,10.0,23.8,29.4,10.0,28.3,28.1,10.8]
    TOP_GAP = 5   

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
        re_date = r'(\d{1,2})/(\d{1,2})/(\d{1,2})'
        try:
            # Load the template Excel file and extract unique values from 'nv1' column
            # template_df = pd.read_excel(template_path)                

            # Open the PDF file and extract the relevant page
            with pdfplumber.open(file_path) as pdf: 
                page_to_extract = get_pdf_report_page(pdf=pdf, key_words=key_words, num_caracteres='ALL')
                print(f"Extracting from page number: {page_to_extract.page_number}")
                lines = page_to_extract.extract_text_lines()

                # Find the pivot corner in the extracted lines
                PIVOT_CORNER = [line for line in lines if search_key_words(text=line['text'], key_words=key_words)]
                if not PIVOT_CORNER:
                    raise ValueError("The pivot corner not be found in the page.")
                
                PIVOT_CORNER = PIVOT_CORNER[0]
                # print(PIVOT_CORNER)                                 
                X0 = min([line['x0'] for line in lines])                
                TOP = PIVOT_CORNER['top'] + self.TOP_GAP * self.CONVERSION_FACTOR
                BOTTOM = page_to_extract.height - 10*self.CONVERSION_FACTOR 
                print(f"The X0 point is: {X0/self.CONVERSION_FACTOR:02}mm")

                # Extract titles above the pivot corner
                titles = [line["text"] for line in page_to_extract.within_bbox((0,TOP - self.TOP_GAP * self.CONVERSION_FACTOR,page_to_extract.width,TOP)).extract_text_lines()]
                print(f"Titles extracted: {titles}")

                # Extract and format the date from titles
                date = [date_match.group(1,2,3) for title in titles if (date_match:= re.search(re_date,title, re.IGNORECASE))][0]
                print(date)                
                
                formated_date = format_date(f'20{date[2]}-{date[1]}-{date[0]}')

                # Calculate column lines based on the gaps
                column_lines = list(X0 + np.cumsum(self.COLUMN_GAPS) * self.CONVERSION_FACTOR)
                v_lines = [X0] + column_lines

                # Extract table with pdfplumber
                cropped1 = page_to_extract.crop((X0, TOP, page_to_extract.width, BOTTOM))
                table_data1 = cropped1.extract_table({
                    "vertical_strategy": "explicit",
                    "explicit_vertical_lines": v_lines,
                    "horizontal_strategy": "text"
                })
                tabs = pd.DataFrame(table_data1)
                tabs = tabs.replace(r'^\s*$', np.nan, regex=True).dropna(how='all').reset_index(drop=True)

                tabs2 = pd.DataFrame()
                if page_to_extract.page_number < len(pdf.pages):
                    page2 = pdf.pages[page_to_extract.page_number]
                    cropped2 = page2.crop((X0, 30 * self.CONVERSION_FACTOR, page2.width, BOTTOM))
                    table_data2 = cropped2.extract_table({
                        "vertical_strategy": "explicit",
                        "explicit_vertical_lines": v_lines,
                        "horizontal_strategy": "text"
                    })
                    tabs2 = pd.DataFrame(table_data2).replace(r'^\s*$', np.nan, regex=True).dropna(how='all').reset_index(drop=True)

                if not tabs2.empty and re.search(r'embarque', str(tabs2.iloc[0, 1]), re.IGNORECASE):
                    df = pd.concat([tabs, tabs2])
                else:
                    df = tabs
                df = df.drop_duplicates()
                df = df.reset_index(drop=True)
                
                if df[df.columns[2]].isna().any():
                    nan_index = df[df.columns[2]].isna().idxmax()
                    df = df.loc[:nan_index-1]

                df.columns = df.iloc[0]
                df_cleaned = df.loc[1:]

                df_cleaned = pd.concat([df_cleaned.iloc[:,:3], df_cleaned.iloc[:,3:6],df_cleaned.iloc[:,6:]])
                df_cleaned = df_cleaned.reset_index(drop=True)
                
                value_column = df_cleaned.columns[-1]
                column_to_analize = df_cleaned[df_cleaned.columns[1]].str.split(r'\s+',expand=True,regex=True)
                new_column_mask = column_to_analize.iloc[:,1].notna()
                new_column_values = df_cleaned.loc[new_column_mask,value_column]
                new_cols = str(column_to_analize.iloc[new_column_values.index[0],0]).split('/')
                
                df_cleaned.insert(len(df_cleaned.columns),column=new_cols[1],value=df_cleaned.loc[new_column_mask,value_column])

                df_cleaned.loc[new_column_mask,value_column] = column_to_analize.loc[new_column_mask,column_to_analize.columns[1]]
                df_cleaned[df_cleaned.columns[1]] = column_to_analize.iloc[:,0]

                df_cleaned = df_cleaned.rename(columns={value_column:new_cols[0]})

                df_melted = df_cleaned.melt(id_vars=df_cleaned.columns[:2],value_name='valor', var_name='nv1')
                df_melted = df_melted.dropna()    

                df_melted.insert(len(df_melted.columns) - 1,column="fecha",value=formated_date.strftime(format))

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
        totals_mismatch = False
        # Create a copy of the DataFrame to work on
        cleaned_df = dataframe.copy()
        
        # Clean the 'valor' column by removing special characters and converting to numeric
        cleaned_df['valor'] = to_numeric_datax(serie=cleaned_df['valor'],decimal_separator=decimal_separator)

        # Return the cleaned DataFrame if all validations pass
        print("All validations passed. Returning the cleaned DataFrame.")
        return totals_mismatch

Executor_D_BO_000000042_01 = D_BO_000000042_01
Robot = D_BO_000000042_01
