import traceback
import shutil
import os
import pandas as pd
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date,search_key_words
from models.download.Download_Base import Download_Base

class D_BO_000000561(Download_Base):

	def verify_download(self,main_url, updated_to, path, key_words="Descargar Archivo CSV", format='%Y-%m-%d'):
		"""
		Download the file without comparing dates, and saves them to a temporary path.
		Parameters:
			main_url(str):The URL of the main page.
			updated_to (str): The latest date for which the database contains records.
			path (str): The directory path where the downloaded files will be saved.
			key_words(str,optional): Keywords to search for the file on the page.
			format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

		Returns:
			list or bool: A list of dictionaries with information about files that meet the criteria of being more recent than 'updated_to'.
							Returns False if no more recent files are found.
		"""

		# Convert updated_to string to datetime object				
		updated_to = format_date(updated_to)				
		
		# Initialize list to store file paths and URLs
		file_paths = []

		with sync_playwright() as pl:        
						
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
				
				# Get all anchor tags (<a>) on the page
				links = page.locator("a").all()

				for link in links:
					text = link.inner_text() 
					href = link.get_attribute("href")

					# Check if the link text contains the keywords
					if search_key_words(text, key_words):                        
						# Start download expectation and click the link
						with page.expect_download() as download_info:                        
							link.click()
						download = download_info.value
						download_path = os.path.join(path,download.suggested_filename)  
						download.save_as(download_path)
						break # Exit the loop after downloading the first matching file
				
				# Store information about the downloaded file                            
				file_paths.append(
					{
						'tmp_path': download_path,                        
						'download_url': href
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
		try:
			# Convert 'updated_to' from string to datetime object
			updated_to = format_date(updated_to,format)
			
			# Initialize list to store files that are newer than updated_to
			list_files=[]
			
			# Retrieve the temporary file path of the first file in the list         
			tmp_path = files_paths[0].get('tmp_path')

			# Read the CSV file into a pandas DataFrame
			df = pd.read_csv(tmp_path)      
			
			# Get the name of the first column (where the date is expected to be)      
			first_col = df.columns[0]

			# Convert the first column to datetime format using the expected pattern
			# errors="raise" will stop execution if a date cannot be parsed
			df[first_col] = pd.to_datetime(df[first_col])
			
			# Drop any rows where the first column (date) is NaN or NaT
			df = df.dropna(subset=[first_col])            

			# Get the most recent (maximum) date from that column
			last_date = df[first_col].max()            

			# Compare the most recent date in the file with 'updated_to'
			if(last_date.date()>updated_to.date()):                          
				list_files.append(
					{
						"tmp_path": tmp_path,
						"updated_to": last_date.date().strftime(format),
						"download_url":files_paths[0].get('download_url')
					}
				) 

		except Exception as e:
			print(f"An error ocurred: {e}")
			traceback.print_exc()    
			return []  
		
		# Check if any files were found after the updated date
		if not len(list_files):
			print(f"There are NO files after {updated_to.strftime(format)}")
			return False
		return list_files

Executor_D_BO_000000561 = D_BO_000000561
Robot = D_BO_000000561
