import os
import re
import random
import shutil
import traceback
import pandas as pd
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number
from models.download.Download_Base import Download_Base

class D_PY_000000003(Download_Base):

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
         # Convert updated_to string to datetime object
        updated_to = format_date(updated_to)

        # Erase the previous tmp path and create the a new one
        path = os.path.join(path, 'tmp')
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path)

        # Define XPaths for interacting with dropdowns and buttons
        calendar_button_xpath = '//div[@class="controls"]//span[@class="add-on"]'
        year_select_xpath = '//div[@class="ui-datepicker-title"]//select[@data-handler="selectYear"]'
        month_select_xpath = '//div[@class="ui-datepicker-title"]//select[@data-handler="selectMonth"]'
        day_button_xpath = '//table[@class="ui-datepicker-calendar"]//td[@title="Available"]'
        next_button_disabled_xpath = '//a[@class="ui-datepicker-next ui-corner-all ui-state-disabled"]'
        next_button_xpath = '//a[@class="ui-datepicker-next ui-corner-all"]'
        table_rows_xpath = '//*[@id="cotizacion-interbancaria"]//tr'

        # Regex to extract date in Spanish format
        re_date = r'(\d{1,2})\D*((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\D*(\d{4})'
        
        file_paths = []
        try:            
            with sync_playwright() as pl:
                print(f"[INFO] Launching browser and accessing {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()

                page.goto(main_url,wait_until='domcontentloaded')
                
                # Wait for and open the calendar
                page.wait_for_selector(calendar_button_xpath,state='visible')
                page.locator(calendar_button_xpath).click()

                # Select year and month from dropdowns
                page.wait_for_selector(year_select_xpath,state='visible')
                page.locator(year_select_xpath).select_option(f'{updated_to.year}')
                page.locator(month_select_xpath).select_option(f"{updated_to.month - 1}")

                while True:
                    days_buttons = page.locator(day_button_xpath).all()

                    for day in days_buttons:
                        day.click()                        
                        page.wait_for_timeout(random.randint(2,5)*1000)

                        page.wait_for_selector('#cotizacion-interbancaria')

                        rows = [row.locator('xpath=.//td | .//th').all_inner_texts() for row in page.locator(table_rows_xpath).all()]

                        # Insert column for currency code    
                        rows[1].insert(1,'CODIGO_MONEDA')

                        # Extract and format the date
                        date = re.search(re_date,rows[0][0],re.IGNORECASE).groups()
                        print(date)
                        month = m if (m:=month_abr_to_number(date[1])) else month_to_number(date[1])
                        date_formated = format_date(f'{date[2]}-{month}-{date[0]}')

                        # If the date is newer, save it
                        if date_formated>updated_to:
                            df = pd.DataFrame(rows)
                            file_path = os.path.join(path, f"{date_formated.strftime(format)}_{key_words}.xlsx")
                            print(f"[INFO] Saving extracted data to Excel file: {file_path}")
                            df.to_excel(file_path, index=False,header=False)

                            file_paths.append({
                                "tmp_path": file_path,
                                "updated_to": date_formated.strftime(format),
                                "download_url":'-',
                            })
                        
                        # Return to calendar
                        page.locator(calendar_button_xpath).click()
                    
                    # If 'next' is disabled, exit loop
                    next_button_disabled = page.locator(next_button_disabled_xpath)
                    if next_button_disabled.is_visible():
                        break

                    # Go to next calendar page
                    page.locator(next_button_xpath).click()
                    page.wait_for_timeout(2_000)
                    page.wait_for_selector(day_button_xpath,state='visible')

            if not len(file_paths):
                print(f"[INFO] No new files found after {updated_to.strftime(format)}.")
                return []
            
            print(f"[SUCCESS] Found and saved {len(file_paths)} new file(s).")
            return file_paths      

        except Exception as e:
            print(f"[ERROR] An error occurred during scraping: {e}")
            traceback.print_exc()
            return []

Executor_D_PY_000000003 = D_PY_000000003
Robot = D_PY_000000003
