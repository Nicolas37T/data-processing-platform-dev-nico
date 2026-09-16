import re, os, time, traceback, requests, shutil
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date
from models.download.Download_Base import Download_Base

class D_BO_000000536(Download_Base):

    def download_tmp(self,path,file):
        """
        Downloads files from the specified URLs and saves them to the specified path.

        Parameters:
            path (str): The base path where files will be saved.
            file (dict): A dictionary containing the file details (URLs, code, updated date).

        Returns:
            list: A list of dictionaries with download URLs and file paths.
        """
        files_list = []
        
        
        # # Download the BG file
        # bg_response  = requests.get(file["bg_url"],headers=self.headers)
        # bg_file_path = os.path.join(path,f"{file['updated_to']}_{file['code']}_BG.pdf")

        # if 200 <= bg_response.status_code < 300:
        #     with open(bg_file_path, "wb") as bg_f:
        #         bg_f.write(bg_response.content)
        #     files_list.append(bg_file_path)
        # else: 
        #     print(f"Broken BG URL for code {file['code']}")    
        
        # Download the ER file
        er_response  = requests.get(file["er_url"],headers=self.headers)
        er_file_path = os.path.join(path,f"{file['updated_to']}_{file['code']}_ER.pdf")

        if 200 <= er_response.status_code < 300:
            with open(er_file_path, "wb") as er_f:
                er_f.write(er_response.content)
            files_list.append(er_file_path)
        else: 
            print(f"Broken ER URL for code {file['code']}")
        
        return files_list    

    def get_data(self, main_url, path, updated_to,format='%Y-%m-%d'):
        """
        Extracts data from URLs for files dated in the present year.

        Parameters:
            main_url (str): The URL of the main page.
            path (str): The path where files are stored.
            updated_to (str): The latest date for which the database contains records.
            format (str): The date format to use for the 'updated_to' field.

        Returns:
            str: A temporary path where the files were stored or an empty string if there are no files downloaded.
        """

        with sync_playwright() as pl:
            re_year = r'^\d{4}$'

            # Get the last year downloaded from the directory
            last_year_downloaded = max([d for d in os.listdir(path) if re.search(re_year,d)])

            # Create the directory structure to save files
            new_file_path = os.path.join(path, 'tmp')
            if os.path.exists(new_file_path):
                shutil.rmtree(new_file_path)
            os.makedirs(new_file_path)
            
            files_dicts = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                context.set_default_timeout(600000)
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')
                page.wait_for_selector('//a[@data-tab="eeff"]',state="visible")
                page.query_selector('//a[@data-tab="eeff"]').click()
                print("EEFF tab clicked")
                
                # Select the year and quarter options
                year_select = page.query_selector('#yearEEFF')
                year_select_options = [year.get_attribute('value') for year in year_select.query_selector_all('//option') if year.get_attribute('value') and int(year.get_attribute('value'))>=int(last_year_downloaded)]
                quarter_select = page.query_selector('#tipoTrimestre')
                quarter_select_options = [quarter.get_attribute('value') for quarter in quarter_select.query_selector_all('//option')]

                for year in year_select_options:
                    print(f"Selecting year: {year}")
                    year_select.select_option(year)
                    files_urls = []
                    for quarter in quarter_select_options:
                        print(f"Selecting quarter: {quarter}")
                        quarter_select.select_option(quarter)
                        time.sleep(1)
                        page.wait_for_selector('//div[@class="bbvpress-list__loading"]',state='hidden')
                        while True:
                            rows = page.query_selector_all('//*[@id="bbvDataTable-emisor"]/tbody/tr')
                            if not len(rows):
                                print("No more rows found")
                                break
                            for row in rows:
                                code = row.query_selector('//td[1]').inner_text()
                                date = row.query_selector('//td[3]').inner_text()
                                bg_url = row.query_selector('//td[4]/a')
                                er_url = row.query_selector('//td[5]/a')
                                if not (bg_url and er_url):
                                    continue
                                files_urls.append({
                                    "code": code,
                                    "updated_to": format_date(date, format="%d/%m/%Y").strftime(format=format),
                                    "bg_url": bg_url.get_attribute('href').strip().replace('\t',''),
                                    "er_url": er_url.get_attribute('href').strip().replace('\t','')
                                })
                            # Click the next button if it exists
                            next_button = page.query_selector('//nav[@class="pagination-bbv"]//a[starts-with(text(), "S")]')
                            if not next_button:
                                break
                            next_button.click()
                            time.sleep(1)
                            page.wait_for_selector('//div[@class="bbvpress-list__loading"]',state='hidden')
                    
                    # Process and download files                    
                    for file in files_urls:
                        files_dicts.extend(self.download_tmp(path=new_file_path,file=file))
                        time.sleep(2)
                
                if files_dicts:
                    return new_file_path
                else:
                    return "" 

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
    # robot = Executor_D_BO_000000536()
#     x = robot.get_data(main_url="https://www.bbv.com.bo/estados-financieros-por-emisor",path=r"\\10.0.0.9\SPIM\Bbv\Estados Financieros por Emisor\EEFF Trimestrales")
#     print(len(x))
#     print(x)
#     # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': '\\\\10.0.0.9\\spim\\INE\\ESTADISTICAS ECONOMICAS\\SALARIOS Y REMUNERACIONES\\SECTOR PRIVADO\\02_Grupo Ocupacional\\tmp\\2024-05-13_155615download.xlsx'}]
#     # y = robot.compare_files(files_paths=files,updated_to="2023-01-21")
#     # print(y)

Executor_D_BO_000000536 = D_BO_000000536
Robot = D_BO_000000536
