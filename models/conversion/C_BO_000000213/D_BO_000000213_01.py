# Pega aquí el código del pasante o cárgalo desde GitHub...
from models.conversion.Conversion_Base import Conversion_Base
"""Convert departmental hospital admission and discharge pivot tables."""

import os
import re
from typing import Tuple

import pandas as pd
import xlrd

from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000213_01(Conversion_Base):
    """Consolidate nine departmental workbooks into one conversion."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> Tuple[dict, pd.DataFrame]:
        """Extract and consolidate the nine departmental pivot tables."""

        def normalize_text(value) -> str:
            """Return stable text without altering source labels."""
            if value is None:
                return ""
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return re.sub(r"\s+", " ", str(value)).strip()

        def normalized_header(value) -> str:
            """Normalize structural headers used as table anchors."""
            return normalize_text(value).upper()

        def parse_file_identity(path: str) -> Tuple[str, str, str]:
            """Read date, department code, and family from a file name."""
            stem = os.path.splitext(os.path.basename(path))[0]
            stem = re.sub(
                r"\s+D_BO_\d+_\d+$",
                "",
                stem,
                flags=re.IGNORECASE,
            )
            identity = re.match(
                r"^(20\d{2}-\d{2}-\d{2})[_-]([A-Za-z]{2})[_-](.+)$",
                stem,
            )
            if not identity:
                raise ValueError(
                    "The file name must include date, department code, "
                    "and report name."
                )
            report_date, department_code, report_family = identity.groups()
            try:
                pd.to_datetime(
                    report_date,
                    format="%Y-%m-%d",
                    errors="raise",
                )
            except ValueError as exc:
                raise ValueError("The report date is invalid.") from exc
            report_family = re.sub(
                r"\s+",
                " ",
                report_family.replace("_", " "),
            ).strip().casefold()
            return report_date, department_code.casefold(), report_family

        def extract_department(
            department_path: str,
            report_date: str,
        ) -> Tuple[list, pd.DataFrame]:
            """Extract one source workbook using structural anchors."""
            workbook = xlrd.open_workbook(
                department_path,
                formatting_info=True,
            )
            sheet = None
            header_row = None
            required_headers = {
                "SEDES",
                "MES",
                "SEMANA",
                "SUBSECTOR",
                "VARIABLE",
            }

            for candidate in workbook.sheets():
                for row_idx in range(min(candidate.nrows, 25)):
                    row_headers = {
                        normalized_header(
                            candidate.cell_value(row_idx, col_idx)
                        )
                        for col_idx in range(candidate.ncols)
                    }
                    if required_headers.issubset(row_headers):
                        sheet = candidate
                        header_row = row_idx
                        break
                if sheet is not None:
                    break

            if sheet is None or header_row is None:
                raise ValueError(
                    "The admissions and discharges table was not found in "
                    f"{os.path.basename(department_path)}."
                )

            value_col = None
            for col_idx in range(sheet.ncols - 1, -1, -1):
                header = normalized_header(
                    sheet.cell_value(header_row, col_idx)
                )
                if header.startswith("TOTAL_GRAL"):
                    value_col = col_idx
                    break

            if value_col is None:
                raise ValueError(
                    "The numeric TOTAL_GRAL column was not found in "
                    f"{os.path.basename(department_path)}."
                )

            dimension_cols = [
                col_idx
                for col_idx in range(value_col)
                if normalized_header(
                    sheet.cell_value(header_row, col_idx)
                )
            ]
            if len(dimension_cols) != 15:
                raise ValueError(
                    "The report must contain exactly 15 hierarchy columns."
                )

            titles = []
            for row_idx in range(header_row):
                row_parts = []
                for col_idx in range(sheet.ncols):
                    text = normalize_text(
                        sheet.cell_value(row_idx, col_idx)
                    )
                    if text and text not in row_parts:
                        row_parts.append(text)
                if row_parts:
                    titles.append(" ".join(row_parts))

            dimension_positions = {
                col_idx: position
                for position, col_idx in enumerate(dimension_cols)
            }
            horizontal_subtotals = {}
            for row_low, row_high, col_low, col_high in sheet.merged_cells:
                covered_cols = [
                    col_idx
                    for col_idx in dimension_cols
                    if col_low <= col_idx < col_high
                ]
                if row_high - row_low == 1 and len(covered_cols) > 1:
                    horizontal_subtotals[row_low] = covered_cols[0]

            current_levels = [""] * len(dimension_cols)
            records = []

            for row_idx in range(header_row + 1, sheet.nrows):
                raw_value = sheet.cell_value(row_idx, value_col)
                if not normalize_text(raw_value):
                    if any(
                        normalize_text(
                            sheet.cell_value(row_idx, col_idx)
                        )
                        for col_idx in dimension_cols
                    ):
                        raise ValueError(
                            "Non-numeric value found at Excel row "
                            f"{row_idx + 1}."
                        )
                    continue

                raw_levels = [
                    normalize_text(sheet.cell_value(row_idx, col_idx))
                    for col_idx in dimension_cols
                ]
                changed_positions = [
                    position
                    for position, text in enumerate(raw_levels)
                    if text
                ]
                if not changed_positions:
                    raise ValueError(
                        "Hierarchy not found at Excel row "
                        f"{row_idx + 1}."
                    )

                first_change = changed_positions[0]
                current_levels[first_change:] = [""] * (
                    len(current_levels) - first_change
                )
                for position in changed_positions:
                    current_levels[position] = raw_levels[position]

                output_levels = current_levels.copy()
                subtotal_col = horizontal_subtotals.get(row_idx)
                if subtotal_col is not None:
                    subtotal_position = dimension_positions[subtotal_col]
                    output_levels[subtotal_position + 1:] = [None] * (
                        len(output_levels) - subtotal_position - 1
                    )
                    if subtotal_position == len(output_levels) - 2:
                        output_levels[subtotal_position] = re.sub(
                            r"\s+Total$",
                            "",
                            output_levels[subtotal_position],
                            flags=re.IGNORECASE,
                        ).strip()
                        output_levels[-1] = "Total"

                output_levels = [
                    level if level else None for level in output_levels
                ]
                record = {
                    f"nv{position + 1}": level
                    for position, level in enumerate(output_levels)
                }
                record["fecha"] = report_date
                record["valor"] = raw_value
                records.append(record)

            columns = [f"nv{position}" for position in range(1, 16)]
            columns.extend(["fecha", "valor"])
            dataframe = pd.DataFrame(records, columns=columns)
            if dataframe.empty:
                raise ValueError(
                    "The report does not contain numeric records in "
                    f"{os.path.basename(department_path)}."
                )

            dataframe["valor"] = to_numeric_datax(
                dataframe["valor"],
                decimal_separator=",",
            )
            if dataframe["valor"].isna().any():
                raise ValueError(
                    "Some report values could not be converted in "
                    f"{os.path.basename(department_path)}."
                )
            return titles, dataframe

        file_name = os.path.basename(file_path)
        report_date, _, report_family = parse_file_identity(file_path)
        source_dir = os.path.dirname(os.path.abspath(file_path))
        files_by_department = {}

        for entry in os.scandir(source_dir):
            if not entry.is_file() or not entry.name.lower().endswith(".xls"):
                continue
            try:
                candidate_date, department_code, candidate_family = (
                    parse_file_identity(entry.path)
                )
            except ValueError:
                continue
            if (
                candidate_date != report_date
                or candidate_family != report_family
            ):
                continue
            if department_code in files_by_department:
                raise ValueError(
                    "More than one source file was found for department "
                    f"code '{department_code}'."
                )
            files_by_department[department_code] = entry.path

        if len(files_by_department) != 9:
            raise ValueError(
                "Exactly 9 departmental source files are required; "
                f"{len(files_by_department)} were found."
            )

        titles = None
        department_names = set()
        department_frames = []

        for department_path in sorted(files_by_department.values()):
            source_titles, department_df = extract_department(
                department_path,
                report_date,
            )
            if titles is None:
                titles = source_titles
            elif source_titles != titles:
                raise ValueError(
                    "The source files do not share the same report titles."
                )

            detail_roots = department_df.loc[
                ~department_df["nv1"].str.lower().str.endswith(
                    " total",
                    na=False,
                ),
                "nv1",
            ].unique()
            if len(detail_roots) != 1:
                raise ValueError(
                    "Each source file must contain exactly one department."
                )
            department_names.add(detail_roots[0])
            department_frames.append(department_df)

        if len(department_names) != 9:
            raise ValueError(
                "The source files do not contain 9 unique departments."
            )

        dataframe = pd.concat(department_frames, ignore_index=True)
        key_cols = [f"nv{position}" for position in range(1, 16)]
        key_cols.append("fecha")
        if dataframe.duplicated(key_cols).any():
            raise ValueError(
                "Duplicate hierarchy and date keys were found after "
                "consolidation."
            )

        metadata_dict = {
            "file_name": file_name,
            "titles": titles or [],
            "page_number": int(page_number),
        }
        return metadata_dict, dataframe

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str = ",",
        TOLERANCE: float = 6.0,
    ) -> bool:
        """Validate schema, uniqueness, completeness, and service totals."""
        try:
            level_cols = [f"nv{position}" for position in range(1, 16)]
            required_cols = level_cols + ["fecha", "valor"]
            if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return True
            if not set(required_cols).issubset(dataframe.columns):
                return True

            data = dataframe.loc[:, required_cols].copy()
            if data[["nv1", "fecha", "valor"]].isna().any().any():
                return True
            if data[["nv1", "fecha"]].apply(
                lambda column: column.astype(str).str.strip().eq("").any()
            ).any():
                return True
            if data.duplicated(level_cols + ["fecha"]).any():
                return True

            parsed_dates = pd.to_datetime(
                data["fecha"], format="%Y-%m-%d", errors="coerce"
            )
            if parsed_dates.isna().any():
                return True
            if not parsed_dates.dt.is_month_end.all():
                return True
            if data["fecha"].nunique() != 1:
                return True

            department_mask = ~data["nv1"].str.lower().str.endswith(
                " total",
                na=False,
            )
            departments = set(data.loc[department_mask, "nv1"].str.strip().str.upper().unique())
            if len(departments) != 9:
                return True

            grand_total_mask = data[level_cols[1:]].isna().all(axis=1)
            total_departments = set(
                data.loc[grand_total_mask, "nv1"].str.replace(
                    r"\s+Total$",
                    "",
                    regex=True,
                    flags=re.IGNORECASE,
                ).str.strip().str.upper()
            )
            if total_departments != departments:
                return True

            data["valor_num"] = to_numeric_datax(
                data["valor"], decimal_separator
            )
            if data["valor_num"].isna().any():
                return True

            service_totals = data[data["nv15"].eq("Total")]
            if service_totals.empty:
                return True

            group_cols = level_cols[:-1] + ["fecha"]
            details = data[
                ~data["nv15"].isin(["Total"])
                & data["nv15"].notna()
                & data["nv14"].notna()
            ]
            detail_sums = details.groupby(group_cols)["valor_num"].sum()
            service_sums = service_totals.groupby(group_cols)["valor_num"].sum()

            diff = (detail_sums - service_sums).abs().max()
            if pd.isna(diff) or diff > TOLERANCE:
                return True

            return False
        except Exception:
            import traceback; traceback.print_exc()
            return True

Executor_D_BO_000000213_01 = D_BO_000000213_01
Robot = D_BO_000000213_01
