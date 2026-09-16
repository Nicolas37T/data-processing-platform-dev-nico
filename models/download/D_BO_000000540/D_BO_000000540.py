import traceback
import re
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number, text_extract
from models.download.Download_Base import Download_Base

class D_BO_000000540(Download_Base):
    def verify_url(self,url, retries=3, wait_time=3, timeout=120, is_download_url=False):
        return True

    def get_file_url(self, main_url, updated_to, format='%Y-%m-%d'):
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
            # Regular expression to match dates
            re_date = r"(\d{1,2})\s((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)).\s(\d{4})"

            # Xpaths
            seccion_button_xpath = '#quicktabs-tab-resultado_de_subastas_bonos_del_-1'
            rows_xpath = '//*[@id="quicktabs-tabpage-resultado_de_subastas_bonos_del_-1"]//div[@class="view-content"]/div'
            next_page_button_xpath = '//*[@id="quicktabs-tabpage-resultado_de_subastas_bonos_del_-1"]//li[@class="pager-next"]/a'

            files_urls = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=False)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url, wait_until='domcontentloaded')

                max_retries = 5
                for attempt in range(1, max_retries+1):
                    try:
                        print(f"Waiting for page load (attempt {attempt}/{max_retries})")
                        page.wait_for_selector(seccion_button_xpath, state="visible",timeout=10*1000)
                        break
                    except Exception:
                        print("Reloading page")
                        if attempt<max_retries:
                            page.reload(wait_until="domcontentloaded")
                        else:
                            raise TimeoutError("Page doesn't work after retries")

                page.locator(seccion_button_xpath).click()
                # Get all URLs of interest from the page
                exists_next_page=True
                while exists_next_page:
                    page.wait_for_selector(rows_xpath)
                    files_rows = page.query_selector_all(rows_xpath)
                    for row in files_rows:
                        title = row.query_selector('//div[@class="bcb_title"]').inner_text().lower()
                        
                        date = re.search(re_date, title)
                        if date:
                            #print(title)
                            year = int(date.group(3))
                            month = date.group(2)
                            month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
                            day = int(date.group(1))

                            date_formated = format_date(f"{year}-{month}-{day}")
                        
                            if date_formated<=updated_to:
                                exists_next_page = False
                                break
                            
                            url = row.query_selector('//a')
                            url = url.get_attribute('href')
                            files_urls.append(url)
                    next_page_button = page.query_selector(next_page_button_xpath)
                    if next_page_button:
                        next_page_button.click()
                        page.wait_for_timeout(1*1000)
                    else:
                        exists_next_page = False                    
                
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

        # Iterate over each file path
        for file in files_paths:
            # Regular expression to match dates
            re_date = r"(\d{2}).(\d{2}).(\d{4})"
            print(f"Comparing file: {file['tmp_path']}")

            # Extract date from the file
            print("Extracting date from the file...")
            lines = text_extract(file["tmp_path"])
            date_line = [re.search(re_date,line) for line in lines if re.search(re_date,line)]
            
            date = date_line[-1]
            year = int(date.group(3))
            month = int(date.group(2))
            day = int(date.group(1))

            date_formated = format_date(f"{year}-{month}-{day}")
            # Check if the file is newer than the provided date
            if date_formated>=updated_to:
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
#     robot = Executor_D_BO_000000540()
    # x = robot.get_file_url(main_url="https://www.bcb.gob.bo/?q=content/resultado-de-subastas-bonos-del-bcb-11",updated_to="2015-12-09")
    # print(x)
    # y = robot.compare_files(files_paths=[{"tmp_path": r"C:\Users\Kevin Padilla\Downloads\BRU-10-2023 Desmat_TR.pdf"}],updated_to="2015-01-21")
    # print(y)

Executor_D_BO_000000540 = D_BO_000000540
Robot = D_BO_000000540
