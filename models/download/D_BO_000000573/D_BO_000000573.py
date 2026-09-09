import os
import re
from datetime import datetime
from urllib.parse import urljoin

import pandas as pd
from playwright.sync_api import sync_playwright

from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import format_date, get_date


class D_BO_000000573(Download_Base):
    def get_file_url(self, main_url, updated_to, key_words=None,
                     format='%Y-%m-%d'):
        """Return download URLs for publications newer than ``updated_to``."""
        reference_date = format_date(updated_to, format)

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(main_url, wait_until='networkidle')
                api_root = urljoin(
                    main_url, '/wp-json/cndc/v1/estadisticas/')
                categories = page.request.get(
                    api_root + 'categorias?tipo=diaria').json()
                category = next(
                    (item for item in categories.get('categorias', [])
                     if item.get('nombre', '').strip().lower()
                     == 'inyecciones y retiros cm'),
                    None)
                if not category:
                    return []

                documents = page.request.get(
                    api_root + f"documentos?categoria_id={category['term_id']}"
                    '&agrupado=true').json()
                candidates = []
                keywords = key_words.split() if isinstance(
                    key_words, str) else (key_words or [])
                for group in documents.get('grupos', []):
                    for document in group.get('docs', []):
                        title = document.get('titulo', '')
                        filename = document.get('archivo_nom', '')
                        searchable_text = f'{title} {filename}'.lower()
                        if keywords and not all(
                                keyword.lower() in searchable_text
                                for keyword in keywords):
                            continue
                        document_date = datetime.strptime(
                            document['fecha'], '%Y-%m-%d')
                        if document_date > reference_date:
                            candidates.append((
                                document_date,
                                document['archivo_url']))

                browser.close()
        except Exception as error:
            print(f'Could not retrieve file URLs: {error}')
            return []

        return [url for _, url in candidates]

    def compare_files(self, files_paths, updated_to, format='%Y-%m-%d'):
        """Keep downloaded files whose internal date is newer than a reference."""
        reference_date = format_date(updated_to, format)
        verified_files = []

        def parse_excel_date(value):
            if not isinstance(value, str):
                return None

            value = value.strip()
            if not value:
                return None

            month_map = {
                'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
                'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
                'septiembre': 9, 'setiembre': 9, 'octubre': 10,
                'noviembre': 11, 'diciembre': 12,
            }

            iso_match = re.search(
                r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b', value)
            if iso_match:
                return datetime.strptime(
                    iso_match.group(0).replace('/', '-'), '%Y-%m-%d')

            spanish_match = re.search(
                r'(?:\b\w+\s*,\s*)?(?P<day>\d{1,2})\s+de\s+'
                r'(?P<month>enero|febrero|marzo|abril|mayo|junio|julio|'
                r'agosto|septiembre|setiembre|octubre|noviembre|diciembre)'
                r'\s+de\s+(?P<year>\d{4})', value, re.IGNORECASE)
            if spanish_match:
                month = month_map.get(spanish_match.group('month').lower())
                if month is None:
                    return None
                return datetime(
                    int(spanish_match.group('year')),
                    month,
                    int(spanish_match.group('day')),
                )

            day_month_year_match = re.search(
                r'\b(?P<day>\d{1,2})[-/](?P<month>\d{1,2})[-/]'
                r'(?P<year>\d{4})\b', value)
            if day_month_year_match:
                return datetime(
                    int(day_month_year_match.group('year')),
                    int(day_month_year_match.group('month')),
                    int(day_month_year_match.group('day')),
                )

            return None

        for file_data in files_paths or []:
            file_path = file_data.get('tmp_path')
            if not file_path or not os.path.isfile(file_path):
                continue

            try:
                internal_date = None
                extension = os.path.splitext(file_path)[1].lower()
                if extension in ('.xlsx', '.xls'):
                    workbook = pd.read_excel(
                        file_path, sheet_name=0, header=None)
                    for value in workbook.iloc[:, 0].dropna():
                        if isinstance(value, (datetime, pd.Timestamp)):
                            candidate_date = value.to_pydatetime() \
                                if isinstance(value, pd.Timestamp) else value
                            internal_date = max(
                                internal_date or candidate_date, candidate_date)
                        elif isinstance(value, str):
                            candidate_date = parse_excel_date(value)
                            if candidate_date is not None:
                                internal_date = max(
                                    internal_date or candidate_date,
                                    candidate_date)

                    if internal_date is None:
                        date_parts = get_date(workbook)
                        if date_parts:
                            internal_date = datetime(
                                date_parts[1], date_parts[0], 1)
                if internal_date is None or internal_date <= reference_date:
                    continue

                result = {
                    'tmp_path': file_path,
                    'download_url': file_data.get('download_url'),
                    'updated_to': internal_date.strftime(format),
                }
                verified_files.append(result)
            except (OSError, ValueError) as error:
                print(f'Could not compare file {file_path}: {error}')

        return verified_files if verified_files else False