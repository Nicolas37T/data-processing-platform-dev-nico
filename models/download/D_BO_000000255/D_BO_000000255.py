import traceback, os,re, shutil
from playwright.sync_api import sync_playwright
import pandas as pd
from functools import reduce
from models.download.tools.download_tools import format_date
from models.download.Download_Base import Download_Base

class D_BO_000000255(Download_Base):

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
            
            # Regular expression to find dates in text
            re_date = r'\d{1,2}.?\d{1,2}.?\d{4}'

            # XPath to locate elements
            rows_xpath = '//div[@class="moduletable _tabla_precios"]//tbody/tr'

            # Erase the previous tmp path and create the a new one 
            path = os.path.join(path, 'tmp')
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path)

            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch()
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url, wait_until='domcontentloaded')
                
                # Extract the date from the page
                date = page.query_selector('//div[@class="tit-precios"]').inner_text()
                date = re.search(re_date,date).group()

                # Format the extracted date
                data_date = format_date(date,format='%d-%m-%Y')
                print(updated_to,data_date)
                # Check if there is new data available
                if data_date <= updated_to:
                    print(f"There is no data after the date: {updated_to.strftime(format=format)}")
                    return []
                
                # Extract data rows
                rows = page.query_selector_all(rows_xpath)
                rows.pop(2)

                # Extract cell data from each row
                rows = [row.query_selector_all("td") for row in rows]
                rows = [[i.inner_text() for i in row] for row in rows]
                
                # Flatten the rows into a single list and prepend the date
                data_rows = [data_date.strftime(format=format)] + reduce(lambda x,y: x+y,rows)
                data_rows = [data_rows]
                print(data_rows)
                # Define column headers
                columns = ['Fecha','Precio del Pollo', 'Precio Gallina Descarte', 'Precio del Huevo (EXT)', 'Precio del Huevo (1RA)', 'Precio del Huevo (2DA)', 'Precio del Huevo (3RA)', 'Precio del Huevo (4TA)']

                # Create a DataFrame and save it to an Excel file
                df = pd.DataFrame(data_rows,columns=columns)
                file_path = os.path.join(path,f"{key_words}.xlsx")
                df.to_excel(file_path,index=False,)
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

if __name__ == "__main__":
    robot = Executor_D_BO_000000255()
    
    x = robot.check_new_data(main_url="https://www.adascz.com.bo/",updated_to="2024-02-12",path = r'D:\DATAX\data-processing-platform\models\download\D_BO_000000255', key_words="precio productores")
    print(x)
#     # y = robot.compare_files(files_paths=[{"tmp_path": r"C:\Users\Kevin Padilla\Downloads\01.03.xlsx"}],updated_to="2023-01-21")
#     # print(y)
#     robot.verify_url("https://www.adascz.com.bo/")

Executor_D_BO_000000255 = D_BO_000000255
Robot = D_BO_000000255
