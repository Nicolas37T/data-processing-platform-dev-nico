import os
import shutil
import re
import json
import pandas as pd
from typing import Any, Dict, List, Optional
from datetime import datetime
from playwright.sync_api import sync_playwright
from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import format_date, human_delay

SHOP_BASE        = "https://farmacorp.com"
JSON_LIMIT       = 250

def _http_get_json(path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Performs an HTTP GET request using Playwright and attempts to parse JSON response.
    Returns None if request fails or JSON parsing fails.
    """
    print(f"[HTTP] Requesting: {path} | params={params}")

    with sync_playwright() as p:
        req = p.request.new_context(
            extra_http_headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        )

        try:
            r = req.get(path, timeout=30_000, params=params)
        except Exception as e:
            print(f"[HTTP ERROR] Request failed: {e}")
            return None

        if not r.ok:
            print(f"[HTTP ERROR] Status not OK: {r.status}")
            return None

        try:
            return r.json()
        except Exception:
            try:
                return json.loads(r.text())
            except Exception:
                print("[PARSE ERROR] Failed to parse JSON")
                return None

class D_BO_000000559(Download_Base):

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
        
        print("[START] check_new_data")

        updated_to_dt = format_date(updated_to, format=format)
        if updated_to_dt.date() >= datetime.now().date():
            print("[INFO] Data already up to date")
            return []

        # Prepare temp directory
        path = os.path.join(path, 'tmp')
        if os.path.exists(path):
            print("[INFO] Cleaning temp directory")
            shutil.rmtree(path)
        os.makedirs(path)

        scrape_date = datetime.now().strftime(format)

        all_items: List[Dict[str, Any]] = []

        # -------------------------
        # STEP 1: Fetch all products
        # -------------------------
        print("[STEP] Fetching products")

        page = 1
        while True:
            data = _http_get_json(f"{SHOP_BASE}/products.json", {"limit": JSON_LIMIT, "page": page})

            if data is None:
                print(f"[WARNING] No data returned for page {page}")
                break

            products = data.get("products", [])
            if not products:
                print(f"[INFO] No more products at page {page}")
                break

            print(f"[INFO] Page {page}: {len(products)} products")

            all_items.extend(products)
            page += 1
            human_delay()

        # -------------------------
        # STEP 2: Normalize data
        # -------------------------
        print("[STEP] Normalizing data")

        rows = []

        for p in all_items:
            pid = p.get("id") or p.get("handle")

            # Clean HTML description
            body_html = p.get("body_html")
            if body_html:
                txt = re.sub(r"<br\s*/?>", "\n", body_html, flags=re.I)
                txt = re.sub(r"<.*?>", " ", txt)
                txt = re.sub(r"\s+", " ", txt).strip()
            else:
                txt = None

            # Extract price
            variants = p.get("variants", [])
            prices = []

            for vr in variants:
                val = vr.get("price")
                if val is None:
                    continue

                try:
                    val_str = str(val).strip()

                    # Case 1: already has decimal separator
                    if "." in val_str or "," in val_str:
                        val_str = val_str.replace(",", ".")
                        f = float(val_str)

                    # Case 2: no separator → assume cents
                    else:
                        f = float(val_str) / 100.0

                    prices.append(round(f, 2))

                except Exception:
                    continue

            price_val = min(prices) if prices else None

            handle = p.get("handle")

            row = {
                "fecha": scrape_date,
                "nombre": p.get("title"),
                "precio": price_val,
                "tipo_producto": p.get("product_type"),
                "descripcion": txt,
                "url": f"{SHOP_BASE}/products/{handle}" if handle else SHOP_BASE,
                "handle": handle,
                "vendor": p.get("vendor"),
                "tags": (
                    ",".join(p.get("tags"))
                    if isinstance(p.get("tags"), list)
                    else p.get("tags")
                )
            }

            rows.append(row)

        print(f"[INFO] Total unique products: {len(rows)}")

        # -------------------------
        # STEP 3: Export
        # -------------------------
        df = pd.DataFrame(rows)

        out_file = os.path.join(path, f"{key_words}.xlsx")
        df.to_excel(out_file, index=False)

        print(f"[DONE] File saved: {out_file}")

        return [{
            "tmp_path": out_file,
            "updated_to": scrape_date,
            "download_url": "-"
        }]

Executor_D_BO_000000559 = D_BO_000000559
Robot = D_BO_000000559
