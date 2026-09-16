import traceback
import os
import shutil
import re
import pandas as pd
from playwright.sync_api import sync_playwright
from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number

class D_BO_000000545(Download_Base):

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

        # Prepare temporary path
        path = os.path.join(path, 'tmp')
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path)

        # Convert updated_to from string to datetime object
        updated_to = format_date(updated_to)

        # Define XPaths and values to interact with the page
        frame_xpath = '//iframe[@name="indiframe"]'
        titles_xpath = '//div[@class="bcbs-subtitulo"]//h3'
        headers_xpath = '//table[@class="tablaborde"]//th'
        rows_xpath = '//table[@class="tablaborde"]//tr'
        
        # Regular expression to match dates in text
        re_date = r'\b(\d{1,2})\b\D*((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\b\D*\b(\d{4})\b'

        with sync_playwright() as pl:
            try:
            # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                context.set_default_timeout(300000)
                page = context.new_page()

                page.goto(main_url, wait_until='domcontentloaded')
                page.wait_for_selector(frame_xpath,state='attached')

                # Access the iframe and its content
                print("Accessing iframe content...")
                frame = page.frame(name="indiframe").frame_element().content_frame()                
                frame.wait_for_selector('//body/table',state='attached')

                # Extract titles containing dates
                print("Extracting titles...")
                titles = frame.locator(titles_xpath).all_inner_texts()

                print("Searching for a date inside titles...")
                date = [d for t in titles if (d:=re.search(re_date,t,re.IGNORECASE))]
                date = date[0].group(1,2,3)                
                month = m if (m:=month_to_number(date[1])) else month_abr_to_number(date[1])
                data_date = format_date(f'{date[2]}-{month}-{date[0]}')
                print(f"Data date extracted: {data_date.strftime(format=format)}")

                # Compare with updated_to date
                if data_date<=updated_to:
                    print(f"No new data available. Data date ({data_date.strftime(format=format)}) <= updated_to ({updated_to.strftime(format=format)})")
                    return[]

                # Extract table headers and rows
                print("Extracting table headers...")                
                headers = frame.locator(headers_xpath).all_inner_texts()

                print("Extracting table rows...")
                rows = [item.locator('//td').all_inner_texts() for item in frame.locator(rows_xpath).all()]

                # Insert headers as the first row and include titles
                rows.insert(0,headers)
                rows = [[i] for i in titles] + [i for i in rows if i]

                df = pd.DataFrame(rows)

                # Save data to Excel file
                file_path = os.path.join(path,f"{key_words}.xlsx")
                print(f"Saving data to Excel file: {file_path}")
                df.to_excel(file_path,index=False,header=False)

                print("Extraction completed successfully.")   
                return [{
                    "tmp_path":file_path,
                    "updated_to":data_date.strftime(format=format),
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

Executor_D_BO_000000545 = D_BO_000000545
Robot = D_BO_000000545
