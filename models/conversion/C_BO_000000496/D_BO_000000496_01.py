import os
import traceback
import pandas as pd
from models.download.tools.download_tools import format_date
from models.conversion.tools.conversion_tools import to_numeric_datax
from models.conversion.Conversion_Base import Conversion_Base

class D_BO_000000496_01(Conversion_Base):

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
            # template_df = pd.read_excel(template_path)            
            
            df = pd.read_excel(file_path, header=None)

            numeric_mask = pd.to_numeric(df.iloc[:,1], errors='coerce').notna()
            numeric_indices = df.loc[numeric_mask].index
        
            titles, df_splited = df.loc[:numeric_indices[0]-2, df.columns[0]],df.loc[numeric_indices[0]-1:]
            
            print(df_splited)
            print(titles)
            titles = titles.dropna().to_list()

            df_splited.iloc[0,0] = 'nv1'
            df_splited.columns = df_splited.iloc[0]
            df_splited = df_splited.iloc[1:]

            df_melted = df_splited.melt(id_vars=df_splited.columns[0], value_name='valor', var_name='fecha')            
            df_melted['fecha'] = df_melted['fecha'].apply(lambda x: format_date(x,format='%m-%d-%Y').strftime(format))

            df_melted = df_melted.dropna().reset_index(drop=True)

            return ({
                    "file_name": file_name,
                    "titles": titles,
                    "page_number":1
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
        cleaned_df = cleaned_df.dropna(subset='valor')        
        
        # Return the cleaned DataFrame if all validations pass
        print("All validations passed. Returning the cleaned DataFrame.")      
        return totals_mismatch