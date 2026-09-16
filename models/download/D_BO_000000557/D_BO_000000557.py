import re, traceback
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date, text_extract,search_key_words,last_day_month,month_to_number
from datetime import datetime
from models.download.Download_Base import Download_Base

class D_BO_000000557(Download_Base):

	def get_file_url(self, main_url, updated_to,key_words="Margen solvencia patrimonio", format='%Y-%m-%d'):
		"""
		Extracts download URLs for files dated after update_to date.

		Parameters:
			main_url (str): The URL of the main page.
			updated_to (str): The latest date for which the database contains records.
			format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

		Returns:
			list: A list of download URLs for files that meet the criteria.
		"""

		with sync_playwright() as pl:
			# Convert updated_to string to datetime object
			updated_to = format_date(updated_to)
			try:
				# Launch browser and navigate to main URL
				print(f"Launching browser and navigating to {main_url} ...")
				# browser = pl.chromium.launch()
				browser = pl.chromium.launch(headless=True)
				context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
				page = context.new_page()
				page.goto(main_url)

				# Select element for downloading
				select_element = page.locator('//select[@id="webdocs___UNE___DS___Estadisticas"]')
				
				# Filter options based on key words
				options = [option.inner_text() for option in select_element.locator('option').all() if search_key_words(text=option.inner_text(),key_word=key_words) ]                        
				select_element.select_option(label=options[0])

				# Select date element
				select_element_date=page.locator('(//div[@id="render_webdocs___UNE___DS___Estadisticas"]//select[@class="select2"])[2]')
				select_element_date.locator('option').first.wait_for(state="attached")

				# Get available years greater than or equal to 'updated_to'
				years = [int(option_date.inner_text()) for option_date in select_element_date.locator('option').all() if int(option_date.inner_text())>=updated_to.year]
				
				# Pattern to extract year and month from href
				pattern = re.compile(r"/(\d{4})/A\s*([A-Za-zÁÉÍÓÚáéíóúñÑ]+)(?:[^/]*)\.pdf", re.IGNORECASE)
				hrefs = []

				# Iterate over available years to filter results
				for year in years:
					select_element_date.select_option(label=str(year)) # Select year from the dropdown
					
					page.wait_for_timeout(1500) # Wait for the page to load after selecting the year
					
					# Get all download links for the selected year
					links = page.query_selector_all("#renderfiles_webdocs___UNE___DS___Estadisticas a")

					# Process each link to extract and validate the file's date
					for link in links:
						href = link.get_attribute("href")  # Get the link URL
						match = pattern.search(href) # Match the URL against the pattern

						# If the URL matches the pattern and date is valid
						if href and match:
							year, month = match.groups() # Extract year and month                         
							num_month=month_to_number(month.lower()) # Convert month name to number
							last_day_url = last_day_month(int(year),num_month) # Get last day of the month                           
							date_url = datetime(int(year), num_month, last_day_url) # Create a datetime object     

							# If the file's date is later than the 'updated_to' date, add it to the list
							if date_url>updated_to:                                
								hrefs.append(href)                   
				return hrefs
			
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

	def compare_files(self, files_paths, updated_to, format='%Y-%m-%d'):
		"""
		Extract the date from a list of files to compare and filter which are more recent than the updated_to date.

		Parameters:
			files_paths (list): List of dictionaries containing information about files.
			updated_to (str): The latest date for which the database contains records.
			format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

		Returns:
			list or bool: A list of dictionaries with information about files that meet the criteria of being more recent than 'updated_to'. Returns False if no more recent files are found.
		"""
		print("Comparing files...")

		# List to store file dictionaries
		files_dicts = []

		# Convert updated_to string to datetime object
		updated_to = format_date(updated_to)        

		# Regular expression to extract the month and year from file content
		re_date = re.compile(r"A\s+([A-Za-zÁÉÍÓÚáéíóúñÑ]+)\s+(\d{4})", re.IGNORECASE)

		# Iterate over each file in the provided list of file paths
		for file in files_paths:                    
			lines = text_extract(file["tmp_path"])                                    
			for line in lines:
				
				# Extract the text content from the current file using the 'text_extract' function
				match = re_date.search(line)

				if match: 
					# If a match is found, extract the month and year from the match groups
					month, year = match.groups()
					print(f"Month: {month}, Year: {year}")
					break
			
			# Convert the extracted month (in text) to a numeric value using the 'month_to_number' function
			num_month=month_to_number(month.lower())

			# Determine the last day of the extracted month and year using the 'last_day_month' function
			last_day_url = last_day_month(int(year),num_month)
			
			# Create a datetime object for the last day of the month and year
			date_pdf_intern = datetime(int(year), num_month, last_day_url)
			
			# Compare the extracted date with the 'updated_to' date
			if date_pdf_intern>updated_to:        

				# If the file is more recent than 'updated_to', add it to the results list            
				files_dicts.append(
					{
						'updated_to': date_pdf_intern.strftime(format), # Format the datetime object as a string
						'download_url': file['download_url'], # Include the download URL of the file
						'tmp_path': file['tmp_path'] # Include the temporary path of the file
					}
				)                                           

		# Check if any files were found after the updated date
		if not len(files_dicts):
			print(f"There are NO files after {updated_to.strftime(format)}")
			return False
		return files_dicts

Executor_D_BO_000000557 = D_BO_000000557
Robot = D_BO_000000557
