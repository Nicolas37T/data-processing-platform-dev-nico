import sys, os, time, traceback, shutil, re
sys.path.append("..")
from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
from models.download.Download_Base import Download_Base
import pandas as pd
from lxml import etree

class D_BO_000000014(Download_Base):

    def get_data(self, main_url, path,updated_to,format='%Y-%m-%d'):
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
            # Start and end dates to filter data
            today = datetime.today()
            start_date = today - timedelta(days=91)
            end_date = today - timedelta(days=1)
            re_date =  r'\d{4}-\d{1,2}-\d{1,2}'

            # Create the temporary directory to save files
            new_file_path = os.path.join(path, 'tmp')
            if os.path.exists(new_file_path):
                shutil.rmtree(new_file_path)
            os.makedirs(new_file_path)
            
            files_dicts = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=False)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                context.set_default_timeout(1800000)
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

                # Navigate to the "Precio Mayorista. Prod. Agropecuarios" section
                page.wait_for_selector("#accOap",state="visible")
                page.query_selector('//*[@id="accOap"]/div[@class="panel"][1]/div[1]').click()
                page.wait_for_selector("#accPrice div.panel",state="visible")
                page.query_selector("#cbx_wa").select_option("105") #105 = "Capital"
                page.wait_for_selector("#all_areas",state="visible")
                
                # Get all group options
                groups = [group.get_attribute("value") for group in page.query_selector_all('//*[@id="cbx_groups"]/option[@value]')]
                for group in groups:
                    page.query_selector("#cbx_groups").select_option(group)
                    time.sleep(2)

                    # Get all product options
                    products = page.query_selector_all('//*[@id="cbx_products"]/option[@value]')
                    for product in products:
                        value = product.get_attribute('value')
                        product_name = product.inner_text().strip()
                        page.query_selector('#cbx_products').select_option(value)
                        time.sleep(2)
                        print(f"Selected product: {product_name}.")
                        
                        # Fill in start and end dates
                        page.locator('#tabs input.textbox-text').first.fill(start_date.strftime("%d/%m/%Y"))
                        page.locator('//*[@id="tabs"]//span[@class="textbox-addon textbox-addon-right"]').first.click()
                        time.sleep(1)
                        page.locator('#cc td.calendar-selected').click()
                        page.locator('#tabs input.textbox-text').last.fill(end_date.strftime("%d/%m/%Y"))
                        page.locator('//*[@id="tabs"]//span[@class="textbox-addon textbox-addon-right"]').last.click()
                        time.sleep(1)
                        page.locator('#cc td.calendar-selected').click()

                        # Select city options
                        city_options = page.query_selector_all('//*[@id="cities"]//input[@name="areas_ids[]"]')
                        for i in range(4):
                            chunk_size = 3
                            page.query_selector("#all_areas").set_checked(True)
                            page.query_selector("#all_areas").set_checked(False)
                            if i==chunk_size:
                                [option.set_checked(True) for option in city_options[-chunk_size:]]
                            else:
                                [option.set_checked(True) for option in city_options[chunk_size*i:chunk_size*(1+i)]]
                            page.query_selector('#btnGenerate').click()
                            time.sleep(1)
                            page.wait_for_selector('//div[@class="messager-body panel-body panel-body-noborder window-body"]',state="detached")
                            print(f"Generated report for chunk {i}.")
                            
                            # Export the report
                            toolbar_frame = page.frame("birtViewer")
                            toolbar_frame.locator('//*[@id="toolbar"]//input[@name="exportReport"]').click()
                            time.sleep(2)

                            toolbar_frame.locator('#exportFormat').select_option("xls")
                            with page.expect_download() as download_info:
                                toolbar_frame.locator('#exportReportDialogokButton').click()
                            download = download_info.value

                            # Verify the date in the downloaded report
                            page_rows = toolbar_frame.query_selector_all('//*[@id="Document"]//tbody/tr[@valign="top"]')
                            if not len(page_rows)>2:
                                print("No date found in the report.")
                                page.query_selector('//*[@id="tabConainer"]//li[@class="tabs-selected"]/a[@class="tabs-close"]').click()
                                continue
                            
                            tree = etree.parse(download.path())
                            root = tree.getroot()
                            namespaces = {'ss': 'urn:schemas-microsoft-com:office:spreadsheet'}

                            rows = root.xpath('.//ss:Table/ss:Row', namespaces=namespaces)
                            data = []
                            for row in rows:
                                cells = row.xpath('ss:Cell/ss:Data', namespaces=namespaces)
                                row_data = [cell.text for cell in cells]
                                data.append(row_data)

                            df_new_file = pd.DataFrame(data)
                            column_to_search = list(df_new_file[df_new_file.columns[0]])
                            print(column_to_search)
                            dates = [re.search(re_date, str(cell)).group() for cell in column_to_search if re.search(re_date, str(cell))]

                            date_formated = dates[-1]
                            # Save the downloaded file
                            download_path = os.path.join(
                            new_file_path, f"{date_formated}_{product_name}0{i}.xls")
                            download.save_as(download_path)
                            files_dicts.append(download_path)

                            # Close the current tab
                            page.query_selector('//*[@id="tabConainer"]//li[@class="tabs-selected"]/a[@class="tabs-close"]').click()
                            time.sleep(2)
                    
                if files_dicts:
                    return new_file_path
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
    
if __name__ == "__main__":
    robot = Executor_D_BO_000000014()
    x = robot.get_data(main_url="http://bancodedatos.observatorioagro.gob.bo/birt/report/",path=r"\\10.0.0.9\spim\Ministerio de Desarrollo Rural y Tierras\Estadisticas Agropecuarisa VDR\SISPAM\Precios mercados mayoristas")
#     print(len(x))
#     print(x)
#     # robot.store_new_data(tmp_path=r"\\10.0.0.9\spim\Ministerio de Desarrollo Rural y Tierras\Estadisticas Agropecuarisa VDR\SISPAM\Precios mercados mayoristas\2024\2024-06\2024-06-10_Limón Sutil (Mediano)03.xls", last_file_path="")
#     # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': '\\\\10.0.0.9\\spim\\INE\\ESTADISTICAS ECONOMICAS\\SALARIOS Y REMUNERACIONES\\SECTOR PRIVADO\\02_Grupo Ocupacional\\tmp\\2024-05-13_155615download.xlsx'}]
#     # y = robot.compare_files(files_paths=files,updated_to="2023-01-21")
#     # print(y)

Executor_D_BO_000000014 = D_BO_000000014
Robot = D_BO_000000014
