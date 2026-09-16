import re, traceback
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number, text_extract, last_day_month
from models.download.Download_Base import Download_Base

class D_BO_000000013(Download_Base):

    def get_file_url(self, main_url, updated_to, format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """

        with sync_playwright() as pl:
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)
            files_urls = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=False)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                context.set_default_timeout(10*60*1000)
                page = context.new_page()
                page.goto(main_url, wait_until='domcontentloaded')

                page.wait_for_selector('#bcb-estados-deuda-frame')
                frame = page.frame_locator('#bcb-estados-deuda-frame')

                card_items = frame.locator('//div[@class="bcb26-card-body"]').all()

                for item in card_items:
                    date = re.search(r'(\d{2}\D\d{2}\D\d{4})',item.inner_text())
                    
                    if not date:
                        continue
                    date = format_date(date.groups()[0],"%d-%m-%Y")
                    if date<=updated_to:
                        continue
                    url = item.locator('xpath=.//a[@href]').first.get_attribute('href')
                    files_urls.append(url)

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
            re_date = r"\b((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\b\D*\b(\d{4})\b"

            print(f"Comparing file: {file['tmp_path']}")

            # Extract date from the file
            print("Extracting date from the file...")
            lines = text_extract(file["tmp_path"])
            date_line = [m for line in lines if (m:=re.search(re_date,line,re.IGNORECASE))]
            date = date_line[0].groups()
            print(date)
            if not date:
                raise NameError("An error occurred while extracting the date")
            
            month = m if (m:=month_to_number(date[0])) else month_abr_to_number(date[0])

            year = int(date[1])
            day = last_day_month(year=year, month=month)
            date = format_date(f'{year}-{month}-{day}')
           
            # Check if the file is newer than the provided date
            if date>updated_to:
                file["updated_to"] = date.strftime(format)
                files_dicts.append(file)
            else:
                print("File does not meet update criteria. Skipping...") 

        # Check if any files were found after the updated date
        if not len(files_dicts):
            print(f"There are NO files after {updated_to.strftime(format)}")
            return False
        return files_dicts
        
# if __name__ == "__main__":
#     robot = Executor_D_BO_000000013()
#     x = robot.get_file_url(main_url="https://deudaexternapublica.bcb.gob.bo/publico/inicio",updated_to="2024-05-31")
#     print(x)
#     # y = robot.compare_files(files_paths=[{"tmp_path": r"C:\Users\Kevin Padilla\Downloads\ESTADO FEBRERO 2024.pdf"}],updated_to="2024-01-21")
#     # print(y)

Executor_D_BO_000000013 = D_BO_000000013
Robot = D_BO_000000013
