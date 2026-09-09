import os
import re
from datetime import datetime

import pandas as pd

from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import to_numeric_datax
from models.download.tools.download_tools import month_to_number


class D_BO_000000573_01(Conversion_Base):
    def extraction(self, file_path, key_words, template_path, page_number,
                   format='%Y-%m-%d'):
        """Extract and normalize the daily XLSX report."""
        try:
            _ = template_path
            workbook = pd.read_excel(file_path, sheet_name=0, header=None)
            if key_words:
                workbook_text = workbook.astype(str).to_string().lower()
                if not all(
                        keyword.lower() in workbook_text
                        for keyword in key_words.split()):
                    raise ValueError(
                        'The requested keywords were not found.')
            date_text = str(workbook.iloc[3, 0]).lower()
            date_match = re.search(
                r'(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})',
                date_text)
            if not date_match:
                raise ValueError('The report date could not be found.')

            day, month_name, year = date_match.groups()
            month = month_to_number(month_name)
            if not month:
                raise ValueError('The report month is not recognized.')
            report_date = datetime(
                int(year), month, int(day)).strftime(format)

            hour_columns = [
                index for index, value in enumerate(workbook.iloc[5])
                if re.fullmatch(r'\d{2}:\d{2}', str(value).strip())
            ]
            total_column = next(
                (index for index, value in enumerate(workbook.iloc[5])
                 if str(value).strip().upper() == 'TOTAL'),
                None)
            if total_column is not None:
                hour_columns.append(total_column)
            if not hour_columns:
                raise ValueError('The hourly columns could not be found.')

            rows = []
            current_node = None
            for row_index in range(6, len(workbook)):
                node = workbook.iloc[row_index, 0]
                metric = workbook.iloc[row_index, 1]
                if pd.notna(node):
                    current_node = str(node).strip()
                if pd.isna(metric) or current_node is None:
                    continue

                metric = str(metric).strip()
                for column in hour_columns:
                    value = workbook.iloc[row_index, column]
                    if pd.isna(value):
                        continue
                    if isinstance(value, (int, float)):
                        value = str(value)
                    else:
                        value = str(value).strip()
                    rows.append({
                        'nv1': current_node,
                        'nv2': metric,
                        'nv3': str(workbook.iloc[5, column]).strip(),
                        'fecha': report_date,
                        'valor': value,
                    })

            report_df = pd.DataFrame(
                rows, columns=['nv1', 'nv2', 'nv3', 'fecha', 'valor'])
            if report_df.empty:
                raise ValueError('The report contains no hourly values.')

            titles = [
                str(value).strip() for value in workbook.iloc[:4, 0]
                if pd.notna(value) and str(value).strip()
            ]
            metadata = {
                'file_name': os.path.basename(file_path),
                'titles': titles,
                'page_number': int(page_number),
            }
            return metadata, report_df
        except Exception as error:
            print(f'Could not extract report: {error}')
            return ''

    def validate_data_results(self, dataframe, decimal_separator,
                              TOLERANCE=6.0):
        """Validate hourly injection, withdrawal, and loss totals."""
        try:
            value_column = dataframe['valor'].copy()
            numeric_values = pd.to_numeric(value_column, errors='coerce')
            if numeric_values.isna().any():
                numeric_values = to_numeric_datax(
                    value_column, decimal_separator)
            if numeric_values.isna().any():
                return True

            data = dataframe.copy()
            data['_numeric_value'] = numeric_values
            data['_metric'] = data['nv2'].astype(str).str.upper()
            data['_hour'] = data['nv3'].astype(str)
            detail = data[data['nv1'].astype(str).str.upper() != 'TOTALES']
            summaries = data[
                data['nv1'].astype(str).str.upper() == 'TOTALES']

            for hour in summaries['_hour'].unique():
                hour_detail = detail[detail['_hour'] == hour]
                injections = hour_detail[
                    hour_detail['_metric'].str.contains('INYECCION')
                    & ~hour_detail['_metric'].str.contains('COSTO')
                ]['_numeric_value'].sum()
                withdrawals = hour_detail[
                    hour_detail['_metric'].str.contains('RETIRO')
                    & ~hour_detail['_metric'].str.contains('COSTO')
                ]['_numeric_value'].sum()

                for label, expected in (
                        ('INYECCIONES', injections),
                        ('RETIROS', withdrawals),
                        ('PERDIDAS', injections - withdrawals)):
                    summary = summaries[
                        (summaries['_hour'] == hour)
                        & summaries['_metric'].str.contains(label)
                    ]
                    if summary.empty:
                        continue
                    actual = summary['_numeric_value'].iloc[0]
                    if abs(actual - expected) > TOLERANCE:
                        return True
            return False
        except Exception as error:
            print(f'Could not validate report: {error}')
            return True
