import os
import shutil
import time
import traceback
from datetime import datetime, timedelta
import pandas as pd
from playwright.sync_api import sync_playwright

from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import format_date


class D_BO_000000489(Download_Base):

    def check_new_data(self, main_url, updated_to, path, key_words, format='%Y-%m-%d'):
        """
        Extracts data from the main_url dated after update_to date.
        """
        with sync_playwright() as pl:
            updated_to = format_date(updated_to)
            today = datetime.today()
            init_date = today - timedelta(days=7)

            consultas_link_xpath = '//div[@class="field--item"]//a[contains(@href,"consultas")]'
            product_options_xpath = '//*[@id="edit-product"]//option'
            rows_xpath = '//div[@class="table-responsive"]//tbody/tr'
            pizarra_estimativos_id = "any"

            path = os.path.join(path, 'tmp')
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path, exist_ok=True)

            try:
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
                context.set_default_timeout(300000)
                page = context.new_page()
                page.goto(main_url, wait_until='domcontentloaded')

                print("Navigating to the 'consultas' page...")
                consultas_elem = page.query_selector(consultas_link_xpath)
                if consultas_elem:
                    consultas_link = consultas_elem.get_attribute('href')
                    if not consultas_link.startswith('http'):
                        consultas_link = f"https://www.cac.bcr.com.ar{consultas_link}"
                    page.goto(consultas_link, wait_until='load')
                else:
                    page.goto("https://www.cac.bcr.com.ar/es/consultas", wait_until='load')

                page.wait_for_selector('//*[@id="cms-tweaks-query-form"]//button[@data-id="edit-product"]', state='visible')

                product_options = [
                    (option.inner_text().strip(), option.get_attribute("value"))
                    for option in page.query_selector_all(product_options_xpath)
                    if "seleccione" not in option.inner_text().lower()
                ]

                print("Selecting 'Pizarra Estimativos' filter...")
                page.locator('#edit-type').select_option(pizarra_estimativos_id)
                page.wait_for_selector('//div[@class="modal fade in"]//button[@data-dismiss="modal"][1]', state='visible')
                page.locator('//div[@class="modal fade in"]//button[@data-dismiss="modal"]').first.click()

                print(f"Filling in date range from {init_date.strftime(format)} to {today.strftime(format)}...")
                page.wait_for_selector('#edit-date-start', state="visible")
                page.locator('#edit-date-start').fill(init_date.strftime(format))
                page.locator('#edit-date-end').fill(today.strftime(format))

                dataframes = []
                for product in product_options:
                    print(f"Processing product: {product[0]}...")
                    page.locator('#edit-product').select_option(product[1])
                    page.locator('#edit-submit').click()
                    time.sleep(2)

                    page.wait_for_selector('//div[@class="table-responsive"]', state='visible')

                    rows = [
                        [i.inner_text().replace('.', '').replace('$', '').strip() for i in row.query_selector_all("td")]
                        for row in page.query_selector_all(rows_xpath)
                    ]
                    if rows and len(rows[0]) >= 3:
                        df = pd.DataFrame(rows, columns=["Fecha", "Estimado", "Precio"])
                        df["Producto"] = product[0]
                        df["Fecha"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y", errors='coerce')
                        df = df.dropna(subset=["Fecha"])
                        if not df.empty:
                            dataframes.append(df)

                browser.close()

                if not dataframes:
                    print(f"There is no data after the date: {updated_to.strftime(format)}")
                    return []

                df_merged = pd.concat(dataframes, axis=0)
                df_merged = df_merged.sort_values(by="Fecha", ascending=True)

                latest_date = df_merged["Fecha"].iloc[-1]
                if latest_date <= updated_to:
                    print(f"There is no data after the date: {updated_to.strftime(format)}")
                    return []

                df_merged['Fecha'] = df_merged['Fecha'].dt.strftime(format)
                df_merged = df_merged.loc[:, ["Producto", "Fecha", "Estimado", "Precio"]]

                file_name = f"{key_words.strip() if key_words else 'precios_cac'}.xlsx"
                file_path = os.path.join(path, file_name)
                df_merged.to_excel(file_path, index=False)

                return [{
                    "tmp_path": file_path,
                    "updated_to": latest_date.strftime(format),
                    "download_url": '-',
                }]

            except Exception as e:
                print(f"An error occurred: {e}")
                traceback.print_exc()
                return []


# Compatibility alias
Executor_D_BO_000000489 = D_BO_000000489
