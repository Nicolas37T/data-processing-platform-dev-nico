import traceback
import os
import shutil
import random
import pandas as pd
from datetime import datetime
from playwright.sync_api import sync_playwright, BrowserContext
from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import format_date

def fetch_category_products(context:BrowserContext, categorie:dict)->list:
    item_xpath = '//*[@id="CollectionProductGrid"]//div[contains(@class,"grid-item ")]//div[@class="product-bottom"]'
    product_name_xpath='//a[@class="product-title "]'
    product_regular_price_xpath='//div[@class="price-regular"]'
    product_special_price_xpath='//div[@class="price-sale"]'

    try:
        page = context.new_page()
        page.goto(categorie['categorie.url'],wait_until='load')

        previous_height = page.evaluate("document.body.scrollHeight")
        while True:            
            page.evaluate(f"window.scrollTo(2000,{int(previous_height)-1300})")
            page.wait_for_timeout(2000)

            new_height = page.evaluate("document.body.scrollHeight")
            print(f"Previus:{previous_height}, actuall:{new_height}")
            if new_height == previous_height:
                break
            previous_height = new_height
        
        rows = []
        for item in page.query_selector_all(item_xpath):
            title = item.query_selector(product_name_xpath).inner_text().replace("\n", " ").strip()
            print(title)
            if item.query_selector(product_special_price_xpath):
                price = {
                    "regular_price": item.query_selector(product_special_price_xpath+'/span[@class="old-price"]').inner_text().replace("\n", " ").strip(),
                    "special_price": item.query_selector(product_special_price_xpath+'/span[@class="special-price"]').inner_text().replace("\n", " ").strip() 
                }
            else:
                price = {
                    "regular_price": item.query_selector(product_regular_price_xpath).inner_text().replace("\n", " ").strip()
                    ,"special_price": "-" 
                }

            rows.append({**categorie,'name':title, **price})
        return rows

    except Exception as e:
        print(f'There was an error whit category:{categorie["categorie.title"]}')
        traceback.print_exc()
        return []
    finally:
        page.close()

class D_BO_000000546(Download_Base):

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
        base_url = "https://www.fidalga.com/"

        # Prepare temporary path
        path = os.path.join(path, 'tmp')
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path)

        # Convert updated_to from string to datetime object
        updated_to = format_date(updated_to)        

        # Define XPaths and values to interact with the page
        categories_xpath = '//li[@class="sidebar-link-lv1 dropdown"]/a'        

        with sync_playwright() as pl:
            try:
            # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                context.set_default_timeout(300000)
                page = context.new_page()

                page.goto(main_url, wait_until='domcontentloaded')
                print(page.locator('//*[@id="shopify-section-list-collections-template"]//a[@class="btn collections-btn"]').first.inner_html())
                page.locator('//*[@id="shopify-section-list-collections-template"]//a[@class="btn collections-btn"]').first.click()
                
                page.wait_for_selector(categories_xpath,state='attached')

                categories = [{"categorie.title":item.inner_text(), "categorie.url": base_url + item.get_attribute('href')} for item in page.locator(categories_xpath).all()]

                print(categories)
                rows = []
                for cat in categories:
                    f = fetch_category_products(context=context, categorie=cat)
                    rows.extend(f)
                    seconds_to_wait = random.randint(2,5)
                    page.wait_for_timeout(seconds_to_wait*1000)
                
                df = pd.DataFrame(rows)                

                # Save data to Excel file
                file_path = os.path.join(path,f"{key_words}.xlsx")
                print(f"Saving data to Excel file: {file_path}")
                df.to_excel(file_path,index=False)

                print("Extraction completed successfully.")   
                return [{
                    "tmp_path":file_path,
                    "updated_to":datetime.now().strftime(format=format),
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

Executor_D_BO_000000546 = D_BO_000000546
Robot = D_BO_000000546
