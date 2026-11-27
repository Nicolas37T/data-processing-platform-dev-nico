from models.download.Download_Base import Download_Base
import traceback
import re
import os
import shutil
from playwright.sync_api import sync_playwright
from datetime import datetime
from models.download.tools.download_tools import format_date, text_extract, month_to_number, month_abr_to_number


class D_BO_000000501(Download_Base):

    def verify_download(self, main_url, updated_to, path, format='%Y-%m-%d'):
        """
        Navigates to the OAP daily bulletin page, scrapes downloadable PDF links,
        and saves them into the temporary path.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            path (str): The directory path where the downloaded files will be saved.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list: A list of dicts [{'tmp_path': ..., 'download_url': ...}]
        """
        with sync_playwright() as pl:
            updated_to = format_date(updated_to)

            path = os.path.join(path, 'tmp')
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path, exist_ok=True)

            file_paths = []
            browser = None
            try:
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
                    ignore_https_errors=True
                )
                page = context.new_page()
                page.goto(main_url, wait_until='domcontentloaded', timeout=60000)

                # Wait for download links to be present
                page.wait_for_selector('a[href*=".pdf"]', state='attached', timeout=30000)

                # Extract all PDF links on the page
                links = page.query_selector_all('a[href*=".pdf"]')
                pdf_urls = []
                for link in links:
                    href = link.get_attribute('href')
                    if href and href.lower().endswith('.pdf') and href not in pdf_urls:
                        pdf_urls.append(href)

                print(f"Found {len(pdf_urls)} PDF links on the page.")

                # Download PDFs
                for idx, pdf_url in enumerate(pdf_urls):
                    try:
                        # Extract date hint from filename if present (e.g. BOLETIN_DIARIO_YYYY-MM-DD.pdf)
                        date_in_name = re.search(r'(\d{4}-\d{2}-\d{2})', pdf_url)
                        if date_in_name:
                            file_date = format_date(date_in_name.group(1))
                            if file_date <= updated_to:
                                print(f"Skipping {pdf_url} (date {file_date.strftime(format)} <= {updated_to.strftime(format)})")
                                continue

                        filename = os.path.basename(pdf_url)
                        if not filename:
                            filename = f"boletin_diario_{idx}.pdf"

                        file_save_path = os.path.join(path, filename)
                        print(f"Downloading: {pdf_url} -> {file_save_path}")

                        response = context.request.get(pdf_url, ignore_https_errors=True, timeout=60000)
                        if response.ok:
                            with open(file_save_path, 'wb') as f:
                                f.write(response.body())
                            file_paths.append({
                                'tmp_path': file_save_path,
                                'download_url': pdf_url
                            })
                    except Exception as e:
                        print(f"Error downloading {pdf_url}: {e}")
                        continue

                return file_paths

            except Exception as e:
                print(f"An error occurred in verify_download: {e}")
                traceback.print_exc()
                return []
            finally:
                if browser:
                    browser.close()

    def compare_files(self, files_paths, updated_to, format='%Y-%m-%d'):
        """
        Inspects downloaded PDF files, extracts the bulletin date from filename or text,
        and filters files that are newer than updated_to.

        Parameters:
            files_paths (list): List of dicts [{'tmp_path': ..., 'download_url': ...}]
            updated_to (str): The latest date for which the database contains records.
            format (str): Date format string.

        Returns:
            list: List of dicts [{'tmp_path': ..., 'updated_to': ..., 'download_url': ...}]
        """
        updated_to = format_date(updated_to)
        files_dicts = []

        re_date_filename = r'(\d{4}-\d{2}-\d{2})'
        re_date_slash = r'(\d{1,2})/(\d{1,2})/(\d{4})'
        re_date_text = r"(\d{1,2})\D*((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre))\D*(\d{4})"

        for file_info in files_paths:
            tmp_path = file_info.get('tmp_path')
            download_url = file_info.get('download_url')

            if not tmp_path or not os.path.exists(tmp_path):
                continue

            file_date = None

            # 1. Try date from filename / URL
            match_name = re.search(re_date_filename, os.path.basename(tmp_path)) or re.search(re_date_filename, download_url or '')
            if match_name:
                try:
                    file_date = format_date(match_name.group(1))
                except Exception:
                    file_date = None

            # 2. Try date from text inside the PDF if not found in filename
            if not file_date:
                try:
                    lines = text_extract(tmp_path)
                    for line in lines:
                        m_slash = re.search(re_date_slash, line)
                        if m_slash:
                            d, m, y = m_slash.groups()
                            file_date = format_date(f"{y}-{int(m):02d}-{int(d):02d}")
                            break
                        m_text = re.search(re_date_text, line, re.IGNORECASE)
                        if m_text:
                            d, m_str, y = m_text.groups()
                            m_num = month_to_number(m_str) or month_abr_to_number(m_str)
                            if m_num:
                                file_date = format_date(f"{y}-{m_num:02d}-{int(d):02d}")
                                break
                except Exception as e:
                    print(f"Error extracting text from {tmp_path}: {e}")

            if not file_date:
                print(f"Could not determine date for {tmp_path}. Skipping...")
                continue

            if file_date > updated_to:
                print(f"File {os.path.basename(tmp_path)} date ({file_date.strftime(format)}) > updated_to ({updated_to.strftime(format)}). Accepted.")
                files_dicts.append({
                    'tmp_path': tmp_path,
                    'updated_to': file_date.strftime(format),
                    'download_url': download_url or '-'
                })
            else:
                print(f"File {os.path.basename(tmp_path)} date ({file_date.strftime(format)}) <= updated_to ({updated_to.strftime(format)}). Skipping...")

        return files_dicts


Executor_D_BO_000000501 = D_BO_000000501
Robot = D_BO_000000501
