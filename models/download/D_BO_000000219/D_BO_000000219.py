from models.download.Download_Base import Download_Base
import os
import re
import shutil
import traceback
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import requests
import urllib3
import xlrd

from models.download.tools.download_tools import format_date, month_to_number

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class D_BO_000000219(Download_Base):
    """Download robot (Type IV) for BCB - Cotización de Otras Monedas."""

    def get_data(self, main_url: str, path: str, updated_to: str, format: str = '%Y-%m-%d') -> str:
        """
        Download daily exchange rate Excel files from BCB for all dates after updated_to.

        Args:
            main_url (str): Base URL (e.g. https://www.bcb.gob.bo/librerias/indicadores/otras/anteriores.php).
            path (str): Base directory where the 'tmp' subdirectory is created.
            updated_to (str): Latest downloaded date in YYYY-MM-DD format.
            format (str): Date format string. Default is '%Y-%m-%d'.

        Returns:
            str: Path to the 'tmp' directory containing downloaded files, or '' if none/error.
        """
        tmp_path = os.path.join(path, 'tmp')
        if os.path.exists(tmp_path):
            shutil.rmtree(tmp_path)
        os.makedirs(tmp_path, exist_ok=True)

        try:
            updated_to_dt = format_date(updated_to)
            start_dt = updated_to_dt + timedelta(days=1)
            end_dt = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)

            if start_dt > end_dt:
                print(f"No new dates to check after {updated_to_dt.strftime(format)}.")
                return ""

            xls_base_url = urllib.parse.urljoin(main_url, "otras_imprimir2XLS.php")
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
                )
            }

            # Build list of weekdays between start_dt and end_dt inclusive
            target_dates = []
            cur = start_dt
            while cur <= end_dt:
                if cur.weekday() < 5:
                    target_dates.append(cur)
                cur += timedelta(days=1)

            if not target_dates:
                return ""

            def fetch_date(dt: datetime):
                params = {"qdd": dt.day, "qmm": dt.month, "qaa": dt.year}
                for attempt in range(3):
                    try:
                        resp = requests.get(
                            xls_base_url,
                            params=params,
                            headers=headers,
                            timeout=15,
                            verify=False,
                        )
                        if resp.status_code != 200 or not resp.content:
                            continue
                        real_dt = self.compare_files(file_bytes=resp.content)
                        if real_dt and real_dt > updated_to_dt:
                            return real_dt.strftime(format), resp.content
                        return None
                    except Exception:
                        if attempt == 2:
                            return None
                return None

            saved_dates = set()
            with ThreadPoolExecutor(max_workers=6) as executor:
                futures = [executor.submit(fetch_date, dt) for dt in target_dates]
                for future in as_completed(futures):
                    result = future.result()
                    if not result:
                        continue
                    date_str, content = result
                    if date_str in saved_dates:
                        continue
                    saved_dates.add(date_str)
                    out_file = os.path.join(tmp_path, f"{date_str}_cotizaciones.xls")
                    with open(out_file, "wb") as f:
                        f.write(content)

            if saved_dates:
                print(f"Downloaded {len(saved_dates)} daily exchange rate file(s) to {tmp_path}.")
                return tmp_path

            print(f"No new exchange rate files found after {updated_to_dt.strftime(format)}.")
            return ""

        except Exception as e:
            print(f"An error occurred in get_data: {e}")
            traceback.print_exc()
            return ""

    def compare_files(self, file_path: str = "", format: str = '%Y-%m-%d', file_bytes: bytes = None):
        """
        Extract the official publication date from the downloaded BCB XLS file.
        """
        try:
            if file_bytes is not None:
                wb = xlrd.open_workbook(file_contents=file_bytes, ignore_workbook_corruption=True)
            else:
                wb = xlrd.open_workbook(file_path, ignore_workbook_corruption=True)

            sheet = wb.sheet_by_index(0)
            re_date = r'DEL\s+(\d{1,2})\s+DE\s+([A-ZÁÉÍÓÚÑ]+)\s+DE\s+(\d{4})'

            for r in range(min(15, sheet.nrows)):
                for c in range(min(5, sheet.ncols)):
                    val = str(sheet.cell_value(r, c)).strip()
                    match = re.search(re_date, val, re.IGNORECASE)
                    if match:
                        day = int(match.group(1))
                        month_num = month_to_number(match.group(2).lower())
                        year = int(match.group(3))
                        if month_num:
                            return format_date(f"{year:04d}-{int(month_num):02d}-{day:02d}")
            return None
        except Exception:
            return None


Executor_D_BO_000000219 = D_BO_000000219
Robot = D_BO_000000219
