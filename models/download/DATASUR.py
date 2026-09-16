import os
import traceback
import asyncio
import re
from playwright.async_api import async_playwright, expect
from datetime import datetime
from dotenv import load_dotenv
from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import last_day_month

class DATASUR(Download_Base):
    
    # Dictionary mapping country names to their respective codes and operation types (export/import).
    country_dict = {
            "Argentina":{
                "code":"2",
                "ex": 22,
                "im": 21
                },
            "Bolivia":{
                "code":"6",
                "ex": 460,
                "im": 461
                },
            "Chile":{
                "code":"1",
                "ex": 9,
                "im": 8
                },
            "Colombia":{
                "code":"7",
                "ex": 177,
                "im": 175
                },
            "Costa Rica":{
                "code":"19",
                "ex": 455,
                "im": 457
                # "ex": 342,
                # "im": 340
                },
            "Ecuador":{
                "code":"21",
                "ex": 147,
                "im": 146
                },
            "Guatemala":{
                "code":"24",
                "ex": 284,
                "im": 283
                },
            "Mexico":{
                "code":"37",
                "ex": 293,
                "im": 292
                },
            "Nicaragua":{
                "code":"64",
                "ex": 471,
                "im": 469
                },
            "Panama":{
                "code":"5",
                "ex": 56,
                "im": 55
                },
            "Paraguay":{
                "code":"4",
                #"ex": 46,
                #"im": 45
                "ex": 409,
                "im": 408
                },
            "Perú":{
                "code":"25",
                "ex": 185,
                "im": 167
                },
            "Uruguay":{
                "code":"3",
                "ex": 31,
                "im": 30
                },
            "Venezuela":{
                "code":"18",
                "ex": 106,
                "im": 105
                }
        }

    async def download_file(self, page, download_path, filename):
        """
        Download a file and save it to the specified path.
        
        Parameters:
        page (Page): The Playwright page object.
        download_path (str): The path where the file will be saved.
        filename (str): The name for the downloaded file.
        """
        async with page.expect_download() as download_info:
            await page.locator('#btn_gen_download').click()
            download = await download_info.value
            extension = download.suggested_filename.split(".")[-1]
            full_path = os.path.join(download_path, f"{filename.replace('?','')}.{extension}")
            await download.save_as(full_path)
        print(f"Downloaded file saved as: {full_path}")
    
    def get_flags(self, path):
        """
        Retrieves the latest file from a directory and extracts operation, country, and month details.

        Parameters:
        path (str): The path to the directory containing files.

        Returns:
        tuple: Contains the country, operation (ex/im), and month if available.
        """
        # List all files in the specified path
        files = os.listdir(path)
        datetime.fromtimestamp
        if not files:
            print("No files found in the directory.")
            return (None,"ex",None)
        
        # Create a list of files with their last modified dates
        files = [{"file":element, "date":datetime.fromtimestamp(os.path.getmtime(os.path.join(path,element)))} for element in files]
        
        # Sort files by date (oldest to newest)
        files = sorted(files,key=lambda x: x['date'])
        last_file = files[-1]["file"]
        print(f"Latest file found: {last_file}")

        # Extract operation, country, and month from the filename
        last_file = last_file.split(".")[0]
        last_file = last_file.split("_")

        operation = last_file[1]
        country = last_file[2]
        month = int(last_file[3]) if len(last_file)>3 else None

        return (country,operation, month)

    def missing_downloads_log(self,path,country,message):
        """
        Logs missing downloads for a specific country.

        Parameters:
        path (str): The path to the log file.
        country (str): The country code.
        message (str): The message to log.
        """
        log_file = os.path.join(path,f"{country}_Missing_Downloads.txt")
        num = 0

        # Create a new log file if it doesn't exist
        if not os.path.exists(log_file):
            with open(log_file, 'w') as f:                
                f.write(f"Nro   Execution Date      Missing_download\n")
        else:
            # Read the log file and remove trailing empty lines
            with open(log_file, 'r') as f:
                lines = f.readlines()

            while lines[-1].strip() == '':
                if len(lines)==0:
                    raise Exception("Log file empty")
                lines = lines[:-1]

            with open(log_file, 'w') as f:
                f.writelines(lines)

            # Get the last number from the log file   
            last_line = lines[-1].split()
            num = int(last_line[0]) if last_line[0].isdigit() else 0

        # Append new log entry
        now = datetime.now()
        with open(log_file, 'a') as f:            
            num=num+1
            f.write(f"{str(num).ljust(5)} {now.strftime('%Y-%m-%d %H:%M:%S')} {'-'.ljust(13)} {message}\n")
        print(f"Missing download logged for {country}: {message}")

    async def get_data_main(self, main_url,country_path,user,password, country, year_flag=0, country_flag=None, operation_flag="ex", month_flag=None, resume=False):
        """
        Main method to download data from the given URL for a specified country.

        Parameters:
        main_url (str): The main URL to access.
        country_path (str): Path where files will be saved.
        user (str): Username environment variable name.
        password (str): Password environment variable name.
        country (str): Country code.
        year_flag (int): Year to start downloading from.
        country_flag (str): Specific country filter.
        operation_flag (str): Operation type ('ex' for export, 'im' for import).
        month_flag (int): Specific month filter.
        resume (bool): Flag to resume downloads from the last point.
        """
        load_dotenv()

        # Load username and password from environment variables
        username = os.getenv(user)
        password = os.getenv(password)        

        # If resume flag is set, get flags for the latest file to continue from
        if resume:
            country_flag, operation_flag, month_flag = self.get_flags(path=country_path)        
        
        async with async_playwright() as pl:
            try: 
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = await pl.chromium.launch(headless=True)
                context = await browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                context.set_default_timeout(900000)
                new_page = await context.new_page()
                await new_page.goto(main_url,wait_until='load')

                # Login process
                await new_page.wait_for_selector("#ds_username",state="visible")
                email_input = await new_page.query_selector('//*[@id="ds_username"]')
                password_input = await new_page.query_selector('//*[@id="ds_password"]')
                submit_button = await new_page.query_selector('//*[@id="ds_submit"]')

                await email_input.fill(username)
                await password_input.fill(password)
                await submit_button.click()
                print("Submitted login form.")
                
                # Select country and operation
                button = await new_page.query_selector(f'//a[@data-search="{self.country_dict[country]["code"]}"]')
                await button.click()
                await new_page.wait_for_selector("#oper", state="visible")
                await asyncio.sleep(3)

                # Handle any notices that may pop up
                notice_button = await new_page.query_selector('//*[@id="noticemodal"]//button[@class="close"]')
                if notice_button:
                    await notice_button.click() 

                # Fetch available years for data
                year_options = [await item.get_attribute("value") for item in await new_page.query_selector_all('//*[@id="anio"]/option')]
                if int(year_flag) >0:
                    year_options = [item for item in year_options if int(item) >= int(year_flag)]
                    if not year_options:
                        print(f"The country {country} does not have data after {year_flag}")
                        return ""                
                
                counter = 0
                # Iterate over available years
                for year in sorted(year_options):
                    operation_options = ["im"] if operation_flag == "im" and counter == 0 else ["ex", "im"]

                    # Iterate over export and import options
                    for operation in operation_options:
                        filter_code = self.country_dict[country]["ex"] if operation == "ex" else self.country_dict[country]["im"]
                        await new_page.locator("#oper").select_option(operation)

                        # Fetch available country sources for the selected operation
                        country_source_options = [((await item.inner_text()).strip(), await item.get_attribute("value")) for item in await new_page.query_selector_all(f'//*[@id="filtros"]//select[@id="inp_{filter_code}"]/option')]                
                        country_source_options_b = [item for item in country_source_options if item[0] and item[0].lower() != "todas"]

                        # Apply country filter if specified
                        if country_flag and counter == 0:
                            index = next((i for i, tupla in enumerate(country_source_options) if tupla[0].strip().lower() == country_flag), None)
                            country_source_options = country_source_options_b[index-1:]
                        else:
                            country_source_options = country_source_options_b
                    
                        # Select the desired year from the dropdown
                        await new_page.locator("#anio").select_option(year)
                        await asyncio.sleep(2)
                        print(f"Year: {year} was selected")

                        # Set the period filters to cover the full year (January to December)
                        await new_page.locator('//*[@id="periodo"]//select[@name="finmon"]').select_option(index=11)
                        await new_page.locator('//*[@id="periodo"]//select[@name="inimon"]').select_option("01")
                        
                        await asyncio.sleep(3)

                        # Iterate over filtered country sources
                        for item in country_source_options:
                            # Select an option from the filter dropdown and click the search button
                            await new_page.locator(f'//*[@id="filtros"]//select[@id="inp_{filter_code}"]').select_option(item[1])
                            await new_page.locator('#search').click()

                            # Wait for the modal dialog to appear, indicating search results
                            await new_page.wait_for_selector('//*[@id="modal" and contains(@class, "show")]', state="visible")
                            await expect(new_page.locator('//*[@id="modal" and contains(@class, "show")]//div[@class="modal-body"]')).to_have_text(re.compile(r'\d+'),timeout=900000)
                            await asyncio.sleep(2)

                            # Get and print the text from the modal, which includes the number of records found
                            text = await (await new_page.query_selector('//*[@id="modal"]//div[@class="modal-body"]')).inner_text()
                            print(f"Source: {item[0]}")  
                            print(f"Records found: {text}")
                            regs_found = int(re.search(r'\d+', text).group())

                            # Get the final month of the selected period and format the date string
                            final_month = await new_page.eval_on_selector('//*[@id="periodo"]//select[@name="finmon"]', 'select => select.value')                            
                            day = last_day_month(year=int(year), month=int(final_month))
                            country_date = f'{year}-{final_month}-{day:02}'

                            # Close the modal
                            await new_page.locator('//*[@id="modal"]//button[@class="close"]').click()

                            # If no records found, skip to the next iteration
                            if regs_found == 0:
                                await asyncio.sleep(5)
                                continue

                            # If too many records found, filter further by months and/or customs offices
                            if regs_found >200000:
                                print(f"Too many records found for {item[0]}, filtering further...")
                                await asyncio.sleep(3)                                

                                # Get available month options up to the final month
                                month_options = [((await item.inner_text()).strip(), await item.get_attribute("value")) for item in await new_page.query_selector_all(f'//*[@id="periodo"]//select[@name="finmon"]/option')]
                                month_options = [item for item in month_options if item[1] and int(item[1]) <= int(final_month)]
                                month_options = month_options[month_flag:] if month_flag is not None and counter == 0 else month_options

                                # Iterate over the filtered months
                                for month in month_options:
                                    await new_page.locator('//*[@id="periodo"]//select[@name="finmon"]').select_option(month[1])
                                    await new_page.locator('//*[@id="periodo"]//select[@name="inimon"]').select_option(month[1])

                                    # Perform the search again for each month
                                    await new_page.locator('#search').click() 

                                    # Wait for the modal dialog to appear and get the record count
                                    await new_page.wait_for_selector('//*[@id="modal" and contains(@class, "show")]', state="visible")
                                    await expect(new_page.locator('//*[@id="modal" and contains(@class, "show")]//div[@class="modal-body"]')).to_have_text(re.compile(r'\d+'),timeout=900000)
                                    await asyncio.sleep(2)

                                    # Get and print the text from the modal, which includes the number of records found
                                    text = await (await new_page.query_selector('//*[@id="modal"]//div[@class="modal-body"]')).inner_text()
                                    print(f"Month: {month[0]}")  # Print the month being processed
                                    print(f"Records found: {text}")
                                    regs_found = int(re.search(r'\d+', text).group())
                                    
                                    # Close the modal
                                    await new_page.locator('//*[@id="modal"]//button[@class="close"]').click()

                                    # Skip if no records found
                                    if regs_found == 0:
                                        await asyncio.sleep(5)
                                        continue
                                    
                                    # If records are still too many, filter by customs offices
                                    if regs_found >200000:
                                        print(f"Filtering by customs for {item[0]}, {year}, {month[0]}")
                                        await asyncio.sleep(3)
                                        aduana_select = await new_page.query_selector(f'//*[@id="filtros"]//label[text()="aduana:"]/following-sibling::select')
                                        if not aduana_select:
                                            self.missing_downloads_log(path=country_path, country=country, message=f'{year}_{item[0]}_{month[0]}')
                                            continue
                                        
                                        aduna_options = [((await item.inner_text()).strip(), await item.get_attribute("value")) for item in await new_page.query_selector_all(f'//*[@id="filtros"]//label[text()="aduana:"]/following-sibling::select/option')]
                                        aduna_options = [item for item in aduna_options if item[0] and item[0].lower() != "todas"]

                                        # Iterate over available customs offices
                                        for element in aduna_options:
                                            await new_page.get_by_label("aduana:", exact=True).select_option(element[1])

                                            # Perform search for each customs office
                                            await new_page.locator('#search').click() 

                                            # Wait for the modal dialog to appear and get the record count
                                            await new_page.wait_for_selector('//*[@id="modal" and contains(@class, "show")]', state="visible")
                                            await expect(new_page.locator('//*[@id="modal" and contains(@class, "show")]//div[@class="modal-body"]')).to_have_text(re.compile(r'\d+'),timeout=900000)
                                            await asyncio.sleep(3)

                                            # Get and print the text from the modal, which includes the number of records found
                                            text = await (await new_page.query_selector('//*[@id="modal"]//div[@class="modal-body"]')).inner_text()
                                            print(f"Customs: {element[0]}") 
                                            print(f"Records found: {text}")
                                            regs_found = int(re.search(r'\d+', text).group())

                                            # Close the modal
                                            await new_page.locator('//*[@id="modal"]//button[@class="close"]').click()

                                            # Skip if no records found
                                            if regs_found == 0:
                                                await asyncio.sleep(5)
                                                continue

                                            # Log and skip if still too many records
                                            if regs_found >200000:
                                                print(element[0],year, country)
                                                await asyncio.sleep(5)
                                                self.missing_downloads_log(path=country_path, country=country, message=f'{year}_{item[0]}_{month[0]}_{element[0]}')
                                                continue
                                                
                                            # Proceed with the download if records are manageable          
                                            else:
                                                await new_page.locator('#export').click()
                                                await new_page.wait_for_selector('#exportModalMultiple', state="visible")

                                                # Perform the file download
                                                await self.download_file(page=new_page, download_path=country_path, filename=f"{country_date}_{operation}_{item[0]}_{month[1]}_{element[0]}")
                                            
                                                await new_page.locator('//*[@id="exportModalMultiple"]//button[@class="close"]').click()
                                                await asyncio.sleep(5) 

                                        # Reset the customs filter to 'all'
                                        await new_page.get_by_label("aduana:", exact=True).select_option(label="todas")
                                    
                                    # Download if record count is acceptable after month filtering
                                    else:
                                        await new_page.locator('#export').click()
                                        await new_page.wait_for_selector('#exportModalMultiple', state="visible")

                                        # Perform the file download
                                        await self.download_file(page=new_page, download_path=country_path, filename=f"{country_date}_{operation}_{item[0]}_{month[1]}")
                                        
                                        await new_page.locator('//*[@id="exportModalMultiple"]//button[@class="close"]').click()
                                        await asyncio.sleep(5) 

                                counter = counter + 1 # Increment the counter for each filtered search

                                # Reset the month range for the next operation
                                await new_page.locator('//*[@id="periodo"]//select[@name="finmon"]').select_option(index=11)
                                await new_page.locator('//*[@id="periodo"]//select[@name="inimon"]').select_option("01")

                            # If record count is acceptable without further filtering, proceed with download        
                            else:
                                await new_page.locator('#export').click()
                                await new_page.wait_for_selector('#exportModalMultiple', state="visible")

                                # Perform the file download
                                await self.download_file(page=new_page, download_path=country_path, filename=f"{country_date}_{operation}_{item[0]}")

                                await new_page.locator('//*[@id="exportModalMultiple"]//button[@class="close"]').click()
                                await asyncio.sleep(5) 

                        counter = counter + 1 # Increment the counter  

                    counter = counter + 1

                return country_path    
            except Exception as e:
                    print(f"An error ocurred: {e}")
                    traceback.print_exc()
                    return None
            finally:
                # Close page and browser
                if 'page' in locals():
                    await new_page.close()
                if 'browser' in locals():
                    await browser.close()

