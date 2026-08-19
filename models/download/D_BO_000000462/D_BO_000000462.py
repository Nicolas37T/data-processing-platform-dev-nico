import re
import traceback
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import format_date, month_abr_to_number


class D_BO_000000462(Download_Base):
    """Robot for D_BO_000000462 (Boletín Precios Avícolas - ADASSCZ)."""

    def get_file_url(self, main_url, updated_to, key_words="division ciudad", format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after updated_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            key_words (str, optional): Search keywords.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """
        with sync_playwright() as pl:
            updated_to_dt = format_date(updated_to)
            try:
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch()
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36'
                )
                page = context.new_page()
                page.goto(main_url, wait_until='networkidle')

                # Find the download button by its visible label.
                download_link = page.query_selector(
                    '//a[contains(concat(" ", normalize-space(@class), " "), " mas ") and '
                    'contains(normalize-space(.), "Descargar") and @href]'
                )
                href = download_link.get_attribute('href') if download_link else None
                files_link_searched = [urljoin(main_url, href)] if href else []

                if not files_link_searched:
                    print("The searched files were not found")
                    return []

                print("Found files matching the criteria.")
                return files_link_searched

            except Exception as e:
                print(f"An error occurred: {e}")
                traceback.print_exc()
                return []
            finally:
                if 'page' in locals():
                    page.close()
                if 'browser' in locals():
                    browser.close()

    def compare_files(self, files_paths, updated_to, format='%Y-%m-%d'):
        """
        Extract the date from a list of files to compare and filter which are more recent than the updated_to date.

        Parameters:
            files_paths (list): List of dictionaries containing information about files.
            updated_to (str): The latest date for which the database contains records.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list or bool: A list of dictionaries with information about files that meet the criteria of being more recent than 'updated_to'. Returns False if no more recent files are found.
        """
        print("Comparing files...")
        files_dicts = []
        updated_to_dt = format_date(updated_to)

        for file in files_paths:
            print(f"Comparing file: {file['tmp_path']}")
            try:
                file_name = re.split(r"[/\\]", file["tmp_path"])[-1]
                date_match = re.search(
                    r"Boletin-Precios-Avicolas-(\d{1,2})([A-Za-z]{3})(\d{4})\.pdf$",
                    file_name,
                    re.IGNORECASE,
                )
                if not date_match:
                    print(f"Could not extract date pattern from filename: {file_name}")
                    continue

                day, month_abbreviation, year = date_match.groups()
                month = month_abr_to_number(month_abbreviation.upper())
                if not month:
                    print(f"Unknown month abbreviation in {file_name}")
                    continue

                file_date = datetime(int(year), month, int(day))

                if file_date > updated_to_dt:
                    update_to_formatted = file_date.strftime(format)
                    print(f"File date: {update_to_formatted}. Adding to filtered files.")
                    file["updated_to"] = update_to_formatted
                    files_dicts.append(file)
                else:
                    print("File does not meet update criteria. Skipping...")

            except Exception as error:
                print(f"Could not process file {file['tmp_path']}: {error}")
                traceback.print_exc()
                continue

        if not files_dicts:
            print(f"There are NO files after {updated_to_dt.strftime(format)}")
            return False

        return files_dicts
