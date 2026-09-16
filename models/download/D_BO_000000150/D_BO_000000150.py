import sys, re, os, time, traceback,shutil
sys.path.append("..")
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date
from models.download.Download_Base import Download_Base

class D_BO_000000150(Download_Base):   

    def get_data(self, main_url, path, updated_to,NUMBER_SPLIT=3,format='%Y-%m-%d'):
        """
        Extracts data from URLs for files dated in the present year.

        Parameters:
            main_url (str): The URL of the main page.
            path (str): The path where files are stored.
            updated_to (str): The latest date for which the database contains records.
            format (str): The date format to use for the 'updated_to' field.

        Returns:
            str: A temporary path where the files were stored or an empty string if there are no files downloaded.
        """

        with sync_playwright() as pl:
            # Regular expression to find dates
            re_year = r'^\d{4}$'

            # # Get the last year downloaded from the directory
            # last_year_downloaded = max([d for d in os.listdir(path) if re.search(re_year,d)])
            # print(f"Last year downloaded: {last_year_downloaded}")

            files_dicts = []

            tmp_path = os.path.join(path, 'tmp')
            if os.path.exists(tmp_path):
                shutil.rmtree(tmp_path)
            os.makedirs(tmp_path)
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=False)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='load')

                # Wait until the login selector is visible
                page.wait_for_selector("#ffLogin",state="visible")
                
                # Enter email and password
                email_input = page.query_selector('//*[@id="ffLogin"]//input[@placeholder="Email"]')
                password_input = page.query_selector('//*[@id="ffLogin"]//input[@placeholder="Clave"]')
                submit_button = page.query_selector('//*[@id="ffLogin"]//a[@onclick="submitForm()"]')
                print(password_input.inner_html())
                email_input.fill("karina.centellas@datax.com.bo")
                password_input.fill("3119079")
                submit_button.click()
                print("Submitted login form.")

                # Navigate to the "Series: AgrÃ­cola - Pecuaria" section
                page.wait_for_selector("#accOap",state="visible")
                page.query_selector('//*[@id="accOap"]/div[@class="panel"][2]/div[1]').click()
                page.wait_for_selector("#div_sa_dept",state="visible")

                # Select all cities options
                [checkbox.set_checked(True) for checkbox in page.query_selector_all('//*[@id="div_sa_dept"]//input[@type="checkbox"]')]
                
                # Get all group options
                groups = [group for group in page.query_selector_all('//*[@id="cbx_sa_gcultvs"]/option[@value]')]
                for group in groups:
                    group_title = group.inner_text()
                    group_value = group.get_attribute('value')
                    page.query_selector("#cbx_sa_gcultvs").select_option(group_value)
                    time.sleep(2)

                    # Select all crops options
                    [checkbox.set_checked(True) for checkbox in page.query_selector_all('//*[@id="cultivos"]//input[@type="checkbox"]')]
                    print(f"Selected all crops for group {group_title}.")

                    # Check if there are new data after the last downloaded year
                    year_options = page.query_selector_all('//*[@id="tbSP"]//input[@name="agricls_ids[]"]')
                    date = re.search(r"-(\d{4})", year_options[-1].query_selector('//..').inner_text()).group(1)
                    date = format_date(f"{date}-12-31")
                    
                    # if date.year<=int(last_year_downloaded):
                    #     print(f"There are NO data after {last_year_downloaded}")
                    #     return []
                    
                    # Select the last 3 years
                    [select.set_checked(True) for select in year_options[-3:]]

                    # Generate and download the report
                    page.query_selector("#btnSeries").click()
                    time.sleep(2)
                    page.wait_for_selector('//div[@class="messager-body panel-body panel-body-noborder window-body"]',state="detached")

                    toolbar_frame = page.frame("birtViewer").frame_element().content_frame()
                    toolbar_frame.locator('//*[@id="toolbar"]//input[@name="exportReport"]').click()
                    time.sleep(2)
                    
                    toolbar_frame.locator('#exportFormat').select_option("xls")
                    with page.expect_download() as download_info:
                        toolbar_frame.locator('#exportReportDialogokButton').click()
                    download = download_info.value
                    download_path = os.path.join(
                        tmp_path, f"{date.strftime(format)}_{group_title}.xls")
                    download.save_as(download_path)
                    files_dicts.append(download_path)
                    
                    page.query_selector('//*[@id="tabConainer"]//li[@class="tabs-selected"]/a[@class="tabs-close"]').click()
                    time.sleep(2)

                if files_dicts:
                    return tmp_path
                else:
                    return ""                

            except Exception as e:
                print(f"An error ocurred: {e}")
                traceback.print_exc()
                return ""
            finally:
                # Close page and browser
                if 'page' in locals():
                    page.close()
                if 'browser' in locals():
                    browser.close()
    
# if __name__ == "__main__":
#     robot = D_BO_000000150()
#     x = robot.get_data(main_url="http://bancodedatos.observatorioagro.gob.bo/birt/report/",path=r"\\10.0.0.9\spim\Ministerio de Desarrollo Rural y Tierras\Estadisticas Agropecuarisa VDR\Estadísticas Agropecuarias\Encuestas Subjetivas")
#     print(len(x))
#     print(x)
#     # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': '\\\\10.0.0.9\\spim\\INE\\ESTADISTICAS ECONOMICAS\\SALARIOS Y REMUNERACIONES\\SECTOR PRIVADO\\02_Grupo Ocupacional\\tmp\\2024-05-13_155615download.xlsx'}]
#     # y = robot.compare_files(files_paths=files,updated_to="2023-01-21")
#     # print(y)

Executor_D_BO_000000150 = D_BO_000000150
Robot = D_BO_000000150
