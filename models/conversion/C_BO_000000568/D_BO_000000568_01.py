import os
import re
import sqlite3
import traceback
import pandas as pd
import numpy as np
from rapidfuzz import fuzz

from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.text_normalization import Text_Normalization
from models.conversion.tools.conversion_tools import (
    get_xlsx_report_dataframe,
    get_pdf_report_page,
    extract_pdf_table_fitz,
    to_numeric_datax,
    search_key_words,
    get_date,
    verify_frecuency,
    verify_levels,
    verify_values,
)


class D_BO_000000568_01(Conversion_Base):
    def extraction(self, file_path: str, key_words: str, template_path: str, page_number: int, format: str = '%Y-%m-%d') -> tuple[dict, pd.DataFrame] | str:
        """
        Extract and flatten a specific table from a source document (PDF or Excel).
        
        Args:
            file_path (str): Absolute path of the downloaded source file
            key_words (str): Keywords to identify and validate the table
            template_path (str): Path to reference template (if applicable)
            page_number (int): Page number where the table starts (>= 1)
            format (str): Expected date format (default: '%Y-%m-%d')
        
        Returns:
            tuple[dict, pd.DataFrame]: (metadata_dict, melted DataFrame) on success
            str: Empty string '' on error
        """
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.xlsx':
                # Extract from Excel safely without triggering float unidecode error
                tables = pd.read_excel(file_path, sheet_name=None, header=None)
                df = None
                sheet_num = 1
                for i, (s_name, s_df) in enumerate(tables.items()):
                    s_clean = s_df.fillna('').astype(str)
                    text = ' '.join(s_clean.to_numpy().flatten())
                    if search_key_words(text=text, key_words=key_words):
                        df = s_df
                        sheet_num = i + 1
                        break
                if df is None:
                    target_idx = page_number - 1 if 0 <= (page_number - 1) < len(tables) else 0
                    sheet_num = target_idx + 1
                    df = list(tables.values())[target_idx]
                
                df = df.dropna(how='all').reset_index(drop=True)
                
                # Find header row (row containing Compra and Venta)
                header_row = None
                for i, row in df.iterrows():
                    row_text = " ".join(row.dropna().astype(str))
                    if 'compra' in row_text.lower() and 'venta' in row_text.lower() and 'tipos de cambio' not in row_text.lower():
                        header_row = i
                        break
                
                if header_row is None:
                    raise ValueError("Header row not found")
                
                # Extract titles 
                titles = []
                for i in df.index:
                    if i >= header_row - 2: 
                        break
                    row_text = " ".join(df.loc[i].dropna().astype(str))
                    if row_text.strip():
                        titles.append(row_text.strip())
                
                # Build multi-level column mapping from sub-header rows
                level1_idx = header_row - 2  
                level2_idx = header_row - 1 
                
                level1_raw = df.loc[level1_idx].tolist() if level1_idx in df.index else [None] * len(df.columns)
                level2_raw = df.loc[level2_idx].tolist() if level2_idx in df.index else [None] * len(df.columns)

                # Locate entity column before forward filling
                entity_col_idx = next(
                    (col_idx for col_idx, value in enumerate(level1_raw)
                     if str(value).strip().lower() == 'entidad'),
                    None
                )
                if entity_col_idx is None:
                    entity_col_idx = next(
                        (col_idx for col_idx, value in enumerate(level2_raw)
                         if str(value).strip().lower() == 'entidad'),
                        next(
                            (col_idx for col_idx, value in enumerate(df.loc[header_row].tolist())
                             if str(value).strip().lower() == 'entidad'),
                            1
                        )
                    )

                level1_vals = list(level1_raw)
                level2_vals = list(level2_raw)
                
                # Forward-fill NaN values in each level
                for vals in [level1_vals, level2_vals]:
                    for j in range(1, len(vals)):
                        if pd.isna(vals[j]):
                            vals[j] = vals[j - 1]

                # Build column mapping: col_idx -> {nv2, nv3, nv4}
                header_vals = df.loc[header_row].tolist()
                col_map = {}
                for col_idx in range(len(header_vals)):
                    if col_idx <= entity_col_idx:
                        continue
                    
                    l1 = str(level1_vals[col_idx]).strip() if not pd.isna(level1_vals[col_idx]) else ''
                    l2 = str(level2_vals[col_idx]).strip() if not pd.isna(level2_vals[col_idx]) else ''
                    hv = str(header_vals[col_idx]).strip().lower() if not pd.isna(header_vals[col_idx]) else ''
                    
                    # Determine nv4 from header row (Compra/Venta)
                    if 'compra' in hv:
                        nv4 = 'Compra'
                    elif 'venta' in hv:
                        nv4 = 'Venta'
                    else:
                        continue
                    
                    # Determine nv2 from level 1 (casing matches SQLite template)
                    if 'promedio total' in l1.lower():
                        nv2 = 'Promedio Total'
                    elif 'operaciones con clientes' in l1.lower():
                        nv2 = 'Operaciones con Clientes'
                    elif 'entidades financieras' in l1.lower() or 'operaciones entre' in l1.lower():
                        nv2 = 'Operaciones entre Entidades Financieras'
                    else:
                        continue
                    
                    # Determine nv3 from level 2 (clean footnote numbers)
                    l2_clean = re.sub(r'\d+\s*$', '', l2).strip()
                    if nv2 == 'Promedio Total':
                        nv3 = '-'
                    elif nv2 == 'Operaciones entre Entidades Financieras':
                        # No sub-grouping for inter-entity operations
                        nv3 = '-'
                    elif 'est' in l2_clean.lower():
                        nv3 = '-' if nv2 == 'Operaciones entre Entidades Financieras' else 'Estándar'
                    elif 'preferencial' in l2_clean.lower():
                        nv3 = 'Preferenciales'
                    else:
                        nv3 = '-'
                    
                    col_map[col_idx] = {'nv2': nv2, 'nv3': nv3, 'nv4': nv4}
                
                # Get data rows (after header)
                data_df = df.loc[header_row + 1:].copy()
                
                # Extract date from titles or fallback to filename
                date_str = None
                for title in titles:
                    date_match = re.search(r'Al:?\s*(\d{1,2})\s+de\s+([a-zA-Z]+)\s+de\s+(\d{4})', title, re.IGNORECASE)
                    if date_match:
                        months = {
                            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
                            'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
                            'septiembre': 9, 'setiembre': 9, 'octubre': 10,
                            'noviembre': 11, 'diciembre': 12
                        }
                        day = int(date_match.group(1))
                        month = months.get(date_match.group(2).lower().strip(), 1)
                        year = int(date_match.group(3))
                        date_str = pd.Timestamp(year=year, month=month, day=day).strftime(format)
                        break
                
                if not date_str:
                    fn_match = re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(file_path))
                    if fn_match:
                        date_str = fn_match.group(1)
                    else:
                        date_str = pd.Timestamp.now().strftime(format)
                
                # Melt data
                records = []
                
                for idx, row in data_df.iterrows():
                    val2 = row.iloc[entity_col_idx] if len(row) > entity_col_idx else None
                    
                    # Entity name from col entity_col_idx
                    entity = str(val2).strip() if not pd.isna(val2) and str(val2).strip() else ''
                    
                    if not entity or entity.lower() == 'nan':
                        continue
                    
                    # Stop at second table boundary (Volumen de operaciones)
                    if 'volumen' in entity.lower() or 'expresado' in entity.lower() or entity.strip().lower() == 'entidad':
                        break
                    
                    # Skip footnotes and non-entity text
                    if 'notas' in entity.lower() or 'fuente' in entity.lower() or 'elaboraci' in entity.lower():
                        continue
                    if re.match(r'^\d\s+[A-Z]', entity, re.IGNORECASE) and len(entity) > 20:
                        continue
                    
                    # Remove trailing footnote numbers like "5" or "1" from entity name
                    entity = re.sub(r'\s*\d+\s*$', '', entity).strip()
                    
                    if not entity:
                        continue
                    
                    for col_idx, mapping in col_map.items():
                        value = row.iloc[col_idx]
                        if pd.isna(value) or value == '' or str(value).strip().lower() in ('nan', '-', 'none'):
                            continue
                        
                        try:
                            fval = float(value)
                            if fval == 0:
                                continue
                            valor = f'{fval:.2f}'
                        except (ValueError, TypeError):
                            valor = str(value).strip()
                        
                        records.append({
                            'nv1': entity,
                            'nv2': mapping['nv2'],
                            'nv3': mapping['nv3'],
                            'nv4': mapping['nv4'],
                            'fecha': date_str,
                            'valor': valor
                        })
                
                melted_df = pd.DataFrame(records)
                
                # Clean dataframe
                if not melted_df.empty:
                    required_columns = ['nv1', 'nv2', 'nv3', 'nv4', 'fecha', 'valor']
                    for col in required_columns:
                        if col not in melted_df.columns:
                            melted_df[col] = None
                    
                    melted_df = melted_df[required_columns]
                    
                    for col in ['nv1', 'nv2', 'nv3', 'nv4']:
                        melted_df[col] = melted_df[col].astype(str).str.strip()
                        melted_df[col] = melted_df[col].str.replace(r'\s+', ' ', regex=True)
                        melted_df[col] = melted_df[col].replace(['nan', 'None', 'null'], '')
                    
                    melted_df['fecha'] = pd.to_datetime(melted_df['fecha']).dt.strftime('%Y-%m-%d')
                    melted_df = melted_df.dropna(subset=['nv1'])
                    melted_df = melted_df[melted_df['nv1'] != '']
                    melted_df = melted_df[melted_df['valor'].notna()]
                    melted_df = melted_df[melted_df['valor'] != '']
                    melted_df = melted_df.reset_index(drop=True)
                
                metadata = {
                    'file_name': os.path.basename(file_path),
                    'titles': titles,
                    'page_number': sheet_num
                }
                
                return metadata, melted_df
                
            elif file_ext == '.pdf':
                # Extract from PDF
                import pdfplumber
                
               
                with pdfplumber.open(file_path) as pdf_plumber:
                    target_page = get_pdf_report_page(pdf_plumber, key_words, page_number=page_number)
                    target_page_number = target_page.page_number  # pdfplumber uses 1-based page_number

                    table = target_page.extract_table()
                if not table:
                    raise ValueError("No table extracted from PDF")

                table_width = max(len(row) for row in table)
                table = [list(row) + [None] * (table_width - len(row)) for row in table]
                df = pd.DataFrame(table).dropna(how='all')
                
                # Find header and data sections
                header_row = None
                data_start = None
                
                for i, row in df.iterrows():
                    row_text = " ".join(row.dropna().astype(str))
                    
                    if any(str(cell).strip().lower() == 'compra venta' for cell in row.dropna()):
                        header_row = i
                        data_start = i + 1
                        break
                    
                    if search_key_words(row_text, key_words):
                        for j in range(i + 1, min(i + 5, len(df))):
                            next_row = " ".join(df.iloc[j].dropna().astype(str))
                            if any(str(cell).strip().lower() == 'compra venta' for cell in df.iloc[j].dropna()):
                                header_row = j
                                data_start = j + 1
                                break
                        if header_row is not None:
                            break
                
                if header_row is None:
                    raise ValueError("Header not found in PDF table")
                
                # Extract titles
                titles = []
                for i in range(header_row):
                    row_text = " ".join(df.iloc[i].dropna().astype(str))
                    if row_text.strip():
                        titles.append(row_text.strip())
                
                # Build stable compound headers from the grouped PDF header rows.
                group_row = df.iloc[1].tolist()
                subgroup_row = df.iloc[2].tolist() if header_row >= 2 else [None] * len(group_row)
                action_row = df.iloc[header_row].tolist()
                entity_col_idx = next(
                    (col_idx for col_idx, value in enumerate(group_row)
                     if str(value).strip().lower() == 'entidad'),
                    0,
                )
                actions = [''] * len(group_row)
                action_col_idx = entity_col_idx + 1
                for value in action_row:
                    action_tokens = re.findall(r'compra|venta', str(value or ''), re.IGNORECASE)
                    for action_token in action_tokens:
                        while action_col_idx < len(actions) and actions[action_col_idx]:
                            action_col_idx += 1
                        if action_col_idx < len(actions):
                            actions[action_col_idx] = action_token.capitalize()
                            action_col_idx += 1

                for source in (group_row, subgroup_row):
                    for index in range(entity_col_idx + 1, len(source)):
                        if not source[index]:
                            source[index] = source[index - 1]

                clean_headers = [''] * len(group_row)
                clean_headers[entity_col_idx] = 'Entidad'
                for index in range(entity_col_idx + 1, len(group_row)):
                    group = re.sub(r'\d+\s*$', '', str(group_row[index] or '')).strip()
                    subgroup = re.sub(r'\d+\s*$', '', str(subgroup_row[index] or '')).strip()
                    action = actions[index]
                    parts = [part for part in (group, subgroup, action) if part]
                    clean_headers[index] = ' '.join(parts)

                data_df = df.iloc[data_start:].copy()
                data_df.columns = clean_headers

                # Join wrapped entity names when the continuation row has no values.
                for row_pos in range(len(data_df) - 1):
                    current_entity = data_df.iloc[row_pos, entity_col_idx]
                    next_entity = data_df.iloc[row_pos + 1, entity_col_idx]
                    next_values = data_df.iloc[row_pos + 1].drop(
                        data_df.columns[entity_col_idx]
                    )
                    if (
                        isinstance(next_entity, str)
                        and '\n' in next_entity
                        and not next_values.fillna('').astype(str).str.strip().any()
                    ):
                        entity_lines = [line.strip() for line in next_entity.splitlines() if line.strip()]
                        if len(entity_lines) > 1:
                            data_df.iloc[row_pos, entity_col_idx] = (
                                f'{str(current_entity).strip()} {entity_lines[0]}'
                            ).strip()
                            data_df.iloc[row_pos + 1, entity_col_idx] = ' '.join(entity_lines[1:])
                
                # Extract date from titles or fallback to filename
                date_str = None
                for title in titles:
                    date_match = re.search(r'Al:?\s*(\d{1,2})\s+de\s+([a-zA-Z]+)\s+de\s+(\d{4})', title, re.IGNORECASE)
                    if date_match:
                        months = {
                            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
                            'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
                            'septiembre': 9, 'setiembre': 9, 'octubre': 10,
                            'noviembre': 11, 'diciembre': 12
                        }
                        day = int(date_match.group(1))
                        month = months.get(date_match.group(2).lower().strip(), 1)
                        year = int(date_match.group(3))
                        date_str = pd.Timestamp(year=year, month=month, day=day).strftime(format)
                        break
                
                if not date_str:
                    fn_match = re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(file_path))
                    if fn_match:
                        date_str = fn_match.group(1)
                    else:
                        date_str = pd.Timestamp.now().strftime(format)
                
                # Melt data
                records = []
                
                for idx, row in data_df.iterrows():
                    val = row.iloc[entity_col_idx]
                    entity = str(val) if not pd.isna(val) else ''
                    
                    if not entity or entity == 'nan' or entity == '':
                        continue
                    if entity.isdigit() or entity.replace('.', '').isdigit():
                        continue
                    if 'total' in entity.lower() or 'promedio' in entity.lower():
                        continue
                    
                    for col_idx, col in enumerate(data_df.columns):
                        if col_idx == entity_col_idx or not col:
                            continue
                        
                        value = row.iloc[col_idx]
                        if pd.isna(value) or value == '' or value == 'nan':
                            continue
                        
                        col_name = str(col).lower()
                        
                        if 'promedio total' in col_name:
                            nv2 = 'Promedio Total'
                        elif 'operaciones entre entidades' in col_name:
                            nv2 = 'Operaciones entre Entidades Financieras'
                        else:
                            nv2 = 'Operaciones con Clientes'

                        nv3 = '-' if nv2 != 'Operaciones con Clientes' else 'Estándar'
                        nv4 = ''
                        
                        if 'compra' in col_name:
                            nv4 = 'Compra'
                        elif 'venta' in col_name:
                            nv4 = 'Venta'
                        else:
                            continue
                        
                        if nv2 == 'Operaciones con Clientes' and 'preferencial' in col_name:
                            nv3 = 'Preferenciales'
                        
                        # Preserve the source representation; numeric conversion is
                        # performed only by to_numeric_datax during validation.
                        if isinstance(value, (int, float, np.number)):
                            valor = f'{float(value):.2f}'
                        else:
                            valor = str(value).strip()
                        
                        records.append({
                            'nv1': entity,
                            'nv2': nv2,
                            'nv3': nv3,
                            'nv4': nv4,
                            'fecha': date_str,
                            'valor': valor
                        })
                
                melted_df = pd.DataFrame(records)
                
                # Clean dataframe
                if not melted_df.empty:
                    required_columns = ['nv1', 'nv2', 'nv3', 'nv4', 'fecha', 'valor']
                    for col in required_columns:
                        if col not in melted_df.columns:
                            melted_df[col] = None
                    
                    melted_df = melted_df[required_columns]
                    
                    for col in ['nv1', 'nv2', 'nv3', 'nv4']:
                        melted_df[col] = melted_df[col].astype(str).str.strip()
                        melted_df[col] = melted_df[col].str.replace(r'\s+', ' ', regex=True)
                        melted_df[col] = melted_df[col].replace(['nan', 'None', 'null'], '')
                    
                    melted_df['fecha'] = pd.to_datetime(melted_df['fecha']).dt.strftime('%Y-%m-%d')
                    melted_df = melted_df.dropna(subset=['nv1'])
                    melted_df = melted_df[melted_df['nv1'] != '']
                    melted_df = melted_df[melted_df['valor'].notna()]
                    melted_df = melted_df[melted_df['valor'] != 0]
                    melted_df = melted_df.reset_index(drop=True)
                
                metadata = {
                    'file_name': os.path.basename(file_path),
                    'titles': titles,
                    'page_number': target_page_number
                }
                
                return metadata, melted_df
                
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")
                
        except Exception as e:
            traceback.print_exc()
            return ''
    
    def validate_data_results(self, dataframe: pd.DataFrame, decimal_separator: str, TOLERANCE: float = 6.0) -> bool:
       
        try:
            df = dataframe.copy()
            valor_col = df.columns[-1]
            
            # Convert to numeric using conversion_tools function
            df[valor_col] = to_numeric_datax(df[valor_col], decimal_separator)
            df = df.dropna(subset=[valor_col])
            
            if df.empty:
                return False
            
            # Look for total rows
            total_patterns = ['total', 'promedio', 'suma', 'subtotal']
            total_rows = df[df['nv1'].str.lower().str.contains('|'.join(total_patterns), na=False)]
            
            if total_rows.empty:
                return False
            
            # Group by hierarchy and calculate sums
            group_cols = ['nv1', 'nv2', 'nv3', 'nv4']
            actual_totals = df.groupby(group_cols)[valor_col].sum().reset_index()
            actual_totals['actual_total'] = actual_totals[valor_col]
            
            reported_totals = total_rows.copy()
            merged = pd.merge(
                actual_totals,
                reported_totals,
                on=group_cols,
                suffixes=('_actual', '_reported'),
                how='outer'
            )
            
            # Check discrepancies
            for idx, row in merged.iterrows():
                if pd.isna(row['valor_reported']) or pd.isna(row['valor_actual']):
                    continue
                
                diff = abs(row['valor_reported'] - row['valor_actual'])
                
                if diff > TOLERANCE:
                    print(f"Discrepancy: Reported={row['valor_reported']}, Actual={row['valor_actual']}, Diff={diff}")
                    return True
            
            return False
            
        except Exception as e:
            traceback.print_exc()
            return ""

    def structure_review(self, data_file: str, last_conversion_path: str):
        """
        Verifies the structure of a new data file against a previous conversion.
        Excludes 'nv1' from level verification because financial entities (banks,
        cooperatives) vary daily depending on which entities transacted on each date.
        """
        if not last_conversion_path:
            return data_file

        try:
            data_df = self.get_last_conversion_df(last_conversion_path=data_file, table_name=self.__class__.__name__)
            last_conversion_df = self.get_last_conversion_df(last_conversion_path=last_conversion_path)    
            
            last_conversion_cols = last_conversion_df.columns
            data_cols = data_df.columns

            last_conversion_cols_without_titles = [col for col in last_conversion_cols if not re.search('titulo', col)]
            data_cols_without_titles = [col for col in data_cols if not re.search('titulo', col)]

            for i, template_col in enumerate(last_conversion_cols_without_titles):
                similarity = fuzz.ratio(Text_Normalization.get_srch_value(template_col), Text_Normalization.get_srch_value(data_cols_without_titles[i]))   
                if similarity < 90:
                    raise ValueError(f"Column mismatch detected: Template column '{template_col}' does not match New report column '{data_cols_without_titles[i]}'.")
            
            data_df.columns = last_conversion_cols
            verify_values(data_df=data_df)

            columns_to_review_df = self.get_last_conversion_df(last_conversion_path=last_conversion_path, table_name='columns_to_review')
            columns_to_review = columns_to_review_df['column'].unique().tolist()
            
            # Exclude nv1: financial entities vary per daily publication
            columns_to_review = [col for col in columns_to_review if col != 'nv1']

            if not columns_to_review:
                return data_file
            
            columns_to_review_without_date = [col for col in columns_to_review if not re.search(r'fecha', col)]

            if len(columns_to_review_without_date) > 0:
                verify_levels(template_df=last_conversion_df, data_df=data_df, columns_to_review=columns_to_review_without_date)   
            
            if len(columns_to_review) != len(columns_to_review_without_date):
                verify_frecuency(template_df=last_conversion_df, data_df=data_df)
                
            print("Structure verified successfully.")
            return data_file
        
        except ValueError as e:
            print(f"There might be a change in structure: {e}")            
        except Exception as e:
            print("An error occurred during structure verification")
            traceback.print_exc()            
        return ""

    def report_data_validation(self, *args, **kwargs):
        res = super().report_data_validation(*args, **kwargs)
        if isinstance(res, dict) and res.get("conversion_path") and res.get("file_extension") == "sqlite":
            try:
                # Ensure columns_to_review in newly created sqlite does not keep nv1
                conn = sqlite3.connect(res["conversion_path"])
                conn.execute("DELETE FROM columns_to_review WHERE column = 'nv1'")
                conn.commit()
                conn.close()
            except Exception:
                pass
        return res