import traceback
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date
from models.conversion.tools.conversion_tools import search_key_words
from models.download.Download_Base import Download_Base

class BCB_Sector_Monetario(Download_Base):
        
    def get_file_url_main(self, main_url, updated_to, key_words='', format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after update_to date.
        """
        with sync_playwright() as pl:
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)
            # XPath to locate elements
            report_xpath = '//article[@class="bcb-ext-card"]//a[@href]'
            base_url = "https://www.bcb.gob.bo"
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch()
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')
                
                page.wait_for_timeout(3*1000)
                links = page.locator(report_xpath).all()
                print(f"[LINKS] Found {len(links)} report links on this page")

                # Getting all downloadable elements 
                links = [link for link in links if search_key_words(text=link.inner_text(),key_words=key_words)]                
                # Searching for files matching name_file and constructing URLs
                files_link_searched = [base_url + link.get_attribute('href') for link in links ]
                
                if not len(files_link_searched):
                    print("The searched files were not found")

                print("Found files matching the criteria.")
                return files_link_searched      

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