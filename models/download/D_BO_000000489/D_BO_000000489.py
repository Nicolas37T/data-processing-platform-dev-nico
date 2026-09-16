import traceback
import os
import shutil
import time
from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime, timedelta
from models.download.tools.download_tools import format_date
from models.download.Download_Base import Download_Base

class D_BO_000000489(Download_Base):

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
            consultas_link_xpath = '//div[@class="field--item"]//a[contains(@href,"consultas")]'
            product_options_xpath = '//*[@id="edit-product"]//option'
            rows_xpath = '//div[@class="table-responsive"]//tbody/tr'
            pizarra_estimativos_id = "any"

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
                
                # Get the link for the "consultas" page and navigate there
                print("Navigating to the 'consultas' page...")
                consultas_link = page.query_selector(consultas_link_xpath).get_attribute('href')
                page.goto(consultas_link, wait_until='load')
                page.wait_for_selector('//*[@id="cms-tweaks-query-form"]//button[@data-id="edit-product"]', state='visible')                

                # Extract available product options
                product_options = [(option.inner_text(), option.get_attribute("value")) for option in page.query_selector_all(product_options_xpath) if not "seleccione" in option.inner_text().lower()]

                # Set the filter to 'pizarra estimativos' and dismiss modal window
                print("Selecting 'Pizarra Estimativos' filter...")
                page.locator('#edit-type').select_option(pizarra_estimativos_id)
                page.wait_for_selector('//div[@class="modal fade in"]//button[@data-dismiss="modal"][1]', state='visible')
                page.locator('//div[@class="modal fade in"]//button[@data-dismiss="modal"]').first.click()

                # Fill in date range and submit form
                print(f"Filling in date range from {init_date.strftime(format)} to {today.strftime(format)}...")
                page.wait_for_selector('#edit-date-start', state="visible")
                page.locator('#edit-date-start').fill(init_date.strftime(format))
                page.locator('#edit-date-end').fill(today.strftime(format))

                dataframes = []
                # Loop through each product option, extract data, and store it in DataFrame
                for product in product_options:
                    print(f"Processing product: {product[0]}...")
                    page.locator('#edit-product').select_option(product[1])
                    page.locator('#edit-submit').click()
                    time.sleep(2)

                    page.wait_for_selector('//div[@class="table-responsive"]', state='visible')

                    rows = [[i.inner_text().replace('.','').replace('$','') for i in row.query_selector_all("td")] for row in page.query_selector_all(rows_xpath)]
                    df = pd.DataFrame(rows,columns=["Fecha", "Estimado", "Precio"])
                    df["Producto"] = product[0]
                    df["Fecha"] = pd.to_datetime(df["Fecha"],format="%d/%m/%Y")

                    if not df.empty:
                         dataframes.append(df)                    

                # Merge all dataframes into one
                df_merged = pd.concat(dataframes,axis=0)                
                
                # Check if there is new data available
                date = df_merged["Fecha"].iloc[-1]
                if date <= updated_to:
                    print(f"There is no data after the date: {updated_to.strftime(format=format)}")
                    return []
                
                # Convert date back to string with the desired format
                df_merged['Fecha'] = df_merged['Fecha'].dt.strftime(format)
                df_merged = df_merged.loc[:,["Producto", "Fecha", "Estimado", "Precio"]]

                # Save data to Excel file
                file_path = os.path.join(path,f"{key_words}.xlsx")
                df_merged.to_excel(file_path, index=False)
                        
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
#     robot = Executor_D_BO_000000489()
#     x =robot.check_new_data(main_url="https://www.cac.bcr.com.ar/es",updated_to='2024-08-01', path="./download/D_BO_000000489", key_words=" oro plata")
#     print(len(x))
#     print(x)
    # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"/opt/airflow/models/download/D_BO_000000484/TD_08_08_2024.pdf"}, {'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"/opt/airflow/models/download/D_BO_000000484/TD_08_08_2024.xlsx"}]
    # y = robot.compare_files(files_paths=files,updated_to="2024-08-05")
    # print(y)


Executor_D_BO_000000489 = D_BO_000000489
Robot = D_BO_000000489
