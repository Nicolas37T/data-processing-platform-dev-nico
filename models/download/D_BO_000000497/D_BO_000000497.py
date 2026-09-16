import traceback
import re
import os
import shutil
from playwright.sync_api import sync_playwright
import pandas as pd
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number
from models.download.Download_Base import Download_Base

class D_BO_000000497(Download_Base):

    @staticmethod
    def get_date(str_date):
        re_date = r'(\d{1,2})\D(\w+)\D(\d{4})'
        re_match = re.search(re_date,str_date)
        if not re_match:
            return str_date
        date = re_match.groups()
        month = m if(m:=month_abr_to_number(date[1])) else month_to_number(date[1])
        return pd.to_datetime(f'{date[2]}-{month}-{date[0]}',format='%Y-%m-%d')

    def check_new_data(self, main_url, updated_to,path,key_words, format='%Y-%m-%d'):
        """
        Extracts data from the main_url dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            path (str): The directory path to store temporary files.
            key_words (str): A string used to name the CSV file.
            format (str): The format of the dates. Default is '%Y-%m-%d'.

        Returns:
            list: A list of dictionaries containing information about the extracted data.
        """

        with sync_playwright() as pl:
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)            
            
            # Define XPaths and values to interact with the page            
            titles_xpath = '//div[@class="bccr-contenedor-cuadro-indicadores"]//h1 | //div[@class="bccr-contenedor-cuadro-indicadores"]//h2'
            
            dates_xpath = '//*[@id="idTablaCuadroIndicadores"]//table//th'
            values_xpath = '//*[@id="idTablaCuadroIndicadores"]//table//td'


            # Erase the previous tmp path and create the a new one 
            path = os.path.join(path, 'tmp')
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path)
            
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                context.set_default_timeout(300000)
                page = context.new_page()

                # Navigate to target URL and interact with page elements
                page.goto(main_url, wait_until='domcontentloaded')
                page.wait_for_selector(dates_xpath)

                # Extract and transform historical data from API responses
                titles = [item.inner_text() for item in page.locator(titles_xpath).all()]
                
                dates = page.locator(dates_xpath).all_inner_texts()[-3:]
                values = page.locator(values_xpath).all_inner_texts()[-3:]
                
                dates = [Executor_D_BO_000000497.get_date(date) for date in dates]

                last_date = max(dates)
                if last_date <= updated_to:
                    print('There is no new data')
                    return []
                
                dates = titles + ['Date'] + dates
                values = [pd.NaT for t in titles] + ['Values'] + values

                df = pd.DataFrame({
                    "0":dates,
                    "1": values
                })
                

                #Save data to Excel file
                file_path = os.path.join(path,f"{key_words}.xlsx")
                df.to_excel(file_path, index=False, header=False)
                        
                return [{
                    "tmp_path":file_path,
                    "updated_to":last_date.strftime(format=format),
                    "download_url":'-',
                }]

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

Executor_D_BO_000000497 = D_BO_000000497
Robot = D_BO_000000497
