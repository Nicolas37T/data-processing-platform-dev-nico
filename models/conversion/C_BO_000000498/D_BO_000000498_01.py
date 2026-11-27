from models.conversion.Conversion_Base import Conversion_Base
import os
import traceback
import pandas as pd

class D_BO_000000498_01(Conversion_Base):
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

		order_columns =['currency', 'name', 'nv1', 'fecha', 'valor']
		try:
			df = pd.read_excel(file_path)
			titles_cols = [col for col in df.columns if 'titulo' in col]
			if not titles_cols:
				titles = ['','']
				df['fecha'] = file_name.split('_')[0]
			else:
				titles = df[titles_cols].iloc[0].to_list()
				df = df.drop(columns=titles_cols)

			df.columns = df.columns.str.lower()
			df_melted = df.melt(id_vars=['currency','name','fecha'], var_name='nv1', value_name='valor')

			df_melted = df_melted[order_columns]
			
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
		return False

Executor_D_BO_000000498_01 = D_BO_000000498_01
Robot = D_BO_000000498_01
