import traceback
import os
import asyncio
import aiohttp
import shutil
import requests
import time
import random
import pandas as pd
from operator import itemgetter
from datetime import datetime
from playwright.async_api import async_playwright
from playwright_stealth.stealth import Stealth
from models.download.Download_Base import Download_Base

async def create_session(headers, cookies_dict):
    connector = aiohttp.TCPConnector(ssl=False)
    session = aiohttp.ClientSession(
        headers=headers,
        cookies=cookies_dict,
        connector=connector
    )
    # if proxy:
    #     session._proxy = proxy
    return session

class ProxyRotator:
    def __init__(self):
        self.username = "msgkruim-rotate"
        self.password = "r0tcrt0fzols"
        self.host = "p.webshare.io"
        self.port = "80"

    def get_proxy(self):
        proxy_url = f"http://{self.username}:{self.password}@{self.host}:{self.port}"

        playwright_proxy = {
            "server": f"http://{self.host}:{self.port}",
            "username": self.username,
            "password": self.password
        }

        return proxy_url, playwright_proxy


def fetch_json(session:requests.Session, url:str, params:dict=None, verify:bool=False):
    retries = 5
    for _ in range(retries):
        response = session.get(url, params=params, verify=verify)
        if 200 <= response.status_code < 300:
            return response.json()['Dato']
        time.sleep(2)
    return []

