import os
import re
import traceback

import pandas as pd

from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import (
    get_pdf_report_page,
    get_xlsx_report_dataframe,
    search_key_words,
    to_numeric_datax,
)

class D_BO_000000568_02(Conversion_Base):
    def extraction(
        self,
        file_path: str,
        key_words: str,
        template_path: str,
        page_number: int,
        format: str = '%Y-%m-%d',
    ) -> tuple[dict, pd.DataFrame] | str:
       
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            table = None
            source_page = page_number
            document_text = ''

            if file_ext == '.xlsx':
                result = get_xlsx_report_dataframe(file_path, key_words, page_number)
                if not result:
                    raise ValueError('Report table not found in Excel file')

                workbook_df, source_page = result
                document_text = ' '.join(
                    workbook_df.astype(str).fillna('').to_numpy().flatten()
                )
                volume_rows = workbook_df.astype(str).apply(
                    lambda column: column.str.contains(
                        'volumen de operaciones', case=False, na=False
                    )
                ).any(axis=1)
                volume_index = workbook_df.index[volume_rows]
                if len(volume_index) == 0:
                    raise ValueError('Volume table not found in Excel file')

                start = volume_index[0]
                end = len(workbook_df)
                for index in range(start + 1, len(workbook_df)):
                    row_text = ' '.join(workbook_df.iloc[index].dropna().astype(str))
                    if row_text.lower().startswith('notas'):
                        end = index
                        break
                table = workbook_df.iloc[start:end].reset_index(drop=True)
            elif file_ext == '.pdf':
                import pdfplumber

                with pdfplumber.open(file_path) as pdf:
                    target_page = get_pdf_report_page(
                        pdf, key_words, page_number=page_number
                    )
                    source_page = target_page.page_number
                    document_text = target_page.extract_text() or ''
                    tables = target_page.extract_tables()
                    for candidate in tables:
                        candidate_text = ' '.join(
                            str(cell or '') for row in candidate for cell in row
                        )
                        if 'volumen de operaciones' in candidate_text.lower():
                            table = candidate
                            break

                if table is None:
                    raise ValueError('Volume table not found in PDF file')

                width = max(len(row) for row in table)
                table = pd.DataFrame(
                    [list(row) + [None] * (width - len(row)) for row in table]
                )
                title = table.iloc[1, 0] if len(table) > 1 else ''
                table = table.iloc[1:].reset_index(drop=True)
            else:
                raise ValueError(f'Unsupported file type: {file_ext}')

            table = table.dropna(how='all').reset_index(drop=True)
            if table.empty:
                raise ValueError('Volume table is empty')

            header_row = next(
                (
                    index
                    for index, row in table.iterrows()
                    if any(
                        str(value).strip().lower() == 'entidad'
                        for value in row.dropna()
                    )
                ),
                None,
            )
            if header_row is None:
                raise ValueError('Entity header not found')

            headers = table.iloc[header_row].tolist()
            entity_col = next(
                index for index, value in enumerate(headers)
                if str(value).strip().lower() == 'entidad'
            )
            data_start = header_row + 3
            data = table.iloc[data_start:].copy()

            group_row = table.iloc[header_row].tolist()
            subgroup_row = table.iloc[header_row + 1].tolist()
            action_row = table.iloc[header_row + 2].tolist()
            for row in (group_row, subgroup_row):
                for index in range(entity_col + 1, len(row)):
                    if pd.isna(row[index]) or str(row[index]).strip() == '':
                        row[index] = row[index - 1]

            column_map = []
            for index in range(entity_col + 1, len(headers)):
                action = str(action_row[index] or '').strip().lower()
                if action not in ('compra', 'venta'):
                    continue
                group = str(group_row[index] or '').replace('\n', ' ').strip()
                subgroup = str(subgroup_row[index] or '').strip()
                group = re.sub(r'\d+\s*$', '', group).strip()
                subgroup = re.sub(r'\d+\s*$', '', subgroup).strip()
                if 'preferencial' in subgroup.lower():
                    nv3 = 'Preferenciales'
                elif 'estándar' in subgroup.lower() or 'estandar' in subgroup.lower():
                    nv3 = 'Estándar'
                else:
                    nv3 = '-'
                if 'operaciones entre entidades' in group.lower():
                    nv2 = 'Operaciones entre entidades financieras'
                    nv3 = '-'
                elif 'operaciones con clientes' in group.lower():
                    nv2 = 'Operaciones con clientes'
                else:
                    continue
                column_map.append((index, nv2, nv3, action.capitalize()))

            titles = []
            for index in range(header_row):
                text = ' '.join(table.iloc[index].dropna().astype(str)).strip()
                if text:
                    titles.append(text)

            if file_ext == '.xlsx':
                titles = [
                    text for text in (
                        ' '.join(table.iloc[index].dropna().astype(str)).strip()
                        for index in range(header_row)
                    ) if text
                ]

            date_str = pd.Timestamp.now().strftime(format)
            title_text = document_text or ' '.join(titles)
            date_match = re.search(
                r'Al:?\s*(\d{1,2})\s+de\s+([A-Za-z]+)\s+de\s+(\d{4})',
                title_text,
                re.IGNORECASE,
            )
            if date_match:
                months = {
                    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
                    'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
                    'septiembre': 9, 'setiembre': 9, 'octubre': 10,
                    'noviembre': 11, 'diciembre': 12,
                }
                month = months.get(date_match.group(2).lower())
                if month:
                    date_str = pd.Timestamp(
                        year=int(date_match.group(3)),
                        month=month,
                        day=int(date_match.group(1)),
                    ).strftime(format)

            records = []
            for _, row in data.iterrows():
                entity = str(row.iloc[entity_col]).strip() if not pd.isna(row.iloc[entity_col]) else ''
                entity = re.sub(r'\s+', ' ', entity)
                if not entity or entity.lower() in ('nan', 'otros'):
                    continue
                if entity.lower().startswith(('notas', 'fuente', 'elaboración')):
                    continue
                for index, nv2, nv3, nv4 in column_map:
                    value = row.iloc[index]
                    if pd.isna(value) or str(value).strip() in ('', '-'):
                        continue
                    if isinstance(value, (int, float)):
                        if value == 0:
                            continue
                        valor = f'{value:,.0f}'
                    else:
                        valor = re.sub(r'(?<=\d)\s+(?=[\d,])', '', str(value).strip())
                    records.append({
                        'nv1': entity,
                        'nv2': nv2,
                        'nv3': nv3,
                        'nv4': nv4,
                        'fecha': date_str,
                        'valor': valor,
                    })

            dataframe = pd.DataFrame(
                records,
                columns=['nv1', 'nv2', 'nv3', 'nv4', 'fecha', 'valor'],
            )
            return {
                'file_name': os.path.basename(file_path),
                'titles': titles,
                'page_number': int(source_page),
            }, dataframe
        except Exception:
            traceback.print_exc()
            return ''

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str,
        TOLERANCE: float = 6.0,
    ) -> bool:
      
        try:
            if dataframe.empty or 'valor' not in dataframe.columns:
                return True
            return False
        except Exception:
            traceback.print_exc()
            return ""
