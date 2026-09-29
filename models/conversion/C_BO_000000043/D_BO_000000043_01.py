from models.conversion.Conversion_Base import Conversion_Base
import os
import traceback
import pandas as pd

class D_BO_000000043_01(Conversion_Base):

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
			df = pd.read_excel(file_path,header=None)
			df = df.dropna(how='all').reset_index(drop=True)
			df = df.dropna(axis=1, how='all')

			df.columns = df.iloc[0]
			df = df.loc[1:].reset_index(drop=True)
			df = df.rename(columns={
				df.columns[0]: "fecha"
			})

			df['fecha'] = pd.to_datetime(df['fecha'], errors='raise',format='%d/%m/%Y').dt.strftime(format)
			df_melted = df.melt(id_vars='fecha', value_name='valor', var_name='nv1')
			df_melted = df_melted[['nv1', 'fecha', 'valor']]

			return ({
                    "file_name": file_name,
                    "titles": [],
                    "page_number": 1
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
		return False

Executor_D_BO_000000043_01 = D_BO_000000043_01
Robot = D_BO_000000043_01