async def fetch_market_products(market, products_url, categories_url, headers, cookies_dict, proxy_rotator: ProxyRotator):
    """
    Descarga productos de UN mercado. Si falla, reintenta con otro proxy.
    Mantiene el progreso de categorías ya descargadas.
    """
    max_proxy_retries = 20
    
    for proxy_attempt in range(max_proxy_retries):
        print(f"[{market['Descripcion']}] Attempt {proxy_attempt + 1}")
        current_proxy_url, current_proxy_config = proxy_rotator.get_proxy()
        
        # Solo actualizar cookies en el primer intento o si hubo error 403
        if proxy_attempt == 0 or 'needs_new_cookies' in market:
            print(f"[{market['Descripcion']}] Updating cookies...")
            cookies_dict = await update_cookies(proxy_config=current_proxy_config)
            if 'needs_new_cookies' in market:
                del market['needs_new_cookies']
        
        session = await create_session(headers=headers, cookies_dict=cookies_dict)
        
        try:
            # ============== FETCH CATEGORIES (solo si no existen) ==============
            if 'Categorias' not in market:
                categories_params = {
                    "IdMarket": market['IdMarket'],
                    "IdSucursal": market['IdSucursal'],
                }
                print(f"[{market['Descripcion']}] Fetching categories...")
                
                content = []
                for retry in range(5):
                    response = await session.get(categories_url, params=categories_params, ssl=False, proxy=current_proxy_url)
                    print(f"[{market['Descripcion']}] Categories attempt {retry + 1} - Status: {response.status}")
                    
                    if 200 <= response.status < 300:
                        content = await response.json()
                        content = content.get('Dato', [])
                        print(f"[{market['Descripcion']}] Categories fetched: {len(content)} entries")
                        break
                    elif response.status == 403:
                        print(f"[{market['Descripcion']}] 403 on categories - will retry with new proxy")
                        market['needs_new_cookies'] = True
                        await session.close()
                        await asyncio.sleep(5)
                        raise Exception("403 Forbidden - need new proxy")
                    
                    await asyncio.sleep(2)
                
                if not content:
                    print(f"[{market['Descripcion']}] Failed to retrieve categories")
                    await session.close()
                    continue
                
                # Flatten categories
                categories = []
                for item in content:
                    cat = [{"IdCategoria": i['IdCategoria'], "Descripcion": i['Descripcion']} for i in item['Categorias']]
                    categories.extend(cat)
                
                market['Categorias'] = categories
                print(f"[{market['Descripcion']}] Total categories: {len(categories)}")
            
            # ============== FETCH PRODUCTS FOR EACH CATEGORY ==============
            for cat in market['Categorias']:
                # Continuar desde donde se quedó (NO saltar si tiene productos parciales)
                page = cat.get('last_page', 0)
                products = cat.get('Productos', [])
                
                # Solo saltar si está marcada como COMPLETAMENTE descargada
                if cat.get('completed', False):
                    print(f"[{market['Descripcion']}] Category '{cat['Descripcion']}' already completed ({len(products)} products), skipping")
                    continue
                
                print(f"[{market['Descripcion']}] Fetching products for '{cat['Descripcion']}' (starting at page {page}, {len(products)} products so far)")
                
                while True:
                    products_params = {
                        "IdMarket": market['IdMarket'],
                        "IdLocatario": market['IdSucursal'],
                        "IdCategoria": cat['IdCategoria'],
                        "Pagina": page,
                        "Cantidad": 100,
                    }
                    
                    try:
                        products_response = await session.get(products_url, params=products_params, ssl=False, proxy=current_proxy_url)
                        print(f"[{market['Descripcion']}] Page {page} for '{cat['Descripcion']}' - Status: {products_response.status}")
                        
                        if 200 <= products_response.status < 300:
                            products_content = await products_response.json()
                            products_content = products_content.get('Dato', [])
                            
                            if not products_content:
                                # Marca como completada cuando no hay más productos
                                cat['completed'] = True
                                break
                            
                            products.extend(products_content)
                            print(f"  Retrieved {len(products_content)} products from page {page} (total: {len(products)})")
                            page += 1
                            cat['last_page'] = page  # Guardar progreso
                            await asyncio.sleep(2)
                        
                        elif products_response.status == 403:
                            print(f"[{market['Descripcion']}] 403 FORBIDDEN - Saving progress and changing proxy")
                            cat['Productos'] = products  # Guardar lo descargado hasta ahora
                            cat['last_page'] = page
                            market['needs_new_cookies'] = True
                            await session.close()
                            await asyncio.sleep(5)
                            raise Exception("403 Forbidden - need new proxy")
                        
                        else:
                            print(f"[{market['Descripcion']}] Unexpected status {products_response.status}, retrying...")
                            await asyncio.sleep(5)
                    
                    except aiohttp.ContentTypeError as e:
                        text = await products_response.text()
                        print(f"[{market['Descripcion']}] Response was not JSON! Status: {products_response.status}")
                        print(f"Response preview: {text[:200]}")
                        cat['Productos'] = products  # Guardar progreso
                        cat['last_page'] = page
                        market['needs_new_cookies'] = True
                        await session.close()
                        raise Exception("ContentTypeError - need new proxy")
                
                # Guardar productos finales de la categoría
                cat['Productos'] = products
                
                # Limpiar metadata temporal
                if 'last_page' in cat:
                    del cat['last_page']
                
                print(f"[{market['Descripcion']}] Total products for '{cat['Descripcion']}': {len(products)}")
            
            # ============== SUCCESS ==============
            print(f"[{market['Descripcion']}] ✓ Downloaded successfully!")
            await session.close()
            return  # Salir exitosamente
        
        except Exception as e:
            print(f"[{market['Descripcion']}] Error with proxy: {e}")
            await session.close()
            await asyncio.sleep(3)
            continue
    
    print(f"[{market['Descripcion']}] ✗ Failed after {max_proxy_retries} proxy attempts")


async def fetch_all_markets_products(data, products_url, categories_url, headers, cookies_dict, proxy_rotator):
    """
    Procesa todos los mercados en lotes.
    """
    print("Starting async session to fetch markets' products and categories...")
    
    # Procesar mercados de UNO EN UNO para evitar sobrecargar
    # Si quieres lotes, usa BATCH_SIZE = 3 (no más de 5)
    for i, market in enumerate(data):
        print(f"\n{'='*60}")
        print(f"Processing market {i+1}/{len(data)}: {market['Descripcion']}")
        print(f"{'='*60}\n")
        
        await fetch_market_products(
            market=market,
            products_url=products_url,
            categories_url=categories_url,
            headers=headers,
            cookies_dict=cookies_dict,
            proxy_rotator=proxy_rotator
        )
        
        # Pausa entre mercados
        await asyncio.sleep(5)
    
    print("\n✓ All market data fetched.")
    return data
    
