import sys, re, traceback, time, os, shutil
sys.path.append("..")
from playwright.sync_api import sync_playwright
from datetime import datetime
import pandas as pd
from models.download.tools.download_tools import format_date
from models.download.Download_Base import Download_Base

class D_BO_000000433(Download_Base):

    def verify_download(self, main_url, updated_to, path, key_words = "4.08.01.02",format='%Y-%m-%d'):
        """
        Verifies and downloads files dated after the specified update date, and saves them to a temporary path.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            path (str): The directory path where the downloaded files will be saved.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """

        with sync_playwright() as pl:
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)
            re_year = r"(\d{4})"
        
            # Erase the previous tmp path and create the a new one
            path = os.path.join(path, 'tmp')
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path)

            file_paths = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')
                
                # Filter years greater than the updated_to year
                print("Extracting available years from the page...")
                years_availble = [re.search(re_year,year.inner_text()).group(1) for year in page.query_selector_all('//tr//a[@href]') if re.search(re_year,year.inner_text())]
                years_filtred = [year for year in years_availble if int(year)>updated_to.year]
                print(f"Filtered years after {updated_to.year}: {years_filtred}")

                # Check if there are no files after the updated_to date
                if not len(years_filtred):
                    print(f"There are NO files after {updated_to.strftime(format)}")
                    return False
                
                # Iterate over the filtered years
                for year in years_filtred:
                    # Open a new page for each year
                    new_page = context.new_page()
                    new_page.goto(f"https://anuario.ine.gob.bo/{year}/paginas/buscador_cont.html")

                    # Access the main frame within the new page
                    main_frame = new_page.frame(url=f"https://anuario.ine.gob.bo/{year}/paginas/buscador.html")
                    main_frame.query_selector('//*[@id="select2-mibuscador-container"]/..').click()
                    
                    # Find links that match the key_words
                    links = [link for link in main_frame.query_selector_all('//*[@id="select2-mibuscador-results"]/li[@role="treeitem"]') if key_words in link.inner_text()]
                    
                    # Handle the download process
                    if links:
                        with new_page.expect_download() as download_info:
                            links[0].click()
                        download = download_info.value
                        today = datetime.today()
                        download_path = os.path.join(
                            path, f"{today.strftime('%Y-%m-%d_%H%M%S')}_{download.suggested_filename}")
                        download.save_as(download_path)
                        file_paths.append({
                            "tmp_path": download_path})
                        time.sleep(1)
                
                # If the list of verified_urls is empty returns NONE
                if not len(file_paths):
                    print(f"There are NO files after {updated_to.strftime(format)}")
                    return False
                
                return file_paths

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
    
    def compare_files(self, files_paths, updated_to, format='%Y-%m-%d'):
        """
        Extract the date from a list of files to compare and filter which are more recent than the updated_to date.

        Parameters:
            files_paths (list): List of dictionaries containing information about files.
            updated_to (str): The latest date for which the database contains records.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list or bool: A list of dictionaries with information about files that meet the criteria of being more recent than 'updated_to'. Returns False if no more recent files are found.
        """
        print("Comparing files...")
        # List to store file dictionaries
        files_dicts = []

        # Convert updated_to string to datetime object
        updated_to = format_date(updated_to)
        
        # Iterate over each file path
        for file in files_paths: 

            re_year = r'(\d{4})\s*[(]?p?[)]?'
            print(f"Comparing file: {file['tmp_path']}")

            # Extract date from the file
            df_new_file = pd.read_excel(file["tmp_path"])
            for column in df_new_file.columns:
                if df_new_file[column].isna().all():
                    df_new_file.drop(columns=[column], inplace=True)
            
            sub_set =  df_new_file[df_new_file.iloc[:, 0]=="TIPO DE SERVICIO"].values.tolist()
            
            years = [re.search(re_year, str(line)) for line in sub_set[0] if re.search(re_year, str(line))]
            
            year = int(years[-1].group(1))           
            
            date_formated = format_date(f"{year}-12-31")
            # Check if the file is newer than the provided date
            if date_formated>updated_to:
                # Format the update date
                update_to_formatted = date_formated.strftime(format)
                print(f"File date: {update_to_formatted}. Adding to filtered files.")
                file["updated_to"] = update_to_formatted
                files_dicts.append(file)
                
            
            else:
                print("File does not meet update criteria. Skipping...") 

        # Check if any files were found after the updated date
        if not len(files_dicts):
            print(f"There are NO files after {updated_to.strftime(format)}")
            return False
        return files_dicts
    
# if __name__ == "__main__":
#     robot = D_BO_000000433()
#     # x = robot.verify_download(main_url="https://anuario.ine.gob.bo/",updated_to="2019-10-21",path=r"\\10.0.0.9\spim\INE\Estadisticas Economicas\ESTADÍSTICAS POR ACTIVIDAD ECONÓMICA\Hidrocarburos\PRODUCCIÓN NACIONAL LÍQUIDOS Y PETRÓLEO CONDENSADO, SEGÚN DEPARTAMENTO Y CAMPO")
#     # print(len(x))
#     # print(x)
#     files = [{'download_url': 'https://nube.ine.gob.bo/index.php/s/PnEqp7IopHEJDBu/download', 'tmp_path': r'\\10.0.0.9\spim\INE\Estadísticas por Actividad Económica\Transporte\Aereo\Nacional e Internacional, Según Tipo de Servicio\tmp\2024-06-11_152731_4080102.xlsx'}]
#     y = robot.compare_files(files_paths=files,updated_to="2019-01-21")
#     print(y)

Executor_D_BO_000000433 = D_BO_000000433
Robot = D_BO_000000433
