"""Download robot for the ADA Bolivia poultry price bulletin."""

import re
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import format_date, text_extract

class D_BO_000000462(Download_Base):
    """Type I download robot for D_BO_000000462."""
    def get_file_url(
        self,
        main_url,
        updated_to,
        key_words=None,
        format="%Y-%m-%d",
    ):
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    context = browser.new_context(
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        )
                    )
                    page = context.new_page()
                    page.goto(main_url, wait_until="domcontentloaded")
                    download_link = page.locator(
                        "a",
                        has_text="Descargar",
                    ).first
                    href = download_link.get_attribute("href")
                    if not href:
                        return []

                    return [urljoin(main_url, href)]
                finally:
                    browser.close()

        except Exception as error:
            print(f"Could not retrieve the download URL: {error}")
            return []

    def compare_files(
        self,
        files_paths,
        updated_to,
        format="%Y-%m-%d",
    ):
        valid_files = []

        try:
            reference_date = format_date(updated_to, format)
            date_pattern = re.compile(
                r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2})\b"
            )

            for file_info in files_paths or []:
                file_path = file_info["tmp_path"]
                if not file_path.lower().endswith(".pdf"):
                    continue

                lines = text_extract(file_path)
                report_date = None

                for line in lines:
                    date_match = date_pattern.search(line)
                    if not date_match:
                        continue

                    day, month, year = date_match.groups()
                    report_date = format_date(
                        f"20{year}-{month}-{day}"
                    )
                    break

                if not report_date or report_date <= reference_date:
                    continue

                file_info["updated_to"] = report_date.strftime(format)
                valid_files.append(file_info)

        except Exception as error:
            print(f"Could not compare downloaded files: {error}")
            return False

        return valid_files if valid_files else False