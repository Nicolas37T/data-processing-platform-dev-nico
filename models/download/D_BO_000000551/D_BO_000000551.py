import os
import shutil
import re
import pandas as pd
import traceback
from playwright.sync_api import sync_playwright
from datetime import date
from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import format_date, last_day_month

class D_BO_000000551(Download_Base):

    def verify_download(self,main_url, updated_to, path, format='%Y-%m-%d'):
        """
        Verifies and downloads type II files after the specified update date and saves them to a temporary path.
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

            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0 Win64 x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36'
                )
                page = context.new_page()
                page.goto(main_url, wait_until='domcontentloaded')

                turist_xpath = '(//div[@class="standard-arrow list-divider bullet-top"]/ul/li/a)[1]'
                link = page.locator(turist_xpath)

                # Erase the previous tmp path and create the a new one        
                path = os.path.join(path, "tmp")

                # Verifed if the folder exist else delete it to create of new
                if os.path.exists(path):
                    shutil.rmtree(path)
                os.makedirs(path)

                # Return list of all years                    
                years = re.findall(r'\b\d{4}\b', link.text_content()) 

                max_year = max(map(int, years))                    

                # Download files that meet the criteria
                if max_year>= updated_to.year:                                    
                    with page.expect_download() as download_info:
                        link.click()

                    download = download_info.value

                    # Bolivia – Cotización Oficial de Minerales por Tipo de Mineral según Año y Mes 1990 – 2025
                    download_path = os.path.join(path, str(max_year)+"_"+"turist.xls")                  

                    download.save_as(download_path)
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
        if not file_paths:		
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
            list: A list of dictionaries containing information about files that meet the condition of being later than a specific reference date.
        """        
        updated_to = format_date(updated_to,format)
        list_files=[]

        # Browse the list of dictionaries
        for file in files_paths:
            tmp_path = file.get('tmp_path')            

            # Look for the main header in the first 20 rows
            df_preview = pd.read_excel(tmp_path, header=None, nrows=20)
            row_header = None
        
            for i, row in df_preview.iterrows():
                text_row = row.astype(str).str.strip()                           
                if text_row.eq("CIUDAD Y TIPO DE VISITANTE").any():
                    print(f"Header detected in pandas index {i}")                    
                    row_header = i
                    break

            # print(df_preview)

            if row_header is not None:
                # Extract the row of years and months
                row_years = df_preview.iloc[row_header]
                row_months = df_preview.iloc[row_header+1]

                # Extract only valid years (4 digits) in the row
                extracted_years = row_years.astype(str).str.extract(r'(\d{4})')[0]
                valid_years = extracted_years.dropna().astype(int)
                if not valid_years.empty:                                        

                    # Gets the last year from the maximum
                    last_year = valid_years.max()
                    # print(last_year)
                    
                    # Get the index of the columns containing the last year
                    last_year_col = row_years[row_years.astype(str).str.contains(str(last_year))].index[0] #return a serie
                    # print("ultimo anio col: ", last_year_col)

                    # Find the month from the index of the last year column
                    months_since = row_months.loc[last_year_col:] #col 67 in next
                        
                    # Captures months that are not null, empty, or total
                    valid_months = months_since[
                        months_since.notna() &
                        (months_since.astype(str).str.strip() != "") &                
                        months_since.astype(str).str.upper().str.contains("TOTAL") == False
                    ]
                    if valid_months.empty:
                        print("No valid months found in the file.")
                    else: 
                        # The last month is obtained
                        last_month = valid_months.iloc[-1]
                        last_month_col = valid_months.index[-1]
                        # print(last_month)

                        months = {
                            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
                            'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
                        }                                
                        # We define the last date
                        date_max = date(int(last_year), int(months.get(last_month.lower())), last_day_month(int(last_year),int(months.get(last_month.lower()))))
                        date_formated = date_max.strftime(format)
                        
                        # We add to the list if it meets the given criteria
                        if(date_max>updated_to.date()):                
                            list_files.append(
                                {
                                    "tmp_path": tmp_path,
                                    "updated_to": date_formated,
                                    "download_url":'-', 
                                }
                            )
                else:
                    print("No valid years were found in the file.")
            else:
                print("The expected header was not found in the file.")

        return list_files

Executor_D_BO_000000551 = D_BO_000000551
Robot = D_BO_000000551
