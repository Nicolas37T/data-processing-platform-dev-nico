import sys, traceback, os,asyncio, shutil
sys.path.append("..")
from playwright.async_api import async_playwright
from datetime import datetime
import pandas as pd
from models.download.tools.download_tools import format_date
from models.download.Download_Base import Download_Base
from more_itertools import chunked

class D_BO_000000058(Download_Base):

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

        async with async_playwright() as pl:
            # Convert updated_to string to datetime object
            today = datetime.today()

            # Erase the previous tmp path and create the a new one 
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
                await page.goto(main_url, wait_until='load')
                
                # Get all options from the dropdown
                input_options = [await option.inner_text() for option in await page.query_selector_all('//*[@id="DxCmbFondos_DDD_L_LBT"]//td')]
                print(input_options)

                async def scrape_task(option):
                    try:
                        new_page = await context.new_page()
                        await new_page.goto(main_url,wait_until='load')
                        fondo_input = await new_page.query_selector('#DxCmbFondos_I')
                        await fondo_input.fill(option)

                        start_date_input = await new_page.query_selector('#DxTxtFechaInicial_I')
                        end_date_input = await new_page.query_selector('#DxTxtFecha_I')
                        update_button = await new_page.query_selector('#DxBtnActualizar')

                        await start_date_input.fill(f"01/01/{today.year}")
                        await end_date_input.fill(today.strftime(format='%d/%m/%Y'))
                        await update_button.click()
                        await new_page.wait_for_selector('//*[@id="DxGrvEvolutivos_DXMainTable"]//tr[@class="dxgvDataRow" or @class="dxgvEmptyDataRow"][1]',state='visible')
                
                
                        # Extract the date from the page
                        date = await new_page.query_selector('//*[@id="DxGrvEvolutivos_DXMainTable"]//tr[@class="dxgvDataRow"][1]/td[2]')
                        if not date:
                            print("There is no data.")
                            await new_page.close()
                            return []
                        date = await date.inner_text()

                        # Format the extracted date
                        data_date = format_date(date,format=format)
                
                        # Extract data rows
                        headers = await new_page.query_selector_all('//*[@id="DxGrvEvolutivos_DXHeadersRow0"]/td')
                        rows =[]
                        while True:
                            page_rows = await new_page.query_selector_all('#DxGrvEvolutivos_DXMainTable tr.dxgvDataRow')
                            if len(page_rows):
                                rows.extend(page_rows)
                            next_button = await new_page.query_selector('//*[@id="DxGrvEvolutivos_DXPagerBottom"]/a[@class="dxp-button dxp-bi"]/img[@class="dxWeb_pNext"]/..')
                            if not next_button:
                                break
                            await next_button.click()
                            await asyncio.sleep(2)

                        # Extract cell data from each row
                        rows = [await row.query_selector_all("td") for row in rows]
                        rows = [[await i.inner_text() for i in row] for row in rows]
                        headers = [await i.inner_text() for i in headers] 
                        code =rows[0][0]
                        # Create a DataFrame and save it to an Excel file
                        df = pd.DataFrame(rows,columns=headers)
                        file_path = os.path.join(path,f"{data_date.strftime(format)}_{code}.xlsx")
                        df.to_excel(file_path,index=False,)
                        print(f"Data for {option} was extracted and saved.")
                        files_downloaded.append(file_path)
                        await new_page.close()

                    except Exception as e:
                        print(f"An error ocurred: {e}")
                        traceback.print_exc()
                        await new_page.close()

                # Define batch size for scraping
                batch_size = 8                
                options_batches = chunked(input_options,batch_size)

                # Process each batch of options concurrently
                for batch in options_batches:
                    tasks = [scrape_task(link) for link in batch]
                    await asyncio.gather(*tasks)
                print(path, len(files_downloaded))
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
    
if __name__ == "__main__":
    robot = Executor_D_BO_000000058()
    y = robot.store_new_data(path=r'/media/spim_10009/SPVS/Evolucion de fondos de Inversion (Din)', tmp_path=r'/media/spim_10009/SPVS/Evolucion de fondos de Inversion (Din)/tmp', last_file_path=r"/media/spim_10009/SPVS/Evolucion de fondos de Inversion (Din)/2024/2024-06/2024-06-23")
#     x = robot.check_new_data(main_url="https://appweb2.asfi.gob.bo/PaginasPublicas2/vistareportevalores/EvolutivoFondosInversion.aspx",updated_to="2024-1-21",path = r'D:\DATAX\Download_SPIM\base_path\tmp', key_words="evolucion")
#     print(x)
#     # y = robot.compare_files(files_paths=[{"tmp_path": r"C:\Users\Kevin Padilla\Downloads\01.03.xlsx"}],updated_to="2023-01-21")
#     # print(y)
#     

Executor_D_BO_000000058 = D_BO_000000058
Robot = D_BO_000000058
