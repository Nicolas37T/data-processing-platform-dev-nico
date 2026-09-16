import sys, traceback, re, time, os, shutil
sys.path.append("..")
from playwright.sync_api import sync_playwright
from datetime import datetime
import pandas as pd
from models.download.tools.download_tools import last_day_month, get_departamento_abr
from models.download.Download_Base import Download_Base

class SNIS(Download_Base):

    def verify_download(self, main_url,path,variable,filters_order=[],form_code='302', format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            path (str): The directory path where the downloaded files will be saved.
            variable (dict): A dictionary containing information about the variable to be selected.
            filters_order (list): List specifying the order of filters to be applied.
            form_code (str): The code for the form to be selected (default is '302').
            format (str): The format of the date (default is '%Y-%m-%d').

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """

        with sync_playwright() as pl:

            gestion_link_xpath = '(//table)[3]//a'

            re_year = r'\b(\d{4})\b'

            base_url = "https://estadisticas.minsalud.gob.bo/Reportes_Dinamicos/"

            file_paths = []
            
            # Get the last year downloaded from the directory
            last_year_downloaded = max([d for d in os.listdir(path) if re.search(re_year,d)])
            
            # Erase the previous tmp path and create the a new one
            path = os.path.join(path, 'tmp')
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path)

            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=False)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                context.set_default_timeout(3600000)
                page = context.new_page()
                page.goto(main_url, wait_until='load')

                # Extract download links
                gestion_links = page.query_selector_all(gestion_link_xpath)
                gestion_links = sorted(gestion_links,key=lambda x: int(re.search(re_year,x.inner_text(),re.IGNORECASE).group(1)))
                year_downloaded = int(re.search(re_year,gestion_links[-1].inner_text(),re.IGNORECASE).group(1))
                gestion_links = [base_url + gestion_links[-1].get_attribute('href')]

                for link in gestion_links:
                    new_page = context.new_page()
                    new_page.goto(link,wait_until="load")
                    
                    # Select form and variable
                    formulario_select = new_page.query_selector('//*[@id="MainContent_DDL_form"]')
                    formulario_select.select_option(form_code)

                    new_page.wait_for_selector('#MainContent_DDL_sedes',state="visible")
                    departamento_select = new_page.query_selector('//*[@id="MainContent_DDL_sedes"]')
                    var_select = new_page.query_selector('//*[@id="MainContent_DDL_var"]')
                    generar_button = new_page.query_selector('//*[@id="MainContent_Button1"]')

                    var_select.select_option(variable["code"])

                    # Iterate over department options
                    departamento_options = departamento_select.query_selector_all('//option')
                    departamento_text = [dep.inner_text().strip().lower() for dep in departamento_options]
                    departamento_options = [dep.get_attribute('value') for dep in departamento_options]
                    for index,departamento_option_value in enumerate(departamento_options):
                    
                        departamento_select = new_page.query_selector('//*[@id="MainContent_DDL_sedes"]')
                        generar_button = new_page.query_selector('//*[@id="MainContent_Button1"]')

                        departamento_select.select_option(departamento_option_value)
                        generar_button.click()
                        print(f"Selected department: {departamento_text[index]}")     
                        
                        time.sleep(5)

                        # Apply filters
                        print("Applying filters...")
                        
                        # Logic to move filters in the columns to the rows
                        # num_column_filters = len(new_page.query_selector_all('//*[@id="ctl00_MainContent_ASPxPivotGrid1_ColumnArea"]/tbody/tr/td'))
                        # for num in range(num_column_filters):
                        #     column_filter = new_page.query_selector('//*[@id="ctl00_MainContent_ASPxPivotGrid1_ColumnArea"]/tbody/tr/td[1]')
                        #     print(f"Applying filter: {column_filter.inner_text()}")
                        #     column_filter.wait_for_element_state(state='visible')

                        #     if not column_filter:
                        #         continue

                        #     # Drag and drop the filter
                        #     column_filter.hover()
                        #     new_page.mouse.down()
                        #     new_page.locator('//*[@id="ctl00_MainContent_ASPxPivotGrid1_sortedpgHeader1S"]').hover()
                        #     new_page.mouse.up()
                        #     time.sleep(2)

                        #     # Waiting until the "Cargando.." message dissapear
                        #     new_page.wait_for_selector('#ctl00_MainContent_ASPxPivotGrid1_TL', state='hidden')
                        #     new_page.wait_for_selector('#ctl00_MainContent_ASPxPivotGrid1_DXCustFields_TL', state='hidden')
                        #     new_page.wait_for_selector('#ctl00_MainContent_ASPxPivotGrid1_DXHFP_TL', state='hidden')
                        #     time.sleep(2)
                        
                        for element in filters_order:
                            new_page.wait_for_selector('//*[@id="ctl00_MainContent_ASPxPivotGrid1_FilterArea"]/tbody/tr/td[last()]', state='visible')
                            dragdrop_filters = new_page.query_selector_all('//*[@id="ctl00_MainContent_ASPxPivotGrid1_FilterArea"]/tbody/tr/td')

                            filter_searched = [e for e in dragdrop_filters if re.search(element,e.inner_text(),re.IGNORECASE)][0]
                            if not filter_searched:
                                continue
                            print(f"Applying filter: {filter_searched.inner_text()}")
                            filter_searched.wait_for_element_state(state='visible')

                            # Drag and drop the filter
                            filter_searched.hover()
                            new_page.mouse.down()
                            new_page.locator('//*[@id="ctl00_MainContent_ASPxPivotGrid1_sortedpgHeader0S"]').hover()
                            new_page.mouse.up()
                            time.sleep(2)

                            # Waiting until the "Cargando.." message dissapear
                            new_page.wait_for_selector('#ctl00_MainContent_ASPxPivotGrid1_TL', state='hidden')
                            new_page.wait_for_selector('#ctl00_MainContent_ASPxPivotGrid1_DXCustFields_TL', state='hidden')
                            new_page.wait_for_selector('#ctl00_MainContent_ASPxPivotGrid1_DXHFP_TL', state='hidden')
                            time.sleep(2)

                        # Downloading files
                        exportar_select = new_page.query_selector('//*[@id="MainContent_ASPxComboBox1"]')
                        exportar_select.click()
                        execel_option = new_page.query_selector('//*[@id="MainContent_ASPxComboBox1_DDD_L_LBI1T0"]').hover()
                        time.sleep(1)
                        new_page.click(selector='//*[@id="MainContent_ASPxComboBox1_DDD_L_LBI1T0"]',button='left')                    
                        
                        exportar_button = new_page.query_selector('//*[@id="MainContent_ASPxButton1_CD"]')
                        with new_page.expect_download() as download_info:
                            print("Downloading file...")
                            exportar_button.click()
                            
                            download = download_info.value
                            departamento_abr = get_departamento_abr(departamento_text[index])
                            extension = download.suggested_filename.split(".")[1]
                            download_path = os.path.join(
                        path, f"{departamento_abr}_{variable['key_words']}.{extension}")
                            download.save_as(download_path)
                            file_date = self.compare_files(file_path=download_path, year=int(year_downloaded))
                            new_path = os.path.join(
                        path,f"{file_date}_{departamento_abr}_{variable['key_words']}.{extension}")
                            os.rename(download_path,new_path) 
                            file_paths.append({
                                "tmp_path": new_path})
                    
                    if file_paths:
                        return path
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

    def compare_files(self, file_path, year, format='%Y-%m-%d'):
        """
        Compares a list of files with a last file, extracts dates from the new files,
        and filters out the files based on the provided date criteria.

        Parameters:
            files_paths (list): List of dictionaries containing information about files.
            updated_to (str): The latest date for which the database contains records.

        Returns:
            list: List of dictionaries containing information about files that meet the criteria.
        """
        r_week = r"(\d{1,2})"
        df_new_file = pd.read_excel(file_path)
        index_row = df_new_file[df_new_file.iloc[:, 0]=="SEDES"].values.tolist()
        df_new_file.columns = index_row
        # for column in df_new_file.columns:
        #     if df_new_file[column].isna().all():
        #         df_new_file.drop(columns=[column], inplace=True)
        if not "MES" in df_new_file.columns:
            return "no_data"
        sub_set = df_new_file["MES"]
        sub_set = sub_set.values.tolist()
        sub_set = [re.search(r_week,str(value)) for value in sub_set if re.search(r_week,str(value))]
        if not len(sub_set):
            return "no_data"
        month = int(sub_set[-1].group(1))
        day = last_day_month(year=year, month=month)
        date = datetime.strptime(f"{year}-{month}-{day}",format)
        return date.strftime(format=format)


# if __name__ == "__main__":
#     robot = SNIS()
#     x = robot.verify_download(main_url="https://estadisticas.minsalud.gob.bo/Reportes_Dinamicos/Menu_rep_dinamicos.aspx",updated_to="2022-12-21",path=r"\\10.0.0.9\spim\SNIS\Vigilancia Epidemiologica\02 Inmunoprevenibles",filters_order=['subsector', 'ambito', 'establecimiento', 'nivel', 'tipo', 'institucion', 'municipio', 'provincia', 'semana','mes'],variable={"code":"04","key_words":"inmunoprevenibles"},form_code='302')
#     print(x)
#     # y = robot.compare_files(file_path=r"\\10.0.0.9\spim\SNIS\Vigilancia Epidemiologica\01 sospecha_diagnostica\2022\ch_inmunoprevenibles.xls", year=2022)
#     # print(y)