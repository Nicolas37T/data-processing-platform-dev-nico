import traceback
import os
import shutil
from playwright.sync_api import sync_playwright
import pandas as pd
from models.download.tools.download_tools import format_date
from models.download.Download_Base import Download_Base

class D_BO_000000495(Download_Base):

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
            rows_xpath = '//div[@data-triami-bind="TableResponsive:1"]/table//tbody/tr'
            headers_xpath = '//div[@data-triami-bind="TableResponsive:1"]/table//thead/tr/th'
           

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
                
                page.wait_for_selector('//div[@data-triami-bind="TableResponsive:1"]/table',state="visible")                

                rows = [[i.inner_text().strip().replace('%','') for i in row.query_selector_all("td")] for row in page.query_selector_all(rows_xpath)]
                headers = [item.inner_text().strip() for item in page.query_selector_all(headers_xpath)]
                df = pd.DataFrame(rows,columns=headers)                

                if df.empty:
                    print(f"There is no data after the date: {updated_to.strftime(format=format)}")
                    return []  
                
                # Check if there is new data available
                date = format_date(headers[1],format="%m-%d-%Y")
                
                if date <= updated_to:
                    print(f"There is no data after the date: {updated_to.strftime(format=format)}")
                    return []                
                

                # Save data to Excel file
                file_path = os.path.join(path,f"{key_words}.xlsx")
                df.to_excel(file_path, index=False)
                        
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
#     robot = Executor_D_BO_000000495()
#     x =robot.check_new_data(main_url="https://www.global-rates.com/en/interest-rates/libor/libor.aspx",updated_to='2024-08-01', path=r"D:\DATAX\data-processing-platform\models\download\D_BO_000000495", key_words=" oro plata")
#     print(len(x))
#     print(x)
    # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"/opt/airflow/models/download/D_BO_000000484/TD_08_08_2024.pdf"}, {'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"/opt/airflow/models/download/D_BO_000000484/TD_08_08_2024.xlsx"}]
    # y = robot.compare_files(files_paths=files,updated_to="2024-08-05")
    # print(y)


Executor_D_BO_000000495 = D_BO_000000495
Robot = D_BO_000000495
