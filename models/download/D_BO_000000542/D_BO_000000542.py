import traceback
import os
import shutil
from playwright.sync_api import sync_playwright
import pandas as pd
from models.download.tools.download_tools import format_date
from models.download.Download_Base import Download_Base

class D_BO_000000542(Download_Base):

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
            titles_xpath = '//div[contains(@class,"fiats2-single-header")]//h1 | //div[contains(@class,"fiats2-single-header")]//div[contains(@class,"subtitle_center")]'
            dayly_button_xpath = '//div[@class="_switcher"]/a[@data-val="24H"]'

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
                
                # Set up response interceptor to capture API calls
                api_responses_json = []
                def log_responses(response):
                    content_type = response.headers.get("content-type", "")
                    if 'application/json' in content_type:
                        content = response.json()
                        if 'items' in content:
                            api_responses_json.append(content)
                page.on('response', log_responses)

                # Navigate to target URL and interact with page elements
                page.goto(main_url, wait_until='domcontentloaded')
                page.wait_for_selector('#chart-market-stat')
                page.locator(dayly_button_xpath).click()
                page.wait_for_timeout(3*1000)

                # Extract and transform historical data from API responses
                titles = [[item.inner_text()] for item in page.locator(titles_xpath).all()]                         

                historical_data = api_responses_json[-1]
                historical_data_transformed = {'fecha': historical_data['categories']}
                for item in historical_data['items']:
                    historical_data_transformed[item['tm']] = item['values']
                titles.append(historical_data_transformed.keys())

                historical_data_df = pd.DataFrame(historical_data_transformed)
                
                # Check if new data exists by comparing dates
                historical_data_df['fecha'] = pd.to_datetime(historical_data_df['fecha'],format='%Y-%m-%d %H:%M:%S')
                date = historical_data_df['fecha'].max()

                if date <= updated_to:
                    print('There is no new data')
                    return []
                
                historical_data_df = pd.concat([pd.DataFrame(titles,columns=historical_data_df.columns),historical_data_df],)                
                
                # Save data to Excel file
                file_path = os.path.join(path,f"{key_words}.xlsx")
                historical_data_df.to_excel(file_path, index=False, header=False)
                        
                return [{
                    "tmp_path":file_path,
                    "updated_to":date.strftime(format=format),
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

Executor_D_BO_000000542 = D_BO_000000542
Robot = D_BO_000000542
