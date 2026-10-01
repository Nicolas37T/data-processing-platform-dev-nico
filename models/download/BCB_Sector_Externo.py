import re
import urllib.parse
import traceback
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date, search_key_words
from models.download.Download_Base import Download_Base

class BCB_Sector_Externo(Download_Base):
        
    def get_file_url_main(self, main_url, updated_to, key_words='', format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after update_to date.
        """
        with sync_playwright() as pl:
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)
            # XPath to locate elements (compatible with both new and legacy BCB pages)
            report_xpath = '//a[contains(@href, ".xlsx") or contains(@href, ".xls")]'
            summary_xpath = '//details[@class="bcb-ext-acc"]'
            base_url = "https://www.bcb.gob.bo"
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch()
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')
                
                summaries = page.locator(summary_xpath).all()
                if summaries:
                    for summary in summaries:
                        summary.click()
                        page.wait_for_timeout(2*1000)
                
                links = page.locator(report_xpath).all()
                print(f"[LINKS] Found {len(links)} report links on this page")

                # Getting all downloadable elements matching key_words in text or href
                matched_urls = []
                for link in page.query_selector_all(report_xpath):
                    text = link.inner_text().strip()
                    href = link.get_attribute('href') or ''
                    decoded_href = urllib.parse.unquote(href)
                    clean_href = re.sub(r'[_/.-]', ' ', decoded_href)
                    combined_text = f"{text} {clean_href}".replace("BCB", "Banco Central de Bolivia")
                    if search_key_words(text=combined_text, key_word=key_words) or search_key_words(text=text, key_word=key_words) or search_key_words(text=href, key_word=key_words):
                        full_url = href if href.startswith('http') else base_url + href
                        matched_urls.append(full_url)

                files_link_searched = list(dict.fromkeys(matched_urls))
                
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