import os
import shutil
import traceback
import random
import pandas as pd
from datetime import datetime 
from io import StringIO
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number
from models.download.Download_Base import Download_Base

class D_PE_000000006(Download_Base):

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
        now = datetime.now()

        # Define XPaths
        container_xpath = '//div[contains(@class,"tipo-de-cambio")]//div[contains(@class, "tip-contenedor")]//div[contains(@class,"align-top")]'
        title1_xpath = '//h3[@class="titulo-menor"]'         
        table_xpath = '//table//tr'
        try:
            with sync_playwright() as pl:
                print(f"[INFO] Launching browser and navigating to: {main_url}")
                browser = pl.chromium.launch(headless=False)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()

                # Navigate to target page
                page.goto(main_url, wait_until='domcontentloaded')
                print("[INFO] Page loaded. Simulating user activity...")

                # Simulate mouse movement to mimic real user
                page.mouse.move(x=random.randint(100,1000),y=random.randint(100,1000),steps=random.randint(3,15))
                page.wait_for_timeout(random.randint(2,10)*1000)                

                page.wait_for_selector(container_xpath,state='attached')

                # Extract relevant DOM elements
                container = page.locator(container_xpath).last
                title1 = container.locator(title1_xpath).inner_text()                
                rows = [item.locator("xpath=.//td | .//th").all_inner_texts() for item in container.locator(table_xpath).all()]
                print(f"[DEBUG] Table extracted with {len(rows)} rows.")

                # Extract and parse date from the first data row
                date = rows[0][1]
                date = [item.replace('.','').strip() for item in date.split()]
                month = m if (m:=month_abr_to_number(date[0])) else month_to_number(date[0])
                data_date = format_date(f'{now.year}-{month}-{date[1]}')
                
                # Check if data is already updated
                if data_date <= updated_to:
                    print(f"[INFO] No new data available. Latest in database: {updated_to.strftime(format)}")
                    return []

                # Prepend titles to table
                rows.insert(0,[title1])
                
                # Save to DataFrame
                df = pd.DataFrame(rows)
                
                # Save data to Excel file
                file_path = os.path.join(path,f"{key_words}.xlsx")
                print(f"[INFO] Saving extracted data to Excel file: {file_path}")
                df.to_excel(file_path,index=False,header=False)

                print("[SUCCESS] Data extraction completed successfully.")   
                return [{
                    "tmp_path":file_path,
                    "updated_to":data_date.strftime(format=format),
                    "download_url":'-',
                }]

        except Exception as e:
            print(f"[ERROR] An exception occurred during execution: {e}")
            traceback.print_exc()
            return []        

Executor_D_PE_000000006 = D_PE_000000006
Robot = D_PE_000000006
