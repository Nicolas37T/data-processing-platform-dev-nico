import re
import traceback
from playwright.sync_api import sync_playwright
from unidecode import unidecode
import sys
sys.path.append("..")
from models.download.tools.download_tools import format_date, month_to_number,last_day_month, month_abr_to_number
from models.download.Download_Base import Download_Base

class BCB_Boletin_Mensual(Download_Base):

    # def download_parent_pdf_file(self,urls):
    #     parent_pdf_files_path = []
    #     current_path = os.getcwd()
    #     download_path = os.path.join(current_path, 'tmp')

    #     # Remove existing tmp directory if it exists
    #     if os.path.exists(download_path):
    #         shutil.rmtree(download_path)

    #     # Create tmp directory
    #     os.makedirs(download_path)

    #     # Iterate through URLs and download PDF files
    #     for url in urls:
    #         response = requests.get(url)
    #         parsed_url = urllib.parse.urlparse(url)
    #         file_name = os.path.basename(parsed_url.path)
    #         file_path = os.path.join(download_path, file_name)

    #         # Check if response is successful (status code 200) and save the file
    #         if response.status_code == 200:
    #             with open(file_path, 'wb') as file:
    #                 file.write(response.content)
    #             parent_pdf_files_path.append(file_path)
        
    #     return parent_pdf_files_path

    def search_key_words(self,text,key_word):
        text = unidecode(text)
        special_keywords = {
            "bcb": "banco central bolivia",
            "tc": "tipo cambio",
            "ipc": "indice precios consumidor",
            "mn": "moneda nacional",
            "me": "moneda extranjera",
            "pib": "producto interno bruto"
        }
        
        key_words = key_word.split(' ')

        # Iterate through keywords and search in text
        for k in key_words:
            regex = re.compile(r'\b' + re.escape(k), re.IGNORECASE|re.UNICODE)
            
            is_in_text = regex.search(text)

            # If keyword not found, check special keywords
            if not is_in_text:
                if k in special_keywords:
                    for j in special_keywords[k].split(' '):
                        
                        regex = re.compile(r'\b' + re.escape(j), re.IGNORECASE|re.UNICODE)
                        
                        if not regex.search(text):
                            return False
                else:
                    return False
        return True

    # Function to check for exact coincidence in text
    def exact_coincidence(self,text,key_word):
        text = re.sub(r'^[\d.]+', '', text).strip()
        text = unidecode(text)
        return text == key_word

    # def extract_download_urls(self, file,base_url,key_word, exact=False):
    #     download_urls = []
    #     doc = fitz.open(file)
        
    #     for num_page in range(len(doc)):
    #         page = doc.load_page(num_page)
    #         links = page.links()
            
    #         # Iterate through links on page
    #         for link in links:
    #             link['from'][0] = 0.0
    #             link_download_url = link['file']
                
    #             link_rect = fitz.Rect(link['from'])
    #             link_text = page.get_text("text", clip=link_rect).lower()
                

    #             # Check for exact coincidence or search keywords in link text
    #             if exact:
    #                 if self.exact_coincidence(text=link_text,key_word=key_word):
    #                     download_urls.append(link_download_url)
    #             else:
    #                 if self.exact_coincidence(text=link_text,key_word=key_word) or self.search_key_words(link_text, key_word=key_word):
    #                     download_urls.append(link_download_url)
                        
    #     download_urls = set(download_urls)
    #     download_urls = list(download_urls)
    #     download_urls = [base_url + f"/{url}" for url in download_urls]
    #     return download_urls
        
    def get_file_url_main(self, main_url, updated_to, key_words='', exact=False, format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after update_to date.
        """

        with sync_playwright() as pl:
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)
            print(f"[INIT] Parsed 'updated_to' date: {updated_to.strftime(format)}")

            # XPaths
            title_xpath = '//div[@class="view-content"]//span[@class="bcb_title"]'
            report_xpath = '//section[@class="bcb-card"]//li/a[@href]'
            summary_xpath = '//section[@class="bcb-card"]//summary[@class="bcb-sum"]'
            next_button_xpath = '//li[@class="pager-next"]//a'

            re_date = r"(\b(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\b)\s*(\b\d{4}\b)"
            base_url = "https://www.bcb.gob.bo"

            try:
                print(f"[BROWSER] Launching Chromium browser")
                browser = pl.chromium.launch(headless=True)

                print("[BROWSER] Creating browser context")
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36'
                )

                page = context.new_page()
                print(f"[NAVIGATION] Navigating to URL: {main_url}")
                page.goto(main_url, wait_until='domcontentloaded')

                download_urls = []
                page_index = 1

                while True:
                    print(f"[PAGE] Processing page #{page_index}")
                    page.wait_for_selector(title_xpath, state='visible')

                    title = page.locator(title_xpath).first.inner_text().lower()
                    print(f"[PAGE] Extracted title text: {title}")

                    date_match = re.search(re_date, title)
                    if not date_match:
                        print("[WARNING] No date found in title. Skipping page.")
                        break

                    year = int(date_match.group(2))
                    month_raw = date_match.group(1)
                    month = m if (m := month_to_number(month_raw)) else month_abr_to_number(month_raw)
                    day = last_day_month(year=year, month=month)

                    date_formated = format_date(f"{year}-{month}-{day}")
                    print(f"[DATE] Page date resolved as: {date_formated.strftime(format)}")

                    if date_formated <= updated_to:
                        print("[STOP] Page date is older or equal to 'updated_to'. Stopping pagination.")
                        break

                    links = page.locator(report_xpath).all()
                    summaries = page.locator(summary_xpath).all()
                    if summaries:
                        for summary in summaries:
                            summary.click()
                            page.wait_for_timeout(2*1000)
                    print(f"[LINKS] Found {len(links)} report links on this page")

                    for idx, link in enumerate(links, start=1):
                        link_text = link.inner_text()
                        link_download_url = base_url + link.get_attribute('href')

                        print(f"[LINK {idx}] Evaluating link text: {link_text}")

                        if exact:
                            if self.exact_coincidence(text=link_text, key_word=key_words):
                                download_urls.append(link_download_url)
                                print(f"[MATCH] Exact match found. URL added: {link_download_url}")
                        else:
                            if (
                                self.exact_coincidence(text=link_text, key_word=key_words)
                                or self.search_key_words(link_text, key_word=key_words)
                            ):
                                download_urls.append(link_download_url)
                                print(f"[MATCH] Keyword match found. URL added: {link_download_url}")

                    print("[PAGINATION] Moving to next page")
                    page.locator(next_button_xpath).click()
                    page.wait_for_timeout(3*1000)
                    page_index += 1

                if not download_urls:
                    print(f"[RESULT] No files found after {updated_to.strftime(format)}")
                    return []

                print(f"[RESULT] Total download URLs collected: {len(download_urls)}")
                return download_urls

            except Exception as e:
                print(f"[ERROR] An exception occurred: {e}")
                traceback.print_exc()
                return []

            finally:
                print("[CLEANUP] Closing browser resources")
                if 'page' in locals():
                    page.close()
                if 'browser' in locals():
                    browser.close()