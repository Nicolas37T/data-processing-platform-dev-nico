from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import calendar
import traceback
import unicodedata
import zipfile
import tempfile
import shutil
import numpy as np
import pandas as pd
import xlrd

from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000318_01(Conversion_Base):
    """
    Conversion robot for D_BO_000000318_01:
    Bpy - Obligaciones, Cartera y Contingente por Departamento.
    Consolidates departmental banking reports (all 9 departments)
    from .xls and .ods files into a single melted vertical DataFrame.
    """

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d"
    ) -> tuple:
        """
        Locates and extracts the obligations, portfolio, and contingent
        data across all 9 departments from the source directory or file.
        Returns a tuple containing a metadata dictionary and a normalized
        melted DataFrame with levels nv1 (Department) through nv7 (Currency).
        """
        try:
            # Internal helper: clean text
            def clean_text(val) -> str:
                if not isinstance(val, str):
                    return ""
                return re.sub(r'\s+', ' ', val).strip()

            # Internal helper: agnostic sheet adapter for .xls and .ods
            class SheetAdapter:
                def __init__(self, data):
                    self.data = data
                    self.nrows = len(data)
                    self.ncols = max((len(r) for r in data), default=0)

                def cell_value(self, r, c):
                    if r < len(self.data) and c < len(self.data[r]):
                        val = self.data[r][c]
                        return "" if pd.isna(val) else val
                    return ""

            def load_sheet(fpath: str, p_num: int = 1):
                sheet_idx = p_num - 1 if p_num >= 1 else 0
                ext = os.path.splitext(fpath)[1].lower()
                if ext == '.xls':
                    wb = xlrd.open_workbook(fpath)
                    s_idx = sheet_idx if sheet_idx < wb.nsheets else 0
                    sh = wb.sheet_by_index(s_idx)
                    data = [
                        [sh.cell_value(r, c) for c in range(sh.ncols)]
                        for r in range(sh.nrows)
                    ]
                    return SheetAdapter(data)
                elif ext == '.ods':
                    df = pd.read_excel(fpath, sheet_name=sheet_idx, header=None, engine='odf')
                    return SheetAdapter(df.values.tolist())
                else:
                    df = pd.read_excel(fpath, sheet_name=sheet_idx, header=None)
                    return SheetAdapter(df.values.tolist())

            # Official department codes and names
            dept_catalog = {
                'BEN': 'Beni',
                'CBB': 'Cochabamba',
                'CHU': 'Chuquisaca',
                'LPZ': 'La Paz',
                'ORU': 'Oruro',
                'PAN': 'Pando',
                'POT': 'Potosí',
                'SCZ': 'Santa Cruz',
                'TAR': 'Tarija'
            }

            # 1. Locate all departmental files in base directory (including compressed ZIP archives)
            base_dir = (
                os.path.dirname(os.path.abspath(file_path))
                if os.path.isfile(file_path)
                else os.path.abspath(file_path)
            )

            temp_extract_dir = None
            search_dirs = [base_dir]

            # Discover if there is a corresponding zip file
            zip_target = None
            if file_path.lower().endswith('.zip') and os.path.isfile(file_path):
                zip_target = file_path
            else:
                # 1. Look in the same directory as file_path
                candidate_zip = os.path.splitext(file_path)[0] + '.zip'
                if os.path.isfile(candidate_zip):
                    zip_target = candidate_zip
                elif os.path.exists(base_dir):
                    for entry in os.listdir(base_dir):
                        if entry.lower().endswith('.zip') and not entry.startswith('~'):
                            zip_target = os.path.join(base_dir, entry)
                            break

                # 2. Look in the download directory if file_path is inside tmp/
                if not zip_target:
                    norm_base = base_dir.replace('\\', '/')
                    dl_base = re.sub(r'/data_process/', '/downloaded_files/', norm_base, flags=re.I)
                    dl_root = re.sub(r'/tmp_[^/]+/?$', '', dl_base)
                    
                    base_fname_no_ext = os.path.splitext(os.path.basename(file_path))[0]
                    date_prefix = base_fname_no_ext[:10] if len(base_fname_no_ext) >= 10 and re.match(r'^\d{4}-\d{2}-\d{2}', base_fname_no_ext) else ""

                    search_roots = [dl_root, os.path.dirname(base_dir)]
                    for sroot in search_roots:
                        if sroot and os.path.exists(sroot):
                            for r_dir, _, f_list in os.walk(sroot):
                                for entry in f_list:
                                    if entry.lower().endswith('.zip') and not entry.startswith('~'):
                                        if not date_prefix or date_prefix in entry:
                                            zip_target = os.path.join(r_dir, entry)
                                            break
                                if zip_target:
                                    break
                        if zip_target:
                            break

            if zip_target and zipfile.is_zipfile(zip_target):
                temp_extract_dir = tempfile.mkdtemp(prefix="datax_dept_")
                try:
                    with zipfile.ZipFile(zip_target, 'r') as zf:
                        zf.extractall(temp_extract_dir)
                    search_dirs.insert(0, temp_extract_dir)
                except Exception as ze:
                    print(f"Warning: Could not extract zip {zip_target}: {ze}")

            candidate_files = []
            for sdir in search_dirs:
                if os.path.exists(sdir):
                    for root, _, files in os.walk(sdir):
                        for entry in files:
                            if entry.lower().endswith(('.xls', '.ods')) and not entry.startswith('~'):
                                candidate_files.append(os.path.join(root, entry))

            # Prioritize .xls over .ods when sorting
            candidate_files.sort(
                key=lambda x: (0 if x.lower().endswith('.xls') else 1, x)
            )

            # Match files to departments, ignoring national/total files
            dept_files = {}
            for f in candidate_files:
                fname = os.path.basename(f)
                if re.search(r'\b(total|nacional|pais)\b', fname, re.I):
                    continue
                for code, dept_name in dept_catalog.items():
                    if code not in dept_files:
                        pattern = re.compile(rf"{code}", re.I)
                        norm_fname = unicodedata.normalize(
                            'NFKD', fname
                        ).encode('ASCII', 'ignore').decode('utf-8')
                        norm_dept = unicodedata.normalize(
                            'NFKD', dept_name
                        ).encode('ASCII', 'ignore').decode('utf-8')
                        if pattern.search(norm_fname) or norm_dept.lower() in norm_fname.lower():
                            dept_files[code] = (dept_name, f)
                            break

            # If still not found, check header of candidate files to match department
            if len(dept_files) < 9:
                for f in candidate_files:
                    fname = os.path.basename(f)
                    if re.search(r'\b(total|nacional|pais)\b', fname, re.I):
                        continue
                    try:
                        sh_check = load_sheet(f, 1)
                        if sh_check.nrows > 1:
                            r1_text = clean_text(sh_check.cell_value(1, 0)).lower()
                            for code, dept_name in dept_catalog.items():
                                if code not in dept_files and dept_name.lower() in r1_text:
                                    dept_files[code] = (dept_name, f)
                                    break
                    except Exception:
                        pass

            # Fallback if no sibling files found: process the single received file
            if not dept_files and os.path.isfile(file_path):
                single_fname = os.path.basename(file_path)
                matched_dept = "Bolivia"
                for code, dept_name in dept_catalog.items():
                    if code.lower() in single_fname.lower() or dept_name.lower() in single_fname.lower():
                        matched_dept = dept_name
                        break
                dept_files['SINGLE'] = (matched_dept, file_path)

            months_es = {
                'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4,
                'MAYO': 5, 'JUNIO': 6, 'JULIO': 7, 'AGOSTO': 8,
                'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12
            }

            all_records = []
            general_t0 = "BANCOS PYME"
            general_t3 = "(en miles de bolivianos)"

            # 2. Extract each department file
            for code, (dept_name, fpath) in dept_files.items():
                sheet = load_sheet(fpath, page_number)

                t0 = clean_text(sheet.cell_value(0, 0)) if sheet.nrows > 0 else ""
                t2_raw = clean_text(sheet.cell_value(2, 0)) if sheet.nrows > 2 else ""
                t3 = clean_text(sheet.cell_value(3, 0)) if sheet.nrows > 3 else ""

                if t0:
                    general_t0 = t0
                if t3:
                    general_t3 = t3

                # Parse date dynamically
                date_match = re.search(
                    r'AL\s+(\d{1,2})\s+DE\s+([A-ZÁÉÍÓÚ]+)\s+DE\s+(\d{4})',
                    t2_raw.upper()
                )
                if date_match:
                    day = int(date_match.group(1))
                    m_name = unicodedata.normalize(
                        'NFKD', date_match.group(2)
                    ).encode('ASCII', 'ignore').decode('utf-8')
                    year = int(date_match.group(3))
                    month = months_es.get(m_name, 8)
                    _, max_day = calendar.monthrange(year, month)
                    target_day = min(day, max_day)
                    date_str = f"{year:04d}-{month:02d}-{target_day:02d}"
                else:
                    date_str = "2026-08-31"

                # Map column entities (nv6) and currencies (nv7)
                col_mapping = {}
                current_entity = None
                for c in range(1, sheet.ncols):
                    e_val = sheet.cell_value(5, c) if sheet.nrows > 5 else ""
                    c_val = sheet.cell_value(6, c) if sheet.nrows > 6 else ""

                    e_clean = clean_text(e_val)
                    c_clean = clean_text(c_val)

                    if e_clean:
                        current_entity = e_clean

                    if current_entity and c_clean:
                        col_mapping[c] = (current_entity, c_clean)

                # State machine for accounting accounts (nv2 to nv5)
                current_nv2 = None
                current_nv3 = None
                current_nv4 = None
                current_nv5 = None

                for r in range(7, sheet.nrows):
                    raw_cell = sheet.cell_value(r, 0)
                    if not str(raw_cell).strip():
                        continue

                    concept = clean_text(raw_cell)
                    spaces = len(raw_cell) - len(raw_cell.lstrip(' '))
                    concept_upper = concept.upper()

                    # Skip total summary rows to avoid double counting
                    if concept_upper in ['OBLIGACIONES', 'CARTERA Y CONTINGENTE']:
                        continue
                    if concept_upper.startswith('TOTAL'):
                        continue

                    if re.match(r"^OBLIGACIONES CON EL P[ÚU]BLICO$", concept, re.I) and spaces == 0:
                        current_nv2 = concept
                        current_nv3 = None
                        current_nv4 = None
                        current_nv5 = None
                    elif re.match(r"^OBLIGACIONES CON EL P[ÚU]BLICO A LA VISTA$", concept, re.I) and spaces == 0:
                        current_nv2 = "OBLIGACIONES CON EL PÚBLICO"
                        current_nv3 = concept
                        current_nv4 = None
                        current_nv5 = None
                    elif re.match(r"^OBLIGACIONES CON EL P[ÚU]BLICO POR CUENTAS DE AHORROS$", concept, re.I) and spaces == 0:
                        current_nv2 = "OBLIGACIONES CON EL PÚBLICO"
                        current_nv3 = concept
                        current_nv4 = None
                        current_nv5 = None
                    elif re.match(r"^OBLIGACIONES CON EL P[ÚU]BLICO A PLAZO$", concept, re.I) and spaces == 0:
                        current_nv2 = "OBLIGACIONES CON EL PÚBLICO"
                        current_nv3 = concept
                        current_nv4 = None
                        current_nv5 = None
                    elif re.match(r"^OBLIGACIONES CON EL P[ÚU]BLICO A PLAZO$", concept, re.I) and spaces == 6:
                        current_nv4 = concept
                        current_nv5 = None
                    elif re.search(r"RESTRINGIDAS", concept, re.I) and spaces == 4:
                        current_nv2 = "OBLIGACIONES CON EL PÚBLICO"
                        current_nv3 = concept
                        current_nv4 = None
                        current_nv5 = None
                    elif re.search(r"A PLAZO FIJO CON ANOTACI[ÓO]N EN CUENTA", concept, re.I) and spaces == 4:
                        current_nv2 = "OBLIGACIONES CON EL PÚBLICO"
                        current_nv3 = concept
                        current_nv4 = None
                        current_nv5 = None
                    elif re.match(r"^OBLIGACIONES CON EMPRESAS P[ÚU]BLICAS$", concept, re.I):
                        current_nv2 = concept
                        current_nv3 = None
                        current_nv4 = None
                        current_nv5 = None
                    elif re.match(r"^OBLIGACIONES CON INSTITUCIONES FISCALES$", concept, re.I):
                        current_nv2 = concept
                        current_nv3 = None
                        current_nv4 = None
                        current_nv5 = None
                    elif "BANCOS Y ENTIDADES DE FINANCIAMIENTO" in concept_upper:
                        current_nv2 = concept
                        current_nv3 = None
                        current_nv4 = None
                        current_nv5 = None
                    elif concept_upper == "OBLIGACIONES CON EL BCB":
                        current_nv2 = concept
                        current_nv3 = None
                        current_nv4 = None
                        current_nv5 = None
                    elif any(concept_upper.startswith(k) for k in [
                        'CARTERA', 'CUENTAS CONTINGENTES', 'PRODUCTOS DEVENGADOS',
                        '(PREVISIÓN', '(PREVISION'
                    ]):
                        current_nv2 = concept
                        current_nv3 = None
                        current_nv4 = None
                        current_nv5 = None
                    else:
                        if current_nv4 == "OBLIGACIONES CON EL PÚBLICO A PLAZO" and spaces >= 8:
                            current_nv5 = concept
                        elif current_nv2 == "OBLIGACIONES CON BANCOS Y ENTIDADES DE FINANCIAMIENTO":
                            current_nv3 = concept
                            current_nv4 = None
                            current_nv5 = None
                        elif current_nv2 == "OBLIGACIONES CON EL BCB":
                            current_nv3 = concept
                            current_nv4 = None
                            current_nv5 = None
                        elif current_nv3 is not None:
                            current_nv4 = concept
                            current_nv5 = None

                    row_nv1 = dept_name
                    row_nv2 = current_nv2
                    row_nv3 = current_nv3
                    row_nv4 = current_nv4
                    row_nv5 = current_nv5

                    for c, (entity, cur) in col_mapping.items():
                        cell_val = sheet.cell_value(r, c)
                        if cell_val is None or str(cell_val).strip() == '':
                            continue
                        try:
                            num_val = float(cell_val)
                        except (ValueError, TypeError):
                            continue

                        all_records.append({
                            'nv1': row_nv1,
                            'nv2': row_nv2,
                            'nv3': row_nv3,
                            'nv4': row_nv4,
                            'nv5': row_nv5,
                            'nv6': entity,
                            'nv7': cur,
                            'fecha': date_str,
                            'valor': num_val
                        })

            df_melted = pd.DataFrame(all_records)

            if not df_melted.empty:
                df_melted['valor'] = df_melted['valor'].apply(
                    lambda x: np.format_float_positional(x, trim='-') if pd.notna(x) else x
                )
                df_melted = df_melted.dropna(subset=['valor'])

            metadata_dict = {
                "file_name": os.path.basename(file_path),
                "titles": [
                    general_t0,
                    "OBLIGACIONES, CARTERA Y CONTINGENTE POR DEPARTAMENTO",
                    general_t3
                ],
                "page_number": int(page_number)
            }

            if temp_extract_dir and os.path.exists(temp_extract_dir):
                shutil.rmtree(temp_extract_dir, ignore_errors=True)

            return metadata_dict, df_melted

        except Exception as error:
            if 'temp_extract_dir' in locals() and temp_extract_dir and os.path.exists(temp_extract_dir):
                shutil.rmtree(temp_extract_dir, ignore_errors=True)
            print(f"Could not extract report from {file_path}: {error}")
            traceback.print_exc()
            return ({}, pd.DataFrame())

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str = ",",
        TOLERANCE: float = 6.0
    ) -> bool:
        """
        Validates the arithmetic integrity of the extracted vertical dataset.
        Checks both horizontal currency reconciliations (sum of currencies == TOTAL)
        and vertical hierarchy reconciliations, grouped by department (nv1) and date.
        Returns False when all checks pass, and True if discrepancies are found.
        """
        try:
            if dataframe is None or dataframe.empty:
                return False

            df = dataframe.copy()

            if df['valor'].dtype == object:
                df['valor'] = df['valor'].astype(str).str.replace(
                    decimal_separator, '.', regex=False
                )
                df['valor'] = pd.to_numeric(df['valor'], errors='coerce')

            df = df.dropna(subset=['valor'])

            # 1. Horizontal reconciliation: currencies sum to TOTAL per concept, entity, dept
            df_currencies = df[df['nv7'] != 'TOTAL']
            df_totals = df[df['nv7'] == 'TOTAL']

            if not df_currencies.empty and not df_totals.empty:
                sum_currencies = df_currencies.groupby(
                    ['nv1', 'nv2', 'nv3', 'nv4', 'nv5', 'nv6', 'fecha'],
                    dropna=False
                )['valor'].sum().reset_index()
                sum_currencies.rename(columns={'valor': 'calc_total'}, inplace=True)

                merged_h = pd.merge(
                    sum_currencies,
                    df_totals,
                    on=['nv1', 'nv2', 'nv3', 'nv4', 'nv5', 'nv6', 'fecha'],
                    how='inner'
                )
                if not merged_h.empty:
                    merged_h['diff'] = (merged_h['calc_total'] - merged_h['valor']).abs()
                    if (merged_h['diff'] > TOLERANCE).any():
                        return True

            # 2. Vertical reconciliation: main accounts equal sum of direct sub-accounts per dept
            parent_pub = df[
                (df['nv2'] == 'OBLIGACIONES CON EL PÚBLICO') & (df['nv3'].isna())
            ]
            children_pub = df[
                (df['nv2'] == 'OBLIGACIONES CON EL PÚBLICO') &
                (df['nv3'].notna()) &
                (df['nv4'].isna())
            ]

            if not parent_pub.empty and not children_pub.empty:
                sum_pub = children_pub.groupby(
                    ['nv1', 'nv6', 'nv7', 'fecha']
                )['valor'].sum().reset_index()
                sum_pub.rename(columns={'valor': 'calc_pub'}, inplace=True)

                merged_v = pd.merge(
                    sum_pub,
                    parent_pub,
                    on=['nv1', 'nv6', 'nv7', 'fecha'],
                    how='inner'
                )
                if not merged_v.empty:
                    merged_v['diff'] = (merged_v['calc_pub'] - merged_v['valor']).abs()
                    if (merged_v['diff'] > TOLERANCE).any():
                        return True

            return False

        except Exception as error:
            print(f"Validation error encountered: {error}")
            traceback.print_exc()
            return True

Executor_D_BO_000000318_01 = D_BO_000000318_01
Robot = D_BO_000000318_01
