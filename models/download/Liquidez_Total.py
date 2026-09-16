import re
import os
import shutil
import requests
import urllib
import fitz
import pandas as pd
from playwright.sync_api import sync_playwright
from unidecode import unidecode
import sys
sys.path.append("..")
from models.download.tools.download_tools import format_date, month_to_number, get_date,format_date, last_day_month ,delete_hidden_sheets
from models.download.Download_Base import Download_Base

class Liquidez_Total(Download_Base):
    def download_parent_pdf_file(self,urls):
        parent_pdf_files_path = []
        current_path = os.getcwd()
        download_path = os.path.join(current_path, 'tmp')
        if os.path.exists(download_path):
            shutil.rmtree(download_path)
        os.makedirs(download_path)
        for url in urls:
            response = requests.get(url)
            parsed_url = urllib.parse.urlparse(url)
            file_name = os.path.basename(parsed_url.path)
            file_path = os.path.join(download_path, file_name)
            if response.status_code == 200:
                with open(file_path, 'wb') as file:
                    file.write(response.content)
                parent_pdf_files_path.append(file_path)
        
        return parent_pdf_files_path

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
        for k in key_words:
            regex = re.compile(r'\b' + re.escape(k), re.IGNORECASE|re.UNICODE)
            
            is_in_text = regex.search(text)
        
            if not is_in_text:
                if k in special_keywords:
                    for j in special_keywords[k].split(' '):
                        
                        regex = re.compile(r'\b' + re.escape(j), re.IGNORECASE|re.UNICODE)
                        
                        if not regex.search(text):
                            return False
                else:
                    return False
        return True

    def exact_coincidence(self,text,key_word):
        text = re.sub(r'^[\d.]+', '', text).strip()
        text = unidecode(text)
        return text == key_word
    def extract_download_urls(self, file,base_url,key_word):
        download_urls = []
        doc = fitz.open(file)
        lines = []
        for num_page in range(len(doc)):
            page = doc.load_page(num_page)
            text = page.get_text()
            lines = lines + text.split('\n')
        
        for i in range(len(lines)):
            if re.match(r"\b\d{1,2}\b",lines[i]):
                if len(lines[i])==1:
                    lines[i]='0'+lines[i]

                file_title = lines[i+1]
                if self.exact_coincidence(text=file_title,key_word=key_word):
                    download_urls.append(base_url + f"/{lines[i]}.pdf")
                    download_urls.append(base_url + f"/{lines[i]}.xlsx")
                    break

                if self.search_key_words(file_title, key_word=key_word):
                    print(file_title)
                    download_urls.append(base_url + f"/{lines[i]}.pdf")
                    download_urls.append(base_url + f"/{lines[i]}.xlsx")
                    break
        return download_urls


    def get_file_url(self, main_url, updated_to, key_word, format='%Y-%m-%d'):
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
            # XPath to locate elements
            info_elements_xpath = '//div[@class="view-content"]/div'

            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch()
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url)

                info_elements = page.query_selector_all(info_elements_xpath)
                
                parents_pdf_urls = []
                base_urls = [] 
                for element in info_elements:
                    title = element.query_selector(
                            '//span[@class="bcb_title"]').inner_text()
                    title = re.split(r'\s|[\xa0]', title)
                    year = int(title[-1])
                    month = month_to_number(title[-2])

                    if year == updated_to.year and month > updated_to.month:
                        button = element.query_selector('//a')
                        url = button.get_attribute('href')
                        baseurl = '/'.join(url.split('/')[:-1])
                        parents_pdf_urls.append(url)
                        base_urls.append(baseurl)

                if not len(parents_pdf_urls):
                    return parents_pdf_urls
                
                browser.close()
                files_paths = self.download_parent_pdf_file(urls=parents_pdf_urls)
                downloads_urls = []
                for i in range(len(files_paths)):
                    downloads_urls.extend(self.extract_download_urls(file=files_paths[i],base_url=base_urls[i],key_word=key_word))
                
                if not len(downloads_urls):
                    "No se encontro el archivo buscado"    
                return downloads_urls
                
            except Exception as e:
                print(f"An error ocurred: {e}")
            finally:
                # Close page and browser
                if 'page' in locals():
                    page.close()
                if 'browser' in locals():
                    browser.close()

    def compare_files(self,files_paths, updated_to, last_file_path, format='%Y-%m-%d'):
        """
        Compares a list of files with a last file, extracts dates from the new files,
        and filters out the files based on the provided date criteria.

        Parameters:
            files_paths (list): List of temp file paths to compare.
            updated_to (str): The latest date for which the database contains records.
            last_file_path (str): Path of the last file for which the database contains records.

        Returns:
            list: List of dictionaries containing information about files that meet the criteria.
        """
        print("Comparing files...")
        # List to store file dictionaries
        files_dicts = []

        # Convert updated_to string to datetime object
        updated_to = format_date(updated_to)

        # Iterate over each file path
        for file in files_paths:
            file_name = os.path.basename(file)
            print(file_name)
            extension = os.path.splitext(file_name)[1]
            if 'pdf' in extension:
                files_dicts.append({
                    "tmp_path": file
                })
            print(f"Comparing file: {file}")

            delete_hidden_sheets(file=file)
            # Extract date from the file
            df_new_file = pd.read_excel(file)
            
            print("Extracting date from the file...")
            date = get_date(dataframe=df_new_file)
            print(date)
            if not date:
                continue
            month = date[0]
            year = date[1]

            # Check if the file is newer than the provided date
            if (year >= updated_to.year) and (month > updated_to.month):
                # Get the last day of the month for the update date
                print("File meets update criteria. Adding to filtered files.")
                day = last_day_month(year=year, month=month)
                # Format the update date
                update_to_formatted = f"{year}-{str('%02d' % (month,))}-{day}"
                # Append file information to the list
                files_dicts.append({
                    "tmp_path": file,
                    "updated_to": update_to_formatted,
                })
            else:
                print("File does not meet update criteria. Skipping...")            
        
        # Check if any files were found after the updated date
        if not len(files_dicts):
            print(f"There are NO files after {updated_to.strftime(format)}")
            return False
        
        files_dicts_with_pdfs = []
        for file in files_dicts:
            file_name = os.path.basename(file["tmp_path"])
            extension = os.path.splitext(file_name)[1]
            if 'pdf' in extension:
                continue
            files_dicts_with_pdfs

        return files_dicts