import re, time
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number, text_extract, last_day_month
from models.download.Download_Base import Download_Base

class D_BO_000000020(Download_Base):

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
            page_links_xpath = '//div[@data-post-id]//a[@href and contains(text(), "IPC")]'
            next_button_xpath = '//div[@role="navigation"]/a[@class="page-numbers nav-next"]'
            file_link_xpath = '//div[@class="wpb_wrapper"]//a[@class="aio-icon-box-link" and @href]'

            # Regular expression to match dates
            re_date = r"\b((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic\b))\D*(\d{4})"

            file_urls = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url, wait_until="load")
                page.wait_for_selector(page_links_xpath,state="visible")

                page_links = []
                while True:
                    # Extract links from the current page
                    print("Extracting links from the current page...")
                    links = [link for link in page.query_selector_all(page_links_xpath)]
                    if links:
                        # Extract and format the date from the last link
                        last_date_link = re.search(re_date,links[-1].inner_text(),re.IGNORECASE).group(1,2)
                        month = last_date_link[0]
                        month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
                        day = last_day_month(year=int(last_date_link[1]), month=month)
                        date_formated = format_date(f"{last_date_link[1]}-{month}-{day}")
                        
                        # Add extracted links to the list and check if we should stop
                        links = [link.get_attribute('href') for link in links]
                        page_links.extend(links)
                        if date_formated <= updated_to:
                            break

                    # Check if there's a next button to paginate; if not, break the loop
                    next_button = page.query_selector(next_button_xpath)
                    if not next_button:
                        break
                    next_button.click()
                    time.sleep(2)
                
                for link in page_links:
                    # Process each page link to find the file download URL
                    new_page = context.new_page()
                    new_page.goto(link, wait_until='domcontentloaded')

                    # Extract the file download link if it exists
                    file_link = new_page.query_selector(file_link_xpath).get_attribute('href')
                    if file_link:
                        print(f"Found file link: {file_link}")
                        file_urls.append(file_link)
                    new_page.close()

                # If the list of file_urls is empty returns empty array
                if not len(file_urls):
                    print(f"There are NO files after {updated_to.strftime(format)}")
                    return []    

                return file_urls
            except Exception as e:
                print(f"An error ocurred: {e}")
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
        re_date = r"\b((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic\b))\D*(\d{4})"

        # Iterate over each file path
        for file in files_paths:            
            print(f"Comparing file: {file['tmp_path']}")

            # Extract date from the file
            print("Extracting date from the file...")
            lines = text_extract(file["tmp_path"])
            date_line = [re.search(re_date,line, re.IGNORECASE) for line in lines if re.search(re_date,line, re.IGNORECASE)]
            
            date = date_line[-1].group(1,2)            
            month = month_to_number(date[0]) if month_to_number(date[0]) else month_abr_to_number(date[0])
            day = last_day_month(year=int(date[1]), month=month)

            date_formated = format_date(f"{date[1]}-{month}-{day}")
            
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
#     robot = Executor_D_BO_000000020()
    # x = robot.get_file_url(main_url="https://www.ine.gob.bo/index.php/comunicacion/publicaciones/",updated_to="2023-12-31")
    # print(x)
    # y = robot.compare_files(files_paths=[{"tmp_path": r"C:\Users\Kevin Padilla\Downloads\BOLETIN IPC JULIO- 2024.pdf"}],updated_to="2023-9-21")

Executor_D_BO_000000020 = D_BO_000000020
Robot = D_BO_000000020
