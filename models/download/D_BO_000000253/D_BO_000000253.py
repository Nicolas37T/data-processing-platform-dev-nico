import traceback, os,re, shutil,time
from playwright.sync_api import sync_playwright
import pandas as pd
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number
from models.download.Download_Base import Download_Base

class D_BO_000000253(Download_Base):

    def check_new_data(self, main_url, updated_to,path,key_words, format='%Y-%m-%d'):
        """
        Extracts data from the main_url dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            path (str): The directory path to store temporary files.
            key_words (str): A string used to name the CSV file.
            format (str): The format of the dates. Default is '%Y-%m-%d'.

        Returns:
            list: A list of dictionaries containing information about the extracted data.
        """

        with sync_playwright() as pl:
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)

            # Regular expression to find dates in text
            re_date = r'\b(\d{1,2})(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)(\d{4})\b'

            # XPath to locate elements
            info_text_xpath = '//h3[@class="bursatil__data-title"] | //p[@class="bursatil__data-description"]'
            first_headers_xpath = '//*[@id="ttbolsa-USD"]//ul[@class="bursatil-data-list is-header first-header"]/li'
            second_headers_xpath = '//*[@id="ttbolsa-USD"]//ul[@class="bursatil-data-list is-header second-header"]/li'
            rows_xpath = '//*[@id="ttbolsa-USD"]//p | //*[@id="ttbolsa-USD"]//ul'

            # Erase the previous tmp path and create the a new one 
            path = os.path.join(path, 'tmp')
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path)

            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url, wait_until='domcontentloaded')

                page.locator('//button[@data-tab="ttbolsa-USD"]').click()
                time.sleep(2)
                
                # Extract information text 
                info_text = [item.inner_text() for item in page.query_selector_all(info_text_xpath)]
                info_text = "\n".join(info_text[:2])                

                # Extract the date from the information text
                date = re.findall(re_date,info_text,re.IGNORECASE)[-1]
                month = date[1]
                month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)

                # Format the extracted date
                date_formated = format_date(f"{date[2]}-{month}-{date[0]}")

                # Check if there is new data available
                if date_formated <= updated_to:
                    print(f"There is no data after the date: {updated_to.strftime(format=format)}")
                    return []
                
                # Extract headers
                first_headers_extract = [""] + [header.inner_text() for header in page.query_selector_all(first_headers_xpath)]
                first_headers = []
                for header in first_headers_extract:
                    first_headers.extend([header,header])
                first_headers = first_headers[:-1]

                headers = [header.inner_text() for header in page.query_selector_all(second_headers_xpath)] + [first_headers[-1]]

                # Extract data rows
                rows = page.query_selector_all(rows_xpath)
                final_rows =[]
                for row in rows:
                    li_elements = row.query_selector_all('//li')

                    if li_elements:
                        final_row = [li.inner_text() for li in li_elements]
                        
                    else:
                        final_row = [row.inner_text()]
                    final_rows.append(final_row)

                # Adjust row lengths
                max_length = max(len(sublist) for sublist in final_rows) 
                for row in final_rows:
                    if len(row) == 8:
                        row.insert(1,"")
                    else:
                        blank = [""]*(max_length-len(row))
                        row.extend(blank)
                final_rows = final_rows[2:]

                # Process the info text
                info_text = re.split(r'\n', info_text)
                info_text = [[row] + [""] * 8 for row in info_text]
                info_text.append(first_headers)
                info_text.append(headers)

                # Combine info text and data rows
                final_rows = info_text + final_rows

                # Save data to Excel file
                df = pd.DataFrame(final_rows)
                file_path = os.path.join(path,f"{key_words}.xlsx")
                df.to_excel(file_path,index=False,header=False)
                print("Data was extracted.")

                # Return information about the extracted data
                return [{
                    "tmp_path":file_path,
                    "updated_to":date_formated.strftime(format=format),
                    "download_url":'-',
                }]

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

# if __name__ == "__main__":
#     robot = Executor_D_BO_000000253()
    
#     x = robot.check_new_data(main_url="https://www2.bbv.com.bo/estadisticas/estadisticas-bursatiles/transacciones-en-bolsa/",updated_to="2024-02-4",path = r'D:\DATAX\data-processing-platform\models\download\D_BO_000000253', key_words="bbv")
#     print(x)
#     # y = robot.compare_files(files_paths=[{"tmp_path": r"C:\Users\Kevin Padilla\Downloads\01.03.xlsx"}],updated_to="2023-01-21")
#     # print(y)

Executor_D_BO_000000253 = D_BO_000000253
Robot = D_BO_000000253
