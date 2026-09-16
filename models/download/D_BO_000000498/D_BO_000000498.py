import traceback
import os
import shutil
import re
from playwright.sync_api import sync_playwright
import pandas as pd
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number
from models.download.Download_Base import Download_Base

class D_BO_000000498(Download_Base):

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
            rows_xpath = '//*[@id="table-section"]//table/tbody/tr'
            titles_xpath = '//*[@id="table-section"]/section/div[@style="text-align:center"]'
            headers_xpath = '//*[@id="table-section"]//table/thead/tr/th'
            date_xpath = '//*[@id="table-section"]/section/p'
            re_date = r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec))\D*(\d{1,2})\D*(\d{4})"           

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
                page.goto(main_url, wait_until='domcontentloaded')
                
                page.wait_for_selector('#table-section',state="visible")

                # Check if there is new data available
                date = page.query_selector(date_xpath).inner_text()
                date = re.search(re_date, date, re.IGNORECASE).group(1,2,3)
                month = date[0]
                month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
                date_formated = format_date(f"{date[2]}-{month}-{date[1]}")
                titles = page.locator(titles_xpath).locator('xpath=./h2|./p').all_inner_texts()
                
                if date_formated <= updated_to:
                    print(f"There is no data after the date: {updated_to.strftime(format=format)}")
                    return []   
                             
                # Extract data, and store it in DataFrame
                rows = [[i.inner_text().strip() for i in row.query_selector_all("td, th")] for row in page.query_selector_all(rows_xpath)]                
                headers = [item.inner_text().strip() for item in page.query_selector_all(headers_xpath)]
                
                df = pd.DataFrame(rows,columns=headers)                
                
                if df.empty:
                    print(f"There is no data after the date: {updated_to.strftime(format=format)}")
                    return []  

                for i,title in enumerate(reversed(titles)):
                    df.insert(0,column=f"titulo{len(titles)-i}",value=title)
                df['fecha'] = date_formated.strftime(format)

                # Save data to Excel file
                file_path = os.path.join(path,f"{key_words}.xlsx")
                df.to_excel(file_path, index=False)
                        
                return [{
                    "tmp_path":file_path,
                    "updated_to":date_formated.strftime(format=format),
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

Executor_D_BO_000000498 = D_BO_000000498
Robot = D_BO_000000498
