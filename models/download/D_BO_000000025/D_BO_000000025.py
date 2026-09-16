import re, traceback
from urllib.parse import urlparse, urljoin
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date, text_extract, month_abr_to_number, month_to_number
from models.download.Download_Base import Download_Base

class D_BO_000000025(Download_Base):

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
            # Extract base url
            parsed = urlparse(main_url)
            base_url = f'{parsed.scheme}://{parsed.netloc}'
            # XPath to locate elements
            buttons_xpath = '//li[@class="nav-item"]/button'
            rows_xpath = '//*[@id="table_precios"]//tbody/tr'
            re_date = r'(\d{1,2})\D+\b((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\b\D+(\d{4})'

            files_urls = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url, wait_until="load")

                # Find and click report link
                page.wait_for_selector(buttons_xpath, state="attached")                
                
                # Click on button corresponding to the present year
                year_buttons = page.locator(buttons_xpath).all()
                year_buttons = [button for button in year_buttons if int(button.inner_text())>=updated_to.year]
                
                for button in year_buttons:
                    button.click()
                    page.wait_for_timeout(5*1000)
                    print(f"Clicked on: {button.inner_text()} button")

                    # Extract rows from table and filter based on date
                    rows_table = page.locator(rows_xpath).all()
                    rows_searched = []
                    for row in rows_table:
                        title = row.inner_text()                        
                        date = re.search(re_date, title).groups()
                        month = m if (m:=month_abr_to_number(date[1])) else month_to_number(date[1])
                        date = format_date(f'{date[2]}-{month}-{date[0]}')

                        if date>updated_to:
                            rows_searched.append(row)
                    
                    if not len(rows_searched):
                        continue
                    # Extract links from filtered rows and initiate downloads to find its urls
                    searched_urls = [urljoin(base_url, link.locator('//img[@data-url]').get_attribute('data-url')) for link in rows_searched]
                    files_urls.extend(searched_urls)

                files_urls = list(set(files_urls))
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
            re_year = r"(\d{4}).\d{2}.(\d{2})"
            re_date = r'(\d{1,2})\D*((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre))'
            print(f"Comparing file: {file['tmp_path']}")

            # Extract date from the file
            print("Extracting date from the file...")
            lines = text_extract(file["tmp_path"])
            year = [y.group(1) for line in lines if (y:=re.search(re_year,line))][0]

            date = [d.group(1,2) for line in lines if (d:=re.search(re_date,line,re.IGNORECASE))][:2]            

            if not date:
                raise NameError("An error occurred while extracting the date")

            date = [(d[0],d[1],m if (m:=month_to_number(d[1])) else month_abr_to_number(d[1])) for d in date]
            date = sorted([format_date(f"{year}-{d[2]}-{d[0]}") for d in date])[-1]
            
            # Check if the file is newer than the provided date
            if date>updated_to:
                print(f"File date: {date.strftime(format)}. Adding to filtered files.")
                file["updated_to"] = date.strftime(format)
                files_dicts.append(file)
            
            else:
                print("File does not meet update criteria. Skipping...") 

        # Check if any files were found after the updated date
        if not len(files_dicts):
            print(f"There are NO files after {updated_to.strftime(format)}")
            return False
        return files_dicts

Executor_D_BO_000000025 = D_BO_000000025
Robot = D_BO_000000025
