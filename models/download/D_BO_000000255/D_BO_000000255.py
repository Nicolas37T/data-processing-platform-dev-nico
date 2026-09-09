import os
import shutil
import traceback
import re
from typing import List, Dict

import pandas as pd
from playwright.sync_api import sync_playwright

from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import format_date


class D_BO_000000255(Download_Base):
    """
    Type III Download Robot for adascz.com.bo.
    Responsible for scraping reference prices, building an exact visual replica
    of the web table, and returning metadata following DATAX architecture rules.
    """

    def check_new_data(
        self, 
        main_url: str, 
        updated_to: str, 
        path: str, 
        key_words: str, 
        format: str = '%Y-%m-%d'
    ) -> List[Dict]:
        
        try:
            # 1. STATELESS ENFORCEMENT
            tmp_dir = os.path.join(path, 'tmp')
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir)
            os.makedirs(tmp_dir)

            extracted_date_str = ""
            
            # 2. PLAYWRIGHT NAVIGATION & DATA EXTRACTION
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True) 
                context = browser.new_context()
                page = context.new_page()
                
                page.goto(main_url, wait_until='domcontentloaded')
                page.wait_for_selector('div.tit-precios', timeout=10000)

                # Extract the full title box (Green Box)
                title_box = page.locator('div.tit-precios').inner_text().strip().replace('\n', ' ')
                
                # Date extraction for idempotency
                match = re.search(r'(\d{2}-\d{2}-\d{4})', title_box)
                if match:
                    raw_date = match.group(1)
                    day, month, year = raw_date.split('-')
                    extracted_date_str = f"{year}-{month}-{day}"
                else:
                    extracted_date_str = pd.Timestamp.now().strftime(format)

                # 3. IDEMPOTENCY CHECK
                if extracted_date_str <= updated_to:
                    browser.close()
                    return []

                # 4. RAW DATA GRID EXTRACTION (Visual Replica)
                rows = page.locator('table tr')

                # Pollo (Row 0)
                pollo_h = rows.nth(0).locator('th, td').nth(0).inner_text().strip().replace('\n', ' ')
                pollo_v = rows.nth(0).locator('th, td').nth(1).inner_text().strip().replace('\n', ' ')

                # Gallina (Row 1)
                gallina_h = rows.nth(1).locator('th, td').nth(0).inner_text().strip().replace('\n', ' ')
                gallina_v = rows.nth(1).locator('th, td').nth(1).inner_text().strip().replace('\n', ' ')

                # Huevo (Row 2 & 3)
                huevo_h = rows.nth(2).locator('th, td').nth(0).inner_text().strip().replace('\n', ' ')
                huevo_sub_h = [h.strip() for h in rows.nth(2).locator('td').all_inner_texts()]
                huevo_vals = [v.strip() for v in rows.nth(3).locator('td').all_inner_texts()]

                browser.close()

            # 5. DATASET CONSTRUCTION (2D Matrix matching the HTML Table)
            grid = [
                [title_box, "", "", "", "", ""],
                [pollo_h, pollo_v, "", "", "", ""],
                [gallina_h, gallina_v, "", "", "", ""],
                [huevo_h] + huevo_sub_h,
                [""] + huevo_vals
            ]
            
            df_raw = pd.DataFrame(grid)
            
            # Save raw dataset as an Excel file (.xlsx) to preserve grid structure perfectly
            file_name = f"{key_words}_{extracted_date_str.replace('-', '')}.xlsx"
            tmp_path = os.path.join(tmp_dir, file_name)
            
            # Write to Excel without headers or index
            df_raw.to_excel(tmp_path, index=False, header=False)

            # 6. XCOM RULE
            return [{
                "tmp_path": tmp_path,
                "updated_to": extracted_date_str,
                "download_url": "-" 
            }]

        except Exception:
            traceback.print_exc()
            return []