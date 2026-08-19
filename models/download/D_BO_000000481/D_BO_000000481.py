import os
import re
import traceback
from playwright.sync_api import sync_playwright

from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import format_date, text_extract


class D_BO_000000481(Download_Base):
    """Robot for D_BO_000000481 (Boletin Diario, Bolsa Boliviana de Valores)."""

    def get_file_url(self, main_url, updated_to, format='%Y-%m-%d'):
        """Extracts download URLs for files dated after updated_to date."""
        with sync_playwright() as pl:
            updated_to_dt = format_date(updated_to)
            file_urls = []

            try:
                print(f"Launching browser and navigating to {main_url} ...")
                file_urls.append(main_url)

                if not file_urls:
                    print(f"There are NO files after {updated_to_dt.strftime(format)}")
                    return []

                return file_urls

            except Exception as e:
                print(f"An error occurred: {e}")
                traceback.print_exc()
                return []

    def compare_files(self, files_paths, updated_to, format='%Y-%m-%d'):
        """Inspect downloaded files and keep only those newer than updated_to."""
        print("Comparing files...")
        files_dicts = []
        updated_to_dt = format_date(updated_to)
        re_date = r"\b(\d{1,2}/\d{1,2}/\d{4})"

        for file in files_paths:
            print(f"Comparing file: {file['tmp_path']}")
            try:
                print("Extracting date from the file...")
                lines = text_extract(file["tmp_path"])
                dates = [re.search(re_date, line) for line in lines if re.search(re_date, line)]

                if not dates:
                    print("Could not find date inside the file.")
                    continue

                date_str = dates[0].group(1)
                date_formatted = format_date(date_str, "%d/%m/%Y")

                if date_formatted > updated_to_dt:
                    print(f"File date: {date_formatted.strftime(format)}. Adding to filtered files.")
                    file["updated_to"] = date_formatted.strftime(format)
                    files_dicts.append(file)
                else:
                    print("File does not meet update criteria. Skipping...")

            except Exception as error:
                print(f"Could not extract date from {file['tmp_path']}: {error}")
                continue

        if not files_dicts:
            print(f"There are NO files after {updated_to_dt.strftime(format)}")
            return False

        return files_dicts
