import sys, traceback, os,time, shutil,re
sys.path.append("..")
from playwright.sync_api import sync_playwright
import pandas as pd
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number
from models.download.Download_Base import Download_Base

class D_BO_000000271(Download_Base):

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

            re_date = r'(\d{1,2})\D*((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\D*(\d{4})'

            # Erase the previous tmp path and create the a new one 
            path = os.path.join(path, 'tmp')
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path)
            
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=False)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                context.set_default_timeout(1800000)
                page = context.new_page()
                page.goto(main_url, wait_until='load')
                
                page.wait_for_timeout(3*1000)
                cookies_button = page.locator('#onetrust-accept-btn-handler')
                if cookies_button:
                    cookies_button.click()
                page.wait_for_selector('//button[@aria-label="Mostrar la Clasificación Mundial completa"]',state="visible")
                
                # Extract link for "precios mercado"
                show_more_data_button = page.query_selector('//button[@aria-label="Mostrar la Clasificación Mundial completa"]')
                show_more_data_button.click()
                time.sleep(5)

                # Extract date of the last data entry
                date = re.search(re_date, page.query_selector('//div[@class="ranking-update-dates_dateItem__t9Z__ ranking-update-dates_justUpdated__dtDaJ"]').inner_text(), re.IGNORECASE).group(1,2,3)
                year = date[2]
                month = month_to_number(date[1]) if month_to_number(date[1]) else month_abr_to_number(date[1])
                day = date[0]
                data_date = format_date(f"{year}-{month}-{day}")

                # Check if there is new data available
                if data_date <= updated_to:
                    print(f"There is no data after the date: {updated_to.strftime(format=format)}")
                    return []
                
                # Extract data rows
                headers = page.query_selector_all('//table//thead//th')
                headers = [i.inner_text() for i in headers]
                page_rows = page.query_selector_all('//table//tbody/tr')
                page_rows = [[i.inner_text() for i in row.query_selector_all("td")] for row in page_rows]
                
                
                # Cleaning rows based on updated_to date
                df = pd.DataFrame(page_rows,columns=headers)
                print(df)
                df[df.columns[0]] = df[df.columns[0]].str.split('\n', expand=True)[0]
                df.columns = ["Posicion"] + list(df.columns.values[1:])
                df["Fecha"] = data_date.strftime(format)
                df = df[["Fecha"] + list(df.columns[:-1])]

                # Save data to excel file
                file_path = os.path.join(path,f"{key_words}.xlsx")
                df.to_excel(file_path,index=False)
                print("Data was extracted.")

                #Return information about the extracted data
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
#     robot = D_BO_000000271()
#     
#     x = robot.check_new_data(main_url="https://es.fifa.com/fifa-world-ranking/ranking-table/men/",updated_to="2024-03-4",path = r'\\10.0.0.9\spim\FIFA\Ranking Mundial', key_words="precios mercado")
#     print(x)
#     # y = robot.compare_files(files_paths=[{"tmp_path": r"C:\Users\Kevin Padilla\Downloads\01.03.xlsx"}],updated_to="2023-01-21")
#     # print(y)

Executor_D_BO_000000271 = D_BO_000000271
Robot = D_BO_000000271
