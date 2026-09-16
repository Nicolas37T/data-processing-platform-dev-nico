import sys, re, traceback,asyncio,time,os, shutil
sys.path.append("..")
from playwright.async_api import async_playwright
from models.download.tools.download_tools import format_date
from models.download.Download_Base import Download_Base
from more_itertools import chunked

class D_BO_000000056(Download_Base):

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
            re_date = r"\d{4}\D*\d{1,2}\D*\d{1,2}"
            base_url = "https://data.un.org/"

            # Create the temporary directory to save files
            new_file_path = os.path.join(path, 'tmp')
            if os.path.exists(new_file_path):
                shutil.rmtree(new_file_path)
            os.makedirs(new_file_path)

            files_dicts = []
            tasks = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = await pl.chromium.launch(headless=False)
                context = await browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                context.set_default_timeout(1800000)
                page = await context.new_page()
                await page.goto(main_url,wait_until='load')
                await page.wait_for_selector("#ygtvt3",state="visible")
                
                # Click on the specified element to load the next page
                await page.click(selector='#ygtvt3 a')
                time.sleep(2)
                await page.wait_for_selector('//*[@id="ygtvc3"]/div[@class="ygtvitem"][1]',state="attached")

                # Extract links to data pages
                links = [base_url +  await link.get_attribute('href') for link in await page.query_selector_all('//*[@id="ygtvc3"]/div[@class="ygtvitem"]//a[@title="View data"]')]

                # Define async function to scrape data from each link
                async def scrape_task(link):

                    try:
                        new_page = await context.new_page()
                        await new_page.goto(link, wait_until='load')

                        # Extract title and code
                        title = await new_page.query_selector('//div[@class="SeriesMeta"]/h2')
                        title = await title.inner_text()
                        code = re.search(r',\s(\d{2}|All)',title).group(1)

                        # Extract and format date
                        date = await new_page.query_selector('//div[@class="Update"]')
                        date = re.search(re_date, await date.inner_text()).group()
                        date_formated = format_date(date, format="%Y/%m/%d")
                        
                        chunk_size = 35
                        for i in range(6):
                            # Deselect and select country filters in batches
                            country_filters = await new_page.query_selector_all('//*[@id="divCountryorAreaInner"]//input[@type="checkbox"]')
                            [await f.set_checked(False) for f in country_filters[:len(country_filters)]]
                            country_filters_batches = list(chunked(country_filters, chunk_size))
                            selected_batch = country_filters_batches[i]
                            [await select.set_checked(True) for select in selected_batch]
                            # year_filters = await new_page.query_selector_all('//*[@id="divYearInner"]//input[@type="checkbox"]')
                            # [await f.set_checked(True) for f in year_filters]

                            # Apply filters and wait for the page to load
                            apply_button = await new_page.query_selector('#ctl00_main_filters_anchorApplyBottom')
                            await apply_button.click()
                            await new_page.wait_for_load_state(state="load")
                            await asyncio.sleep(10)
                            download_button = await new_page.query_selector('//*[@id="ctl00_main_actions_download"]/a[@title]')
                            await download_button.click()

                            # Initiate file download
                            download_csv_button = await new_page.query_selector('#downloadCommaLink')
                            async with new_page.expect_download() as download_info:
                                await download_csv_button.click()
                            download = await download_info.value
                            download_path = os.path.join(
                                new_file_path, f"{date_formated.strftime(format)}_{code}_{i}.zip")
                            await download.save_as(download_path)
                            files_dicts.append(download_path)
                        await new_page.close()
                    
                    except Exception as e:
                        print(f"An error ocurred: {e}")
                        traceback.print_exc()
                        await new_page.close()
                    
                batch_size = 8
                links_batches = chunked(links,batch_size)
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
                return []
            finally:
                # Close page and browser
                if 'page' in locals():
                    await page.close()
                if 'browser' in locals():
                    await browser.close()
    
# if __name__ == "__main__":
#     robot = D_BO_000000056()
#     x = asyncio.run(robot.get_file_url(main_url="http://data.un.org/Explorer.aspx",updated_to="2023-9-21", path=r"\\10.0.0.9\spim\UN DATA\Commodity Trade Statistics Database\2024_robot"))
#     print(len(x))
#     print(x)
#     # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': '\\\\10.0.0.9\\spim\\INE\\ESTADISTICAS ECONOMICAS\\SALARIOS Y REMUNERACIONES\\SECTOR PRIVADO\\02_Grupo Ocupacional\\tmp\\2024-05-13_155615download.xlsx'}]
#     # y = robot.compare_files(files_paths=files,updated_to="2023-01-21")
#     # print(y)

Executor_D_BO_000000056 = D_BO_000000056
Robot = D_BO_000000056
