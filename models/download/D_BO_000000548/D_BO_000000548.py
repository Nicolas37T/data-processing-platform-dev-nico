from playwright.sync_api import sync_playwright
from datetime import datetime, date
import re
import PyPDF2
import traceback
from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import search_key_words, format_date

class D_BO_000000548(Download_Base):

    def get_file_url(self, main_url, updated_to,key_words= "safis", format='%Y-%m-%d'):
        
        """
        Verifies and downloads type I files after the specified update date.
        Parameters:
            main_url(str):The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            key_words(str, optional): Keywords to search for he file     
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list: A list of URLs
        """

        extracted_urls_sup=[]
        cont = 0
        
        # Parse the updated_to date into a datetime object
        # date_updated_to = datetime.strptime(updated_to, date_format).date()           
        date_updated_to=format_date(updated_to,format)             
        
        with sync_playwright() as p:  

            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0 Win64 x64)' \
                    ' AppleWebKit/537.36 (KHTML, like Gecko)' \
                    ' Chrome/89.0.4389.82 Safari/537.36'
                )
                page = context.new_page()
                page.goto(main_url, wait_until='domcontentloaded')
                
                # Click the financial reports tab
                page.locator('//li[@id="tab-estadosfinancieros"]/a').click()                                            
                
                element_xpath = "(//table[@class='bbvTable']/tbody)[3]/tr"

                # Getting all downloadable elements 
                elements = page.query_selector_all(element_xpath)

                # Searching for files matching name_file and constructing URLs
                files_link_searched = []
                for row in elements:
                    tds = row.query_selector_all("td")
                    descripcion = tds[0].inner_text().strip()
                    date_str = tds[1].inner_text().strip()
                    last_date = datetime.strptime(date_str,  "%d/%m/%Y").date()
                    try:
                        if search_key_words(text=descripcion, key_word=key_words):
                            a_tag = row.query_selector("a")
                            if a_tag:
                                href = a_tag.get_attribute("href")
                                if href and last_date>date_updated_to.date():                        
                                    extracted_urls_sup.append(href)  
                    except Exception as e:
                        print("Error processing row:", e)
                         

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
                
        if not len(extracted_urls_sup):		
            print(f"There are NO files after {date_updated_to.strftime(format)}")		
            return []

        return extracted_urls_sup
    

    def compare_files(self,files_paths,updated_to,format='%Y-%m-%d'):  
        """
        Extract the date from a list of files to compare and filter which are more recent than the updated_to date.

        Parameters:
            files_paths (list): List of dictionaries containing information about files.
            updated_to (str): The latest date for which the database contains records.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list or bool: A list of dictionaries with information about files that meet the 
            criteria of being more recent than 'updated_to'. Returns False if no more recent files are found.
        """
      
        list_files=[]        
        date_updated_to = datetime.strptime(updated_to, format).date() 


        for files in files_paths:            
            # Open the PDF file for reading
            with open(files.get('tmp_path'), 'rb') as pdf_file: 
                pdf_reader = PyPDF2.PdfReader(pdf_file)                                
                
                # Extract text from the first page
                page = pdf_reader.pages[0]
                text = page.extract_text()

                # Pattern to search for the date
                pattern = r'(\d{1,2}) de (\w+) de (\d{4})'

                # Find the date in the text
                match = re.search(pattern, text)

                if match:
                    # Extract day, month name, and year
                    day = match.group(1)    # day: "31"
                    month_str = match.group(2)  # month: "agosto"
                    year = match.group(3)    # year: "2024"
                    
                    # Map Spanish month names to month numbers
                    months = {
                        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
                        'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
                    }                
                    
                    # Construct a date object from the extracted components
                    date_file = date(int(year), int(months.get(month_str)), int(day))
                    
                    # Compares the file date with the specified date
                    if( date_file > date_updated_to ):                
                        date_formated = date_file.strftime(format)
                        list_files.append(
                            {                        
                                "download_url": files.get('download_url'),                                      
                                "tmp_path":  files.get('tmp_path'),
                                "updated_to": date_formated
                            }                         
                        )                                    
        # If no new files are found, return False                        
        if not len(list_files):		
            # print(f"There are NO files after {updated_to.strftime(format)}")		
            list_files=False
            
        return list_files

Executor_D_BO_000000548 = D_BO_000000548
Robot = D_BO_000000548
