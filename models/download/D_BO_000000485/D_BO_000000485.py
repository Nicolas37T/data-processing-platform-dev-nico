import traceback
import re
import os
import shutil
import time
from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime, timedelta
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number
from models.download.Download_Base import Download_Base

class D_BO_000000485(Download_Base):

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
            today = datetime.today()
            init_date = today - timedelta(days=7)
            
            # Define XPaths and values to interact with the page
            search_button_xpath = '//*[@id="subcateg1_data5"]/input[@type="button"]'
            see_button_xpath = '//form[@name="formone"]//input[@type="submit"]'
            rows_xpath = '//form[@name="formone"]/following-sibling::table//tr'
            categ_id = "5"
            re_date = r'(\d{1,2})\D*((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\D*(\d{4})'

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

                # Select options and initiate search
                print(f"Selecting category : Metales Preciosos")
                page.locator("#subcateg1").select_option(categ_id)
                page.locator("#combos1_5").select_option("2")
                page.locator(search_button_xpath).click()

                # Wait for iframe to load and interact with it
                page.frame_locator('//iframe[@name="indiframe"]').locator('#sdd').wait_for()                
                time.sleep(3)

                frame = page.frame(name="indiframe").frame_element().content_frame()
                frame.wait_for_selector('//select[@id="moneda"]', state="visible")

                metal_options = [(option.inner_text(),option.get_attribute("value")) for option in frame.query_selector_all('//*[@id="moneda"]/option')]

                print(f"Setting date range from {init_date.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}")
                frame.locator("#sdd").select_option(str(init_date.day))
                frame.locator("#smm").select_option(str(init_date.month))
                frame.locator("#saa").select_option(str(init_date.year))
                frame.locator("#edd").select_option(str(today.day))
                frame.locator("#emm").select_option(str(today.month))
                frame.locator("#eaa").select_option(str(today.year))
                
                dataframes = []
                for option in metal_options:
                    print(f"Selecting metal option: {option[0]}")
                    frame.locator('//select[@id="moneda"]').select_option(option[1])
                    frame.locator(see_button_xpath).click()

                    time.sleep(5)
                    frame.wait_for_selector('//form[@name="formone"]/following-sibling::table//tr[1]', state="visible")

                    # Extract the data from the results and format
                    rows = [[i.inner_text().replace('\n',' ') for i in row.query_selector_all("td")] for row in frame.query_selector_all(rows_xpath)]
                    df = pd.DataFrame(rows[1:],columns=rows[0])

                    # Convert and format date columns
                    dates = df["Fecha"].str.extract(re_date,flags=re.IGNORECASE,expand=True)
                    dates[1] = dates[1].apply(lambda x: month_to_number(x) if month_to_number(x) else month_abr_to_number(x))
                    df["Fecha"] = dates[[2, 1, 0]].astype(str).agg('-'.join, axis=1)

                    if not df.empty:
                        dataframes.append(df)

                # Check if there is new data available
                date = dataframes[0]["Fecha"].iloc[-1]
                date = format_date(date)
                
                if date <= updated_to:
                    print(f"There is no data after the date: {updated_to.strftime(format=format)}")
                    return []
                
                # Save data to Excel file
                file_path = os.path.join(path,f"{key_words}.xlsx")
                with pd.ExcelWriter(file_path) as writer:
                   dataframes[0].to_excel(writer, sheet_name='Oro', index=False)
                   dataframes[1].to_excel(writer, sheet_name='Plata', index=False)
                        
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
        
# if __name__ == "__main__":
#     robot = Executor_D_BO_000000485()
#     x =robot.check_new_data(main_url="https://www.bcb.gob.bo/?q=cotizaciones_tc",updated_to='2024-08-01', path="./download/D_BO_000000485", key_words=" oro plata")
#     print(len(x))
#     print(x)
    # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"/opt/airflow/models/download/D_BO_000000484/TD_08_08_2024.pdf"}, {'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"/opt/airflow/models/download/D_BO_000000484/TD_08_08_2024.xlsx"}]
    # y = robot.compare_files(files_paths=files,updated_to="2024-08-05")
    # print(y)


Executor_D_BO_000000485 = D_BO_000000485
Robot = D_BO_000000485