def get_dataframe(data:dict) -> pd.DataFrame:
    rows  = []
    for market in data:
        market_meta = {f'Market.{k}':v for k,v in  market.items() if k != 'Categorias'}
        if 'Categorias' not in market:
            print(f"WARNING: Market '{market.get('Descripcion', 'Unknown')}' has no categories")
            continue     
        for cat in market['Categorias']:
            cat_meta = {f'Categoria.{k}':v for k,v in  cat.items() if k != 'Productos'}

            if 'Productos' not in cat:
                print(f"WARNING: Category '{cat.get('Descripcion', 'Unknown')}' in market '{market.get('Descripcion', 'Unknown')}' has no products")
                continue

            for product in cat['Productos']:
                row = {}
                row.update(product)
                row.update(cat_meta)
                row.update(market_meta)
                rows.append(row)        
    
    return pd.DataFrame(rows)

async def update_cookies(
    proxy_config=None,
    main_url: str = 'https://www.hipermaxi.com/santa-cruz/farmacia-roca-y-coronado'
):
    print("Updating session cookies...")

    async with async_playwright() as pl:
        browser = None
        page = None

        try:
            print(f"Launching browser and navigating to {main_url} ...")

            browser = await pl.chromium.launch(
                headless=False,
                # proxy=proxy_config,
                args=["--disable-blink-features=AutomationControlled"]
            )

            context = await browser.new_context(
                user_agent=(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/89.0.4389.82 Safari/537.36'
                ),
                ignore_https_errors=True
            )

            context.set_default_timeout(300_000)

            page = await context.new_page()

            stealth = Stealth()
            await stealth.apply_stealth_async(page)

            # Navegar y esperar
            await page.goto(main_url, wait_until='load')
            await page.wait_for_timeout(30 * 1000)

            # Obtener cookies
            cookies = await context.cookies()
            cookie_dict = {c['name']: c['value'] for c in cookies}
            print(cookie_dict)
            return cookie_dict

        except Exception as e:
            print(f"Error trying to get cookies: {e}")
            traceback.print_exc()
            return {}

        finally:
            if page:
                await page.close()
            if browser:
                await browser.close()

class D_BO_000000544(Download_Base):

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

        # Define API Endpoints
        markets_url = 'https://hipermaxi.com/tienda-api/api/v1/public/markets/activos?IdMarket=0&IdTipoServicio=0'
        categories_url = 'https://hipermaxi.com/tienda-api/api/v1/markets/clasificaciones'
        products_url = 'https://hipermaxi.com/tienda-api/api/v1/public/productos'
        try:
            # Initialize requests session with headers
            print("Initializing session and setting headers...")            
            headers = self.headers
            headers["Referer"] = "https://www.hipermaxi.com/"

            session = requests.Session()
            session.headers.update(headers)

            proxy_rotator = ProxyRotator()
            current_proxy_url, current_proxy_config = proxy_rotator.get_proxy()
            cookies_dict = asyncio.run(update_cookies(proxy_config=current_proxy_config, main_url=main_url))

            session.cookies.update(cookies_dict)   

            # Fetch markets data
            print(f"Fetching market data from {markets_url}...")
            markets_content = fetch_json(session=session,url=markets_url)
            if not markets_content:
                raise Exception(f"Error fetching from {markets_url}")        
            
            # Extract location info
            data = []
            for market in markets_content:
                getter = itemgetter('IdMarket', 'IdSucursal', 'Descripcion', 'Direccion')
                markets = [dict(zip(['IdMarket', 'IdSucursal', 'Descripcion', 'Direccion'], getter(item)))
                        for item in market['Locatarios']]
                data.extend(markets)
            
            # Step 8: Fetch product and category data for each market
            print("Fetching products and categories for each market...")
            data = asyncio.run(fetch_all_markets_products(data=data,products_url=products_url,categories_url=categories_url,headers=headers,cookies_dict=cookies_dict,proxy_rotator=proxy_rotator))

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

Executor_D_BO_000000544 = D_BO_000000544
Robot = D_BO_000000544
