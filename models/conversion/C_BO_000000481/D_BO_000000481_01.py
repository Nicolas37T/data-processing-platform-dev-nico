"""Robot for D_BO_000000481_01 (Fondos de Inversion - Cartera Participantes
y Tasas de Rendimiento, Bolsa Boliviana de Valores).

The source is the same "Boletin Diario" PDF used by D_BO_000000481. The
target table starts on ``page_number`` and continues onto the following
pages as long as they keep repeating the report title (this report spans
pages 2 and 3).
"""
import os
import re
import traceback
from datetime import datetime

import pandas as pd
import pdfplumber

from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import (
    get_col_date,
    get_pdf_report_page,
    search_key_words,
    to_numeric_datax,
)


class D_BO_000000481_01(Conversion_Base):
    """Robot for D_BO_000000481_01 (Cartera Participantes y Tasas de Rendimiento, BBV)."""

    def extraction(self, file_path, key_words, template_path, page_number, format='%Y-%m-%d'):
        """
        Extract the "Fondos de Inversion" hierarchical table and normalize it.

        Only PDF files are supported. The table is located using ``key_words``
        (matched against the page/row text) starting from ``page_number``, and
        continues onto the following pages as long as they still contain the
        same report title (multi-page reports repeat it on every page).

        Args:
            file_path (str): Absolute path of the source file.
            key_words (str): Keywords identifying the report title/table.
            template_path (str): Reserved for future template comparison; unused.
            page_number (int): Page where the search for the table starts.
            format (str, optional): Expected date format. Defaults to '%Y-%m-%d'.

        Returns:
            tuple[dict, pd.DataFrame] | str: ``(metadata, dataframe)`` on success,
            where ``metadata`` has ``file_name``, ``titles`` (title lines plus
            the "al DDMMMYYYY" report date line) and ``page_number`` (the page
            where the table starts), and ``dataframe`` has columns
            ``[nv1, nv2, nv3, nv4, nv5, nv6, nv7, nv8, fecha, valor]``:
            nv1 fund type root, nv2 category (Abierto/Cerrado), nv3 currency
            sub-group, nv4 fund code (or "Total"/"Tasa Promedio Ponderada"),
            nv5 fund name, nv6 SAFI, nv7 risk rating, nv8 metric name.
            Returns an empty string ``""`` on failure.
        """
        try:
            fondos_root_label = 'Fondo de Inversión'
            fondos_summary_labels = {'total', 'tasa promedio ponderada'}
            fondos_columns = ['nv1', 'nv2', 'nv3', 'nv4', 'nv5', 'nv6', 'nv7', 'nv8', 'fecha', 'valor']
            fondos_metric_order = [
                'Cartera', 'Cuota', 'Part', 'TR 30 días', 'TR 90 días',
                'TR 180 días', 'TR 360 días', 'Com Fija', 'Com Éxito',
            ]
            fondos_date_line_pattern = re.compile(r'\bal\s+\d{1,2}[A-Za-zÀ-ÿ]{3,4}\d{4}\b', re.IGNORECASE)

            def clean_cell(value):
                if value is None:
                    return None
                value = re.sub(r'\s+', ' ', str(value)).strip()
                return value or None

            extension = os.path.splitext(file_path)[1].lower()
            if extension != '.pdf':
                raise ValueError(f"Unsupported file extension: {extension}")

            with pdfplumber.open(file_path) as pdf:
                start_page = get_pdf_report_page(pdf, key_words, num_caracteres='ALL', page_number=page_number)
                found_page = start_page.page_number - 1

                all_titles = []
                all_rows = []
                date_text = None
                page_index = found_page

                while page_index < len(pdf.pages):
                    page = pdf.pages[page_index]
                    page_text = page.extract_text() or ''
                    if not search_key_words(text=page_text, key_words=key_words):
                        break

                    if not date_text:
                        match = fondos_date_line_pattern.search(page_text)
                        if match:
                            date_text = match.group(0)

                    tables = page.extract_tables()
                    if not tables:
                        break

                    page_rows = max(tables, key=len)
                    rows = [
                        row for row in page_rows
                        if not fondos_date_line_pattern.search(clean_cell(row[0]) or '')
                    ]

                    pivot_index = None
                    for i, row in enumerate(rows):
                        row_text = ' '.join(str(cell) for cell in row if cell)
                        if search_key_words(text=row_text, key_words=key_words):
                            pivot_index = i
                            break

                    if pivot_index is None:
                        page_index += 1
                        continue

                    titles = [
                        clean_cell(row[0])
                        for row in rows[:pivot_index + 1]
                        if clean_cell(row[0])
                    ]
                    data_rows = rows[pivot_index + 1:]

                    if not all_titles:
                        all_titles = titles + ([date_text] if date_text else [])

                    all_rows.extend(data_rows)
                    page_index += 1

            if not all_rows:
                raise ValueError('The report table could not be found in the file.')

            if not date_text:
                fecha = '-'
            else:
                parsed = get_col_date(date_text)
                try:
                    fecha = datetime.strptime(parsed, '%Y-%m-%d').strftime(format)
                except (ValueError, TypeError):
                    fecha = '-'

            records = []
            nv1 = None
            nv2 = None
            nv3 = None
            headers = None

            for row in all_rows:
                cells = [clean_cell(cell) for cell in row]
                label = cells[0]
                if label is None:
                    continue

                rest = cells[1:]

                if not any(rest):
                    if label == fondos_root_label:
                        nv1 = label
                    else:
                        nv2 = label
                    continue

                if label.lower() in fondos_summary_labels:
                    nv4, nv5, nv6, nv7 = label, None, None, None
                elif cells[1] is None:
                    nv3 = label
                    headers = cells[2:]
                    continue
                else:
                    nv4, nv5, nv6, nv7 = label, cells[1], cells[2], cells[3]

                if headers is None:
                    continue

                metric_headers = headers[2:]
                metric_values = cells[4:]
                for metric_name, value in zip(metric_headers, metric_values):
                    if not metric_name or value is None:
                        continue
                    records.append({
                        'nv1': nv1,
                        'nv2': nv2,
                        'nv3': nv3,
                        'nv4': nv4,
                        'nv5': nv5,
                        'nv6': nv6,
                        'nv7': nv7,
                        'nv8': metric_name,
                        'fecha': fecha,
                        'valor': value,
                    })

            dataframe = pd.DataFrame.from_records(records, columns=fondos_columns)
            nv8_rank = pd.Categorical(dataframe['nv8'], categories=fondos_metric_order, ordered=True)
            dataframe = (
                dataframe.assign(_nv8_rank=nv8_rank)
                .sort_values(by='_nv8_rank', kind='stable')
                .drop(columns='_nv8_rank')
                .reset_index(drop=True)
            )

            metadata = {
                'file_name': os.path.basename(file_path),
                'titles': all_titles,
                'page_number': found_page + 1,
            }
            return metadata, dataframe

        except Exception as error:
            print(f"Could not extract report from {file_path}: {error}")
            traceback.print_exc()
            return ""

    def validate_data_results(self, dataframe, decimal_separator, TOLERANCE=6.0):
        """
        Validate extracted values against the printed "Total" rows.

        Rows labeled "Tasa Promedio Ponderada" are weighted averages, not sums,
        and are excluded from the comparison instead of being (incorrectly)
        validated as plain totals.

        Args:
            dataframe (pd.DataFrame): Normalized data, as enriched by
                ``insert_metadata`` (must include the ``nv1``..``nv8`` and
                ``valor`` columns).
            decimal_separator (str): Decimal separator used in ``valor`` ('.' or ',').
            TOLERANCE (float, optional): Acceptable difference between the
                computed and printed totals. Defaults to 6.0.

        Returns:
            bool: True if a total is off by more than ``TOLERANCE`` (or the
            validation itself failed), False if every total matches or there
            were no totals to compare.
        """
        try:
            fondos_summary_labels = {'total', 'tasa promedio ponderada'}

            working_df = dataframe.copy()
            working_df['valor'] = to_numeric_datax(working_df['valor'], decimal_separator)

            nv4_key = working_df['nv4'].astype(str).str.strip().str.lower()
            total_rows = working_df[nv4_key == 'total']

            if total_rows.empty:
                return False

            group_columns = ['nv1', 'nv2', 'nv3', 'nv8']
            data_rows = working_df[~nv4_key.isin(fondos_summary_labels)]

            for _, total_row in total_rows.iterrows():
                printed_total = total_row['valor']
                if pd.isna(printed_total):
                    continue

                mask = (data_rows[group_columns] == total_row[group_columns]).all(axis=1)
                computed_total = data_rows.loc[mask, 'valor'].sum()

                if abs(computed_total - printed_total) > TOLERANCE:
                    print(
                        f"Total mismatch for {total_row[group_columns].to_dict()}: "
                        f"computed={computed_total}, printed={printed_total}"
                    )
                    return True

            return False

        except Exception as error:
            print(f"Could not validate data results: {error}")
            traceback.print_exc()
            return True


Robot = D_BO_000000481_01

