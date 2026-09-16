import sys, traceback,asyncio, os, shutil
sys.path.append("..")
from playwright.async_api import async_playwright
from datetime import datetime, timedelta
import pandas as pd
from models.download.Download_Base import Download_Base
from more_itertools import chunked

class D_BO_000000057(Download_Base):

    async def get_data(self, main_url,path, updated_to,format='%Y-%m-%d'):
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
        print("Starting the data extraction process...")

        async with async_playwright() as pl:
            # Get current date and set the range of days to scrape
            today = datetime.today()
            days_before = 31

            # Prepare temporary directory for storing files
            path = os.path.join(path, 'tmp')
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path)

            files_downloaded = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = await pl.chromium.launch(headless=False)
                context = await browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                context.set_default_timeout(1800000)
                page = await context.new_page()
                await page.goto(main_url,wait_until='load')

                # Get all options from the dropdown
                input_options = [await option.inner_text() for option in await page.query_selector_all('//*[@id="DxCmbFondos_DDD_L_LBT"]//td')]
                print(input_options)

                async def scrape_task(option):
                    try:
                        new_page = await context.new_page()
                        await new_page.goto(main_url,wait_until='load')
                        await asyncio.sleep(3)
                        await new_page.wait_for_selector("#DxGrvEmisores_DXMainTable",state="visible")

                        fondo_input = await new_page.query_selector('#DxCmbFondos_I')
                        await fondo_input.fill(option)
                        fondo_code = ''
                        rows = []
                        for i in range(days_before):
                            date_input = await new_page.query_selector('#DxTxtFecha_I')
                            update_button = await new_page.query_selector('#DxBtnActualizar_CD')
                            await date_input.fill((today-timedelta(days=i)).strftime('%d/%m/%Y'))

                            await update_button.click()                                                    
                            await new_page.wait_for_selector("#DxGrvEmisores_DXMainTable",state="visible")                            
                            fondo_code_element = await new_page.query_selector('//*  [@id="DxGrvDatosFondos_DXDataRow0"]/td[1]')
                            if fondo_code_element:            
                                fondo_code = await (fondo_code_element).inner_text()

                            headers = await new_page.query_selector_all('//*[@id="DxGrvEmisores_DXHeadersRow0"]/td')
                            headers = [await i.inner_text() for i in headers] 

                            # Collect data from the table rows
                            page_rows = await new_page.query_selector_all("#DxGrvEmisores_DXMainTable tr.dxgvDataRow")
                            if len(page_rows)>3:
                                data_rows = [await e.query_selector_all("//td") for e in page_rows]
                                data_rows = [[await i.inner_text() for i in e] for e in data_rows]
                                df = pd.DataFrame(data_rows,columns=headers)
                                df["Fecha"] = (today-timedelta(days=i)).strftime(format=format)                                
                                rows.append(df)

                        # If no rows collected, print message and close page
                        if not len(rows):
                            print(f"There is no data after the date: {(today-timedelta(days=days_before)).strftime(format=format)} in {option}")
                            await new_page.close()
                            return []
                        
                        df_combined = pd.concat(rows,axis=0,ignore_index=True)
                        df_combined["fondo_inversion"] = fondo_code
                        df_combined = df_combined[["Fecha","fondo_inversion"] + headers]
                        now = datetime.now().strftime("%H_%M_%S")
                        # Create a DataFrame and save it to an Excel file                        
                        file_path = os.path.join(path,f"{df_combined['Fecha'].iloc[0]}_{fondo_code}_{now}.xlsx")
                        df_combined.to_excel(file_path,index=False,)
                        print(f"Data for {option} was extracted and saved. Fondo_code: {fondo_code}")
                        files_downloaded.append(fondo_code)
                        await new_page.close()
                        
                    except Exception as e:
                        print(f"An error ocurred with '{option}' : {e}")
                        traceback.print_exc()
                        await new_page.close()
                
                # Define batch size for scraping
                batch_size = 8                
                options_batches = chunked(input_options,batch_size)

                # Process each batch of options concurrently
                for batch in options_batches:
                    tasks = [scrape_task(link) for link in batch]
                    await asyncio.gather(*tasks)

                if files_downloaded:
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
                    await page.close()
                if 'browser' in locals():
                    await browser.close()
        
    
# if __name__ == "__main__":
#     robot = D_BO_000000057()
#     # x = asyncio.run(robot.get_data(main_url="https://appweb2.asfi.gob.bo/PaginasPublicas2/vistareportevalores/fondosInversionGeneral.aspx", path=r"\\10.0.0.9\spim\SPVS\Información de Fondos de Inversión"))
#     y = robot.store_new_data(path=r"\\10.0.0.9\spim\SPVS\Información de Fondos de Inversión",last_file_path=r"\\10.0.0.9\spim\SPVS\Información de Fondos de Inversión\2024\2024-06\2024-06-01")
#     print(y)
#     # print(len(x))
#     # print(x)
#     # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': '\\\\10.0.0.9\\spim\\INE\\ESTADISTICAS ECONOMICAS\\SALARIOS Y REMUNERACIONES\\SECTOR PRIVADO\\02_Grupo Ocupacional\\tmp\\2024-05-13_155615download.xlsx'}]
#     # y = robot.compare_files(files_paths=files,updated_to="2023-01-21")
#     # print(y)

Executor_D_BO_000000057 = D_BO_000000057
Robot = D_BO_000000057
