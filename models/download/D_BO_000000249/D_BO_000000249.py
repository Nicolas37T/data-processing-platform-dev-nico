import sys, traceback, os,time, shutil
sys.path.append("..")
from playwright.sync_api import sync_playwright
from datetime import datetime
import pandas as pd
from models.download.tools.download_tools import format_date
from models.download.Download_Base import Download_Base

class D_BO_000000249(Download_Base):

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
            updated_to = format_date(f"{datetime.today().year}-01-01")

            base_url = "http://www.sicsantacruz.com/sicv3/"

            # XPath to locate elements
            precios_mercado_link_xpath = '//div[@class="hero-image-services"]//a[2]'
            # page_links_xpath = '//nav[@class="menu-secundario"]//a'

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
                page = context.new_page()
                page.goto(main_url, wait_until='domcontentloaded')
                
                # Extract link for "precios mercado"
                precios_mercado_link = base_url + page.query_selector(precios_mercado_link_xpath).get_attribute("href")
                
                # Navigate to precios mercado link
                page.goto(precios_mercado_link, wait_until="load")
                page.wait_for_selector('//*[@id="tablaPrecios"]//tbody/tr[2]', state='visible')

                # Extract the city 
                city = page.query_selector('//div[@class="container"]/h1').inner_text()

                # Extract date of the last data entry
                date = page.query_selector('//*[@id="tablaPrecios"]//tbody/tr[1]/td[last()]').inner_text()
                data_date = format_date(date,format='%d-%m-%Y')

                 # Check if there is new data available
                if data_date <= updated_to:
                    print(f"There is no data after the date: {updated_to.strftime(format=format)}")
                    return []
                
                # Extract column headers
                columns = page.query_selector_all('//*[@id="tablaPrecios"]//thead//th')
                columns = [column.inner_text() for column in columns]
                columns = columns[1:]

                # Extract data rows
                rows = []
                while True:
                    page_rows = page.query_selector_all('//*[@id="tablaPrecios"]//tbody/tr')
                    page_rows = [[i.inner_text() for i in row.query_selector_all("td")] for row in page_rows]
                    rows.extend(page_rows)

                    next_button = page.query_selector('//a[@class="paginate_button next"]')
                    if not next_button:
                        break
                    next_button.click()
                    time.sleep(2)

                    last_date = page.query_selector('//*[@id="tablaPrecios"]//tbody/tr[last()]/td[last()]').inner_text()
                    last_date = format_date(last_date,format='%d-%m-%Y')
                    
                    if last_date<=updated_to:
                        break
                
                # Filter rows based on updated_to date
                if not rows:
                    print(f"There is no data, extract error")
                    return []
                rows = [row[1:] for row in rows if format_date(row[-1],format='%d-%m-%Y')>updated_to]
                df = pd.DataFrame(rows,columns=columns)
                df['ciudad'] = city.capitalize()
                
                # Save data to CSV file
                file_path = os.path.join(path,f"{key_words}.csv")
                df.to_csv(file_path,index=False,sep=";")
                print("Data was extracted.")

                # Return information about the extracted data
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


# if __name__ == "__main__":
#     robot = Executor_D_BO_000000249()
    
#     x = robot.check_new_data(main_url="http://www.sicsantacruz.com/sicv3/index.php",updated_to="2024-06-24",path = r'/home/datax/Downloads', key_words="precios mercado")
#     print(x)
#     # y = robot.compare_files(files_paths=[{"tmp_path": r"C:\Users\Kevin Padilla\Downloads\01.03.xlsx"}],updated_to="2023-01-21")
#     # print(y)

Executor_D_BO_000000249 = D_BO_000000249
Robot = D_BO_000000249
