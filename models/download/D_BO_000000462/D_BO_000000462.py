import re, traceback
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import text_extract, format_date
from models.download.Download_Base import Download_Base

class D_BO_000000462(Download_Base):

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
            re_date = r"(\d{1,2}-\d{1,2}-\d{4})"
            # XPath to locate elements
            date_xpath = '//div[@class="tit-precios"]'
            link_xpath = '//div[@class="moduletable _tabla_precios"]//a'

            base_url = "https://www.adascz.com.bo"
            files_urls = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch()
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')

                # Extract date from the page using XPath
                date = page.query_selector(date_xpath).inner_text()
                date = re.search(re_date, date)
                date_formated = format_date(date.group(1),"%d-%m-%Y")

                # Extract file link using XPath
                link = page.query_selector(link_xpath).get_attribute('href')  
                if date_formated>updated_to:
                    files_urls.append(base_url + link)

                # Check if any files were found after the updated date
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
            Compares a list of files with a last file, extracts dates from the new files,
            and filters out the files based on the provided date criteria.

            Parameters:
                files_paths (list): List of dictionaries containing information about files.
                updated_to (str): The latest date for which the database contains records.

            Returns:
                list: List of dictionaries containing information about files that meet the criteria.
        """
        print("Comparing files...")
        # List to store file dictionaries
        files_dicts = []

        re_date = r'(\d{1,2})\D(\d{1,2})\D(\d{2})'
        # Convert updated_to string to datetime object
        updated_to = format_date(updated_to)
        
        # Iterate over each file path
        for file in files_paths:
            try:  
                lines = text_extract(file["tmp_path"])
                dates = [re.search(re_date, line,re.IGNORECASE) for line in lines if re.search(re_date, line,re.IGNORECASE)]
                
                date = dates[0].group(1,2,3)                
                date_formated = format_date(f"20{date[2]}-{date[1]}-{date[0]}")
                
                if date_formated>updated_to:
                    # Format the update date
                    update_to_formatted = date_formated.strftime(format)
                    print(f"File date: {update_to_formatted}. Adding to filtered files.")
                    file["updated_to"] = update_to_formatted
                    files_dicts.append(file)
                    
                else:
                    print("File does not meet update criteria. Skipping...")
                    
            except Exception as e:
                print(f"An error ocurred: {e}")
                traceback.print_exc()
                continue

        # Check if any files were found after the updated date
        if not len(files_dicts):
            print(f"There are NO files after {updated_to.strftime(format)}")
            return False
        return files_dicts
# if __name__ == "__main__":
#     robot = Executor_D_BO_000000462()
    # x =robot.get_file_url(main_url="https://www.bcb.gob.bo/?q=reservas_internacionales_bcb",updated_to="2024-01-03",)
    # print(len(x))
    # print(x)
    # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"C:\Users\Kevin Padilla\Downloads\Boletin-Precios-Avicolas-12nov2024.pdf"}]
    # y = robot.compare_files(files_paths=files,updated_to="2024-01-21")
    # print(y)

Executor_D_BO_000000462 = D_BO_000000462
Robot = D_BO_000000462
