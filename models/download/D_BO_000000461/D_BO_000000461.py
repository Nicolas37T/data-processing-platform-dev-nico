import sys, os, asyncio, traceback, shutil
sys.path.append("..")
from playwright.async_api import async_playwright
from datetime import datetime
from more_itertools import chunked
import pandas as pd
from models.download.tools.download_tools import format_date
from models.download.Download_Base import Download_Base

class D_BO_000000461(Download_Base):

    async def get_data(self, main_url, path, updated_to,format='%Y-%m-%d'):
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
            # Today date to filter data
            today = datetime.today()

            # Create the temporary directory to save files
            new_file_path = os.path.join(path, 'tmp')
            if os.path.exists(new_file_path):
                shutil.rmtree(new_file_path)
            os.makedirs(new_file_path)

            base_url = "https://appweb.asfi.gob.bo/Reportes_asp/rmi/"
            files_dicts = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = await pl.chromium.launch(headless=False)
                context = await browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                context.set_default_timeout(1800000)
                page = await context.new_page()
                await page.goto(main_url,wait_until='load')
                
                # Get the URL of the main frame and navigate to it
                main_frame_url = page.frames[-1].url
                await page.goto(main_frame_url,wait_until='load')

                # Extract links for "Emisores"
                emisores_links = [base_url + await link.get_attribute('href') for link in await page.query_selector_all('//li/font[contains(text(), "Emisores")]/../following-sibling::ul[1]//a[@href]')]

                async def scrape_task(link):
                    try:
                        new_page = await context.new_page()
                        await new_page.goto(link,wait_until='load')

                        # Extract emisor code
                        emisor_code = await (await new_page.query_selector('//td/font[contains(text(), "Sigla")]/../following-sibling::td[1]//font')).inner_text()
                        print(f"Emisor code: {emisor_code}")

                        # Extract financial statement link and navigate to it
                        estado_financiero_link = base_url + await (await new_page.query_selector('//a[@class="c2"]')).get_attribute('href')
                        await new_page.goto(estado_financiero_link,wait_until='load')

                        # Extract available dates and filter them 
                        date_select_options = [await option.get_attribute('value') for option in await new_page.query_selector_all('//*[@id="lstFecha"]//option') if format_date(await option.get_attribute('value'),"%Y%m%d").year>=today.year]
                        
                        if not len(date_select_options):
                            print(f"There is no new data for: {emisor_code}")
                            await new_page.close()
                            return []
                        
                        emisor_rows = []
                        for date in date_select_options:
                            await new_page.locator('#lstFecha').select_option(date)
                            date_formated = format_date(date,"%Y%m%d").strftime(format)
                            print(f"Date selected: {date_formated}")

                            await new_page.wait_for_selector('//table[@cellpadding="1"]//tr', state='attached')
                            # Extract rows from the financial table
                            rows = [await row.query_selector_all("td") for row in await new_page.query_selector_all('//table[@cellpadding="1"]//tr')]
                            rows = [[await i.inner_text() for i in row] for row in rows]
                            rows = [row for row in rows if row and str(row[1])!="Saldo"]
                            
                            if not rows:
                                continue

                            for row in rows:
                                row.insert(0,date_formated)
                                row.insert(0,emisor_code)
                            emisor_rows.extend(rows)

                        if not len(emisor_rows):
                            print(f"There is no new data for: {emisor_code}")
                            await new_page.close()
                            return []
                        
                        # Get the last date of data for the emisor
                        emisor_last_date = emisor_rows[0][1]

                        # Create DataFrame and save to Excel
                        df = pd.DataFrame(emisor_rows,columns=["Sigla", "Fecha", "Cuenta", "Saldo"])        
                        file_path = os.path.join(new_file_path, f"{emisor_last_date}_{emisor_code}.xlsx")
                        df.to_excel(file_path,index=False,)

                        files_dicts.append(file_path)
                        print(f"Data extracted and saved for: {emisor_code}")
                        await new_page.close()
                        
                    except Exception as e:
                        print(f"An error ocurred: {e}")
                        traceback.print_exc()
                        await new_page.close()

                # Define batch size for scraping
                batch_size = 8
                links_batches = chunked(emisores_links,batch_size)
                links_batches = list(links_batches)

                # Process each batch of options concurrently
                for batch in links_batches:
                    tasks = [scrape_task(link) for link in batch]
                    await asyncio.gather(*tasks)

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
                    await page.close()
                if 'browser' in locals():
                    await browser.close()
    
# if __name__ == "__main__":
#     robot = Executor_D_BO_000000461()
#     x = asyncio.run(robot.get_data(main_url="https://www.asfi.gob.bo/index.php/registro-rmv/mv-entidades-inscritas-en-el-rmv.html",path=r"\\10.0.0.9\SPIM\ASFI\Entidades Inscritas"))
#     print(len(x))
#     print(x)
#     # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': '\\\\10.0.0.9\\spim\\INE\\ESTADISTICAS ECONOMICAS\\SALARIOS Y REMUNERACIONES\\SECTOR PRIVADO\\02_Grupo Ocupacional\\tmp\\2024-05-13_155615download.xlsx'}]
#     # y = robot.compare_files(files_paths=files,updated_to="2023-01-21")
#     # print(y)

Executor_D_BO_000000461 = D_BO_000000461
Robot = D_BO_000000461
