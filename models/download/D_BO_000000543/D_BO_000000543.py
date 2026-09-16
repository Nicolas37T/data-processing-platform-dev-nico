import traceback
import os
import shutil
import requests
import time
import json
import pandas as pd
from datetime import datetime
from models.download.Download_Base import Download_Base

def get_dataframe(data:dict) -> pd.DataFrame:   
    
    rows = []

    for cat in data:
        cat_meta = {f'categoria.{k}': v if not isinstance(v, list) else str(v) for k, v in cat.items() if k != 'productos'}
        
        for product in cat.get('productos', []):
            product_meta = {f'producto.{k}': v if not isinstance(v, list) else str(v) for k, v in product.items() if k != 'items'}
            
            for item in product.get('items', []):
                item_meta = {f'item.{k}': v if not isinstance(v, list) else str(v) for k, v in item.items() if k != 'sellers'}
                
                for seller in item.get('sellers', []):
                    commertial_df = pd.json_normalize(seller.get('commertialOffer', {}))
                    seller_meta = {f'seller.{k}': v for k, v in seller.items() if k != 'commertialOffer'}

                    full_row = {**commertial_df.iloc[0].to_dict(), **seller_meta, **item_meta, **product_meta, **cat_meta}
                    rows.append(full_row)

    return pd.DataFrame(rows) 

class D_BO_000000543(Download_Base):

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

        # Erase the previous tmp path and create the a new one 
        path = os.path.join(path, 'tmp')
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path)

        categories_url = 'https://www.icnorte.com/api/catalog_system/pub/category/tree/100'
        products_url = 'https://www.icnorte.com/api/catalog_system/pub/products/search/'

        try:
            # Create a session and update headers
            print("Initializing session and setting headers...")
            session = requests.Session()
            session.headers.update(self.headers)
            
            # Fetch the categories
            print("Requesting category list...")
            result = session.get(categories_url)

            if result.status_code != 200:
                raise Exception('There was an error trying to get categories')
            
            categories = result.json()
            data = [{"categoria":item['name'], 'url': item['url']} for item in categories]
            print(f"Found {len(data)} categories")

            for category in data:
                offset=0
                products = []
                print(f"\nProcessing category: {category['categoria']}")
                
                while True:                    
                    params = {'_from': offset * 8, '_to': (offset + 1) * 8 - 1}
                    url = f"{products_url}{category['url'].split('/')[-1]}"
                    print(f"Fetching products {params['_from']} to {params['_to']}...")

                    result = session.get(url,params=params)
                    
                    if 200<=result.status_code<300:                        
                        content = result.json()
                        if not content:
                            break
                        products.extend(content)
                        time.sleep(0.6)
                        offset+=1
                    else:
                        print(f"Error {result.status_code}, retrying after delay...")
                        time.sleep(2)
                category['productos'] = products
                print(f"Total products fetched for category '{category['categoria']}': {len(products)}")                
                time.sleep(1)

            df = get_dataframe(data=data)
            
            # Save the fetched data to a JSON file
            file_path = os.path.join(path,f"{key_words}.xlsx")
            df.to_excel(file_path, index=False)
            print(f"Data saved to {file_path}")

            now = datetime.now().strftime(format)
            return [{
                "tmp_path":file_path,
                "updated_to":now,
                "download_url":'-',
            }]

        except Exception as e:
            print(f"An error ocurred: {e}")
            traceback.print_exc()
            return []

Executor_D_BO_000000543 = D_BO_000000543
Robot = D_BO_000000543
