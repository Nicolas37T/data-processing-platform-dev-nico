import sys, re, traceback
sys.path.append("..")
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date, month_to_number, text_extract, month_abr_to_number, last_day_month
from models.download.Download_Base import Download_Base

class D_BO_000000012(Download_Base):

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
            # XPath to locate elements
            year_link_xpath = '//div[@class="book-navigation"]//li/a'
            month_link_xpath = '//div[@class="field-items"]//a'

            base_url = "https://www.aduana.gob.bo"
            files_urls = []

            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch()
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url)
                # Get all links corresponding to years
                year_links = page.query_selector_all(year_link_xpath)
                year_links = [link for link in year_links if "Gestión" in link.inner_text()]

                # Find and click the link corresponding to the year of the updated date
                for link in year_links:
                    year = re.split(r'\s|[\xa0]',link.inner_text())[-1]
                    
                    if int(year) == updated_to.year:
                        new_page = context.new_page()
                        new_page.goto(main_url)
                        new_page.click(f'a[href="{link.get_attribute("href")}"]')
                        # Wait for the page to fully load after clicking the year link
                        print(f"Navigating to page: {new_page.url} ...")
                        new_page.wait_for_url(new_page.url)
                        # Get all links corresponding to months and select those that are after the updated date
                        month_links = new_page.query_selector_all(month_link_xpath)
                        
                        for month_link in month_links:
                            month = re.split(r'\s|[\xa0]', month_link.inner_text())[-2]
                            
                            if month_to_number(month=month)>updated_to.month:
                                files_urls.append(base_url + month_link.get_attribute('href'))
                    elif int(year)>updated_to.year:
                        new_page = context.new_page()
                        new_page.goto(main_url)
                        new_page.click(f'a[href="{link.get_attribute("href")}"]')
                        
                        print(f"Navigating to page: {page.url} ...")
                        page.wait_for_url(page.url)
                        month_links = new_page.query_selector_all(month_link_xpath)
                        for month_link in month_links:
                            files_urls.append(base_url + month_link.get_attribute('href'))

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
            re_date = r"\b(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic\b)\s*(?:de)?\s*\d{4}"

            print(f"Comparing file: {file['tmp_path']}")

            # Extract date from the file
            print("Extracting date from the file...")
            lines = text_extract(file['tmp_path'])
            date_line = [line for line in lines if re.search(re_date,line)]
            date_line = date_line[0].strip().lower()
            
            date = re.search(re_date,date_line).group()
            if not date:
                raise NameError("An error occurred while extracting the date")
            date = re.split(r'\s|[\xa0]', date)
            
            if 'de' in date:
                date.remove('de')
            
            month = month_to_number(date[0]) if month_to_number(date[0]) else month_abr_to_number(date[0])

            year = int(date[1]) 
            
            # Check if the file is newer than the provided date
            if ((year == updated_to.year) and (month > updated_to.month)) or (year > updated_to.year) :
                # Get the last day of the month for the update date
                
                day = last_day_month(year=year, month=month)
                # Format the update date
                update_to_formatted = f"{year}-{str('%02d' % (month,))}-{day}"
                print(f"File date: {update_to_formatted}. Adding to filtered files.")
                # Append the date of the file to the dict
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
#     robot = D_BO_000000012()
#     # x = robot.get_file_url(main_url="https://www.aduana.gob.bo/aduana7/content/bolet%C3%ADn-de-recaudaciones-0",updated_to="2023-10-21")
#     # print(x)
#     y = robot.compare_files(files_paths=[{"tmp_path": r"C:\Users\Kevin Padilla\Downloads\Boletin recaudaciones para el TGN 242 v2.pdf"}],updated_to="2023-01-21")
#     print(y)

Executor_D_BO_000000012 = D_BO_000000012
Robot = D_BO_000000012
