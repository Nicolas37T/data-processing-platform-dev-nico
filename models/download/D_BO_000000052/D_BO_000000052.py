import traceback, re, os, zipfile
from playwright.sync_api import sync_playwright
import pandas as pd
from urllib.parse import urljoin
from models.download.tools.download_tools import format_date, month_abr_to_number, last_day_month, month_to_number
from models.download.Download_Base import Download_Base

class D_BO_000000052(Download_Base):

    def get_file_url(self, main_url, updated_to, format='%Y-%m-%d', key_words='almacenera'):
        """
        Extracts download URLs for files dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """

        with sync_playwright() as pl:
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)
            # XPath to locate elements
            main_link_xpath = '//div[contains(@id,"collapse")]//div/a[@href]'
            urls_xpath = '//td//a[@href]'
            # Regular expression to match dates
            re_year = r"(\d{4})"
            # re_month = r"((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))" 
            re_date = r"(\d{4})(\d{1,2})"
            
            base_url = "https://www.asfi.gob.bo"
            files_urls = [] 
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=False)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')
                page.wait_for_selector(main_link_xpath)

                main_links = [item for item in page.locator(main_link_xpath).all() if re.search(key_words,item.inner_text(),re.IGNORECASE)]
                for link in main_links:
                    year = int(re.search(re_year, link.inner_text()).group())
                    if year<updated_to.year:
                        continue
                    link_url = urljoin(base_url,link.get_attribute('href'))
                    new_page = context.new_page()
                    new_page.goto(link_url,wait_until='domcontentloaded')
                    new_page.wait_for_selector(urls_xpath)

                    urls = [item.get_attribute('href') for item in new_page.locator(urls_xpath).all()]
                    for url in urls:
                        date_match = re.search(re_date,url,re.IGNORECASE).groups()
                        try:
                            date_formated = pd.to_datetime(f"{date_match[0]}-{date_match[1]}-01",format=format) + pd.offsets.MonthEnd(0)
                        except:
                            continue
                        if date_formated>updated_to:
                            url = urljoin(base_url,url)
                            files_urls.append(url)

                    new_page.close()
                          
                if not len(files_urls):
                    print(f"There are NO files after {updated_to.strftime(format)}")
                    return []
                
                print(f"There are {len(files_urls)} files after {updated_to.strftime(format)}")
                return files_urls               
                
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
        re_date = r"(\d{1,2})\s*\w*\s*((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\s*\w*\s*(\d{4})"

        # Iterate over each file path
        for file in files_paths:
            print(f"Comparing file: {file['tmp_path']}")
            file_name = os.path.basename(file['tmp_path'])
            extension = os.path.splitext(file_name)[1]

            try:
                if "zip" in extension:
                    folder_path = os.path.dirname(file['tmp_path'])
                    extract_dir = os.path.join(folder_path, os.path.splitext(file_name)[0])

                    excel_extensions = {'.xls', '.xlsx'}
                    with zipfile.ZipFile(file['tmp_path'], 'r') as zip_ref:
                        for member in zip_ref.infolist():
                            member_path = member.filename.replace('\\', '/')
                            member.filename = member_path
                            if os.path.splitext(member_path)[1].lower() in excel_extensions or member.is_dir():
                                zip_ref.extract(member, extract_dir)

                    excel_extensions_found = []
                    for root, _, files in os.walk(extract_dir):
                        for f in files:
                            if os.path.splitext(f)[1].lower() in excel_extensions:
                                excel_extensions_found.append(os.path.join(root, f))

                    if not excel_extensions_found:
                        raise FileNotFoundError(f"No se encontró ningún archivo Excel en el ZIP: {file['tmp_path']}")

                    file['zip_path'] = file['tmp_path']
                    file['tmp_path'] = excel_extensions_found[0]
            except Exception as e:
                print(f"An error ocurred: {e}")
                traceback.print_exc()
                continue

            # Extract date from the file
            print("Extracting date from the file...")
            #delete_hidden_sheets(file=file["tmp_path"])

            df_new_file = pd.read_excel(file["tmp_path"],sheet_name='248')
            df_new_file = df_new_file.dropna(axis=1,how='all').dropna(how='all')
            
            sub_set = df_new_file.iloc[:5]
            
            dates = []
            for row in range(len(sub_set)):
                date = [re.search(re_date, str(year), re.IGNORECASE) for year in sub_set.iloc[row] if re.search(re_date, str(year),re.IGNORECASE)]
                dates.extend(date)
            date = dates[0]

            if not date:
                    raise NameError("An error occurred while extracting the date")
            
            year = date.group(3)
            month = date.group(2)
            month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
            day = date.group(1)

            date_formated = format_date(f"{year}-{month}-{day}")
                
            # Check if the file is newer than the provided date
            if date_formated>updated_to:
                print(f"File date: {date_formated.strftime(format)}. Adding to filtered files.")
                file["updated_to"] = date_formated.strftime(format)
                files_dicts.append(file)
            
            else:
                print("File does not meet update criteria. Skipping...") 

        # Check if any files were found after the updated date
        if not len(files_dicts):
            print(f"There are NO files after {updated_to.strftime(format)}")
            return False
        return files_dicts


# if __name__ == "__main__":
#     robot = Executor_D_BO_000000052()
#     x = robot.get_file_url(main_url="https://www.asfi.gob.bo/index.php/esfc-estados-financieros/28-estados-financieros-emp/373-estados-financieros-emp-2023.html",updated_to="2024-09-30")
#     print(x)
#     y = robot.compare_files(files_paths=[{"tmp_path": r"C:\Users\Kevin Padilla\Downloads\202312_ALM_EstadosFinancieros.xls"}],updated_to="2023-01-21")
#     print(y)

Executor_D_BO_000000052 = D_BO_000000052
Robot = D_BO_000000052
