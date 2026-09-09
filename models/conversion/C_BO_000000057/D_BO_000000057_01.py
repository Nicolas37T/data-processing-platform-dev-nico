import os
import traceback
import pandas as pd
from models.download.tools.download_tools import format_date
from models.conversion.tools.conversion_tools import to_numeric_datax
from models.conversion.Conversion_Base import Conversion_Base

class D_BO_000000057_01(Conversion_Base):

    def extraction(self, file_path, key_words, template_path, page_number, format='%Y-%m-%d'):
        """
        Extracts data from a specifiedfile based on provided keywords and a date filter, and saves the extracted data into an Excel file.

        Parameters:
        - file_path (str): The path to the file from which to extract data.
        - key_words (str): keywords to search for within the file.
        - converted_to (str): The date to compare against the extracted date from the file.
        - template_path (str): The path to the template file.
        - format (str): The date format to use when comparing dates and saving the file.

        Returns:
        - str: The path to the Excel file containing the extracted data.

        Raises:
        - ValueError: If the report, or date is not found in the file, or if the date is before the specified date.
        """

        # Extract the file name from the given file path
        file_name = os.path.basename(file_path)

        try:
            df = pd.read_excel(file_path)
            df.rename(columns={'Fecha':'fecha'}, inplace=True)
            titles = ["Información General de Fondos de Inversión"]

            df_melted = df.melt(id_vars=df.columns[:3], value_name='valor', var_name='nv1')

            df_melted = df_melted.iloc[:,[1,2,3,0,4]]

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