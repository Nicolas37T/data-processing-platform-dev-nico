import os
import re
import shutil
import traceback
import pandas as pd
from datetime import date, datetime
from playwright.sync_api import sync_playwright
from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import format_date, last_day_month

class D_BO_000000554(Download_Base):
	def verify_download(self,main_url, updated_to, path, format='%Y-%m-%d'):
		"""
		Download the file without comparing dates, and saves them to a temporary path.
		Parameters:
			main_url(str):The URL of the main page.
			updated_to (str): The latest date for which the database contains records.
			path (str): The directory path where the downloaded files will be saved.
			format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

		Returns:
			list: A list of download tmp_path for files that meet the criteria.
			If there are no elements older than the date, it returns false.
			If there is an error, it returns an empty list.
		"""

		# Convert updated_to string to datetime object				
		updated_to = format_date(updated_to)				
		file_paths = []

		with sync_playwright() as pl:        

			# Road transport volume index
			rt_volume_index_xpath = '(//div[@class="standard-arrow list-divider bullet-top"]/ul/li/a)[7]'
						
			# Erase the previous tmp path and create the a new one        
			path = os.path.join(path, "tmp")

			# Verifed if the folder exist else delete it to create of new
			if os.path.exists(path):
				shutil.rmtree(path)
			os.makedirs(path)

			try:
				# Launch browser and navigate to main URL
				print(f"Launching browser and navigating to {main_url} ...")
				browser = pl.chromium.launch(headless=True)
				context = browser.new_context(
					user_agent='Mozilla/5.0 (Windows NT 10.0 Win64 x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36'
				)
				page = context.new_page()
				page.goto(main_url, wait_until='domcontentloaded')


				link = page.locator(rt_volume_index_xpath)                                                         
				# print(link.text_content())

									
				with page.expect_download() as download_info:
					link.click()

				donwload = download_info.value
			
				# Bolivia – Índice de Volumen de Transporte Carretero por Tipo de Servicio y Flujo según Año y Mes, 1992 – 2024
				download_path = os.path.join(path,"rt_volume_index.xlsx")                  

				donwload.save_as(download_path)
				file_paths.append(
					{
						'tmp_path': download_path,
						'download_url': "-"
					}
				)              

			except Exception as e:
				print(f"An error ocurred: {e}")
				traceback.print_exc()    
				return []            
			finally:
				# Close page and browser
				if 'page' in locals():
					page.close()
				if 'browser' in locals():
					browser.close()
					# Check if any files were found after the updated date		
		if not len(file_paths):		
			print(f"There are NO files after {updated_to.strftime(format)}")		
			return False		        		

		return file_paths    


	def compare_files(self,files_paths,updated_to,format='%Y-%m-%d'):
		"""
		Extract the date from a list of files to compare and filter which are more recent than the updated_to date.

		Parameters:
			files_paths (list): List of dictionaries containing information about files.
			updated_to (str): The latest date for which the database contains records.
			format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

		Returns:
			list or bool: A list of dictionaries with information about files that meet the criteria of being more recent than 'updated_to'. Returns False if no more recent files are found.
		"""
		updated_to = format_date(updated_to,format)
		list_files=[]
		
		# Browse the list of dictionaries
		for file in files_paths:
			tmp_path = file.get('tmp_path')

			# Step 1: Read the first 20 rows to find the "PERIODO" header
			max_rows_to_read = 20 
			df_new_file = pd.read_excel(tmp_path, nrows=max_rows_to_read, header=None, engine="openpyxl")            
			# print(df_new_file) 
			header_row = None
			col_period = None

			
			# Find the row and column where the 'PERIODO' header is
			for i, df_row in df_new_file.iterrows():
				for j, val in enumerate(df_row):
					if isinstance(val, str) and val.strip().upper() == "PERIODO":
						header_row = i
						col_period = j
						break
				if header_row is not None:
					break                                
			
			if header_row is not None:
				print(f"Header 'PERIOD' found in row {header_row} and column {col_period}")
			else:
				print("The 'PERIOD' header was not found in the first rows.")
			tmp_path = file.get('tmp_path')
			
			
			# Step 2: Read the table from the header row
			df = pd.read_excel(tmp_path, header=header_row,engine="openpyxl")
			# print("initial table: ")
			# print(df)
			
			# Step 3: Process PERIODO column to extract years and months
			current_year = None
			full_period = []
			months_dict = {
				'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
				'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
			}

			for val_col_periods in df['PERIODO']: #find the month and year
				# print(type(val_col_periods))
				# print(val_col_periods)
				if val_col_periods and pd.notna(val_col_periods):
					val_col_periods = str(val_col_periods)                
					year_match = re.match(r'^(\d{4})', val_col_periods)

					if year_match:
						current_year = year_match.group(1)
						full_period.append(None) #If it is a year, the full_period column becomes None
					# else:
					#     full_period.append(f"{val_col_periods} {current_year}")
					
					elif str(val_col_periods).strip().lower() in months_dict and current_year:

						full_period.append(f"{str(val_col_periods).strip().lower()} {current_year}")

					else:
						full_period.append(None)
				else:
					full_period.append(None)
			
			df['FULL_PERIOD'] = full_period            
			# print(df)

			# Step 4: Filter rows with valid months
			df_filtering = df[df['FULL_PERIOD'].notna()].copy()


			df_filtering['DATE'] = df_filtering['FULL_PERIOD'].apply(
			# Using apply directly with pd.to_datetime and lambda funtion
				lambda x: datetime(
					year=int(x.split()[1]),
					month=months_dict[x.split()[0].lower()], 
					day=last_day_month(int(x.split()[1]),int(months_dict[x.split()[0].lower()]))                    
				) 

				if len(x.split()) == 2 
				else pd.NaT                                
			)
			# print(df_filtering)
			# print(df_filtering.tail(20))           

			# step 6: Get last year and month
			last_date_df = df_filtering['DATE'].max()

			# Checks if the 'last_year' and 'last_month' values ​​are valid
			if pd.notna(last_date_df):

				# If valid, we get the year and month
				df_last_year = last_date_df.year
				df_last_month = last_date_df.month
				df_last_day = last_date_df.day
				
				try:

					# Create the date if 'last_year' and 'last_month' are not None
					date_df_max = date(df_last_year, df_last_month,df_last_day )                      
					date_formated = date_df_max.strftime(format)                    

					if(date_df_max>updated_to.date()):         

						list_files.append(
							{
								"tmp_path": tmp_path,
								"updated_to": date_formated,
								"download_url":'-'
							}
						)
						# print("the file is older than the given dater")
				except ValueError:
					# In case the date is not valid (for example, an incorrect month or year)
					print("Invalid date, file cannot be processed.")
			else:
				# If 'last_year' or 'last_month' are None, handle the case
				print("The last year and month could not be determined. The file will not be processed.")
		return list_files


Executor_D_BO_000000554 = D_BO_000000554
Robot = D_BO_000000554
