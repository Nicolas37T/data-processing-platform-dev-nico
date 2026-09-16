import re
import traceback
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date
from models.conversion.tools.conversion_tools import search_key_words
from models.download.Download_Base import Download_Base

class CNDC(Download_Base):
        
    def get_file_url_main(self, main_url, updated_to, key_words='', frecuency="diaria", format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after update_to date.
        """
        with sync_playwright() as pl:
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)
            # XPath to locate elements
            frecuency_tabs_xpath = '//button[@role="tab"]'
            card_xpath = '//div[@class="est-doc-card"]'

            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                context.set_default_timeout(5*60*1000)
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')
                page.wait_for_timeout(3*1000)

                frecuency_tab = [item for item in page.locator(frecuency_tabs_xpath).all() if item.inner_text().strip().lower() == frecuency]
                if not frecuency_tab:
                    raise ValueError("Frecuency Tab not found")
                frecuency_tab[0].click()
                page.wait_for_timeout(3*1000)

                page.wait_for_selector(card_xpath,state='visible')
                page.wait_for_timeout(5*1000)
                links = [link for link in page.locator(card_xpath).all() if search_key_words(text=link.inner_text(),key_words=key_words)]                
                print(f"[LINKS] Found {len(links)} report links on this page")

                files_link_searched = []
                for link in links:
                    date = re.search(r'\d{2}\D\d{2}\D\d{4}',link.inner_text())
                    if not date:
                        continue
                    date = format_date(date.group(),format="%d/%m/%Y")
                    if date > updated_to:
                        a = link.locator("a[href]")
                        if a.count() > 0:
                            href = a.first.get_attribute("href")
                            if href:
                                files_link_searched.append(href)
                            continue

                        # 2. Fallback: button con data-url
                        button = link.locator("button[data-url]")

                        if button.count() > 0:
                            url = button.first.get_attribute("data-url")
                            if url:
                                files_link_searched.append(url)
                        
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