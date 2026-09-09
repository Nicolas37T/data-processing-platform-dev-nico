"""Conversion robot for investment fund historical data."""

import re
import struct
import traceback
from pathlib import Path

import pandas as pd
import xlrd

from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import to_numeric_datax


class D_BO_000000058_01(Conversion_Base):
    """Convert and consolidate investment fund historical reports."""

    def extraction(
        self,
        file_path,
        key_words,
        template_path="",
        page_number=1,
        format="%Y-%m-%d",
    ):
        del template_path

        try:
            if int(page_number) < 1:
                raise ValueError("Page number must be greater than zero.")

            normalized_keywords = str(key_words or "").strip().lower()
            if normalized_keywords not in {"", "none"}:
                expected_terms = {"evolutivo", "fondos", "inversion"}
                if not any(
                    term in normalized_keywords for term in expected_terms
                ):
                    raise ValueError(
                        "The configured keywords do not match the report."
                    )

            if isinstance(file_path, dict):
                supplied_items = [file_path]
            elif isinstance(file_path, (list, tuple, set)):
                supplied_items = list(file_path)
            else:
                supplied_items = [file_path]

            source_paths = []
            for item in supplied_items:
                if isinstance(item, dict):
                    item = item.get("tmp_path") or item.get("file_path")
                if not item:
                    continue

                source_path = Path(str(item))
                if source_path.is_dir():
                    source_paths.extend(
                        sorted(
                            path
                            for path in source_path.iterdir()
                            if path.is_file()
                            and path.suffix.lower() in {".xls", ".xlsx"}
                        )
                    )
                    continue

                if not source_path.is_file():
                    raise FileNotFoundError(
                        f"Source file does not exist: {source_path}"
                    )
                if source_path.suffix.lower() not in {".xls", ".xlsx"}:
                    raise ValueError(
                        f"Unsupported file extension: {source_path.suffix}"
                    )

                source_paths.append(source_path)
                if len(supplied_items) == 1:
                    batch_match = re.match(
                        r"^(.*_de_)[^)]+(\))\.(?:xls|xlsx)$",
                        source_path.name,
                        flags=re.IGNORECASE,
                    )
                    if batch_match:
                        prefix = batch_match.group(1).lower()
                        ending = batch_match.group(2).lower()
                        source_paths.extend(
                            sorted(
                                sibling
                                for sibling in source_path.parent.iterdir()
                                if sibling.is_file()
                                and sibling.suffix.lower()
                                in {".xls", ".xlsx"}
                                and sibling.stem.lower().startswith(prefix)
                                and sibling.stem.lower().endswith(ending)
                            )
                        )

            unique_paths = []
            seen_paths = set()
            for source_path in source_paths:
                path_key = str(source_path.absolute()).casefold()
                if path_key not in seen_paths:
                    seen_paths.add(path_key)
                    unique_paths.append(source_path)
            unique_paths.sort(key=lambda path: path.name.casefold())

            if not unique_paths:
                raise ValueError("No investment fund files were found.")

            canonical_headers = [
                "Serie",
                "Fecha",
                "Valor Cuota",
                "Cuota Vigente",
                "Participantes",
                "Tasa Último Día",
                "Tasa Últimos 30 Días",
                "Tasa Últimos 90 Días",
                "Tasa Últimos 180 Días",
                "Tasa Últimos 360 Días",
                "Tasa Efectiva Anual",
                "Total Liquidez",
                "Cartera Neta",
                "Cartera Bruta",
                "Moneda",
            ]
            metric_columns = canonical_headers[2:-1]
            decimal_places = [2, 2, 0, 4, 4, 4, 4, 4, 2, 2, 2, 2]
            normalized_frames = []
            found_page_number = None

            for source_path in unique_paths:
                worksheet_frames = []
                if source_path.suffix.lower() == ".xlsx":
                    workbook_frames = pd.read_excel(
                        source_path,
                        sheet_name=None,
                        header=None,
                        dtype=object,
                    )
                    worksheet_frames = list(workbook_frames.values())
                else:
                    try:
                        workbook = xlrd.open_workbook(
                            source_path,
                            formatting_info=True,
                        )
                    except xlrd.compdoc.CompDocError:
                        content = bytearray(source_path.read_bytes())
                        if content[:8] != bytes.fromhex(
                            "D0CF11E0A1B11AE1"
                        ):
                            raise

                        sector_size = 1 << struct.unpack_from(
                            "<H", content, 30
                        )[0]
                        fat_count = struct.unpack_from(
                            "<I", content, 44
                        )[0]
                        first_directory_sector = struct.unpack_from(
                            "<I", content, 48
                        )[0]
                        fat_sectors = list(
                            struct.unpack_from("<109I", content, 76)
                        )
                        fat_sectors = [
                            sector
                            for sector in fat_sectors
                            if sector < 0xFFFFFFFA
                        ][:fat_count]

                        fat = []
                        for fat_sector in fat_sectors:
                            offset = 512 + fat_sector * sector_size
                            fat.extend(
                                struct.unpack_from(
                                    f"<{sector_size // 4}I",
                                    content,
                                    offset,
                                )
                            )

                        directory_sectors = []
                        visited_sectors = set()
                        sector = first_directory_sector
                        while sector < 0xFFFFFFFA:
                            if sector in visited_sectors:
                                raise ValueError(
                                    "Invalid directory sector chain."
                                )
                            visited_sectors.add(sector)
                            directory_sectors.append(sector)
                            sector = fat[sector]

                        directory = b"".join(
                            content[
                                512 + sector * sector_size:
                                512 + (sector + 1) * sector_size
                            ]
                            for sector in directory_sectors
                        )
                        workbook_entry = None
                        for entry_index in range(len(directory) // 128):
                            entry_offset = entry_index * 128
                            name_length = struct.unpack_from(
                                "<H", directory, entry_offset + 64
                            )[0]
                            stream_name = directory[
                                entry_offset:
                                entry_offset + max(name_length - 2, 0)
                            ].decode("utf-16le", errors="ignore")
                            if stream_name in {"Workbook", "Book"}:
                                workbook_entry = (
                                    entry_index,
                                    struct.unpack_from(
                                        "<I",
                                        directory,
                                        entry_offset + 116,
                                    )[0],
                                )
                                break

                        if workbook_entry is None:
                            raise ValueError(
                                "The Workbook stream was not found."
                            )

                        entry_index, workbook_sector = workbook_entry
                        workbook_sectors = []
                        visited_sectors = set()
                        while workbook_sector < 0xFFFFFFFA:
                            if workbook_sector in visited_sectors:
                                raise ValueError(
                                    "Invalid Workbook sector chain."
                                )
                            visited_sectors.add(workbook_sector)
                            workbook_sectors.append(workbook_sector)
                            workbook_sector = fat[workbook_sector]

                        directory_offset = entry_index * 128 + 120
                        directory_index = directory_offset // sector_size
                        sector_offset = directory_offset % sector_size
                        physical_offset = (
                            512
                            + directory_sectors[directory_index]
                            * sector_size
                            + sector_offset
                        )
                        repaired_size = (
                            len(workbook_sectors) * sector_size
                        )
                        struct.pack_into(
                            "<Q", content, physical_offset, repaired_size
                        )
                        workbook = xlrd.open_workbook(
                            file_contents=bytes(content),
                            formatting_info=True,
                        )

                    worksheet_frames = [
                        pd.DataFrame(
                            [
                                sheet.row_values(row_index)
                                for row_index in range(sheet.nrows)
                            ]
                        )
                        for sheet in workbook.sheets()
                    ]

                if not worksheet_frames:
                    raise ValueError(
                        f"No worksheets were found in {source_path.name}."
                    )

                start_index = int(page_number) - 1
                sheet_indexes = list(
                    range(start_index, len(worksheet_frames))
                ) + list(range(0, min(start_index, len(worksheet_frames))))
                table = None
                current_page_number = None
                for sheet_index in sheet_indexes:
                    raw_dataframe = worksheet_frames[sheet_index]
                    for row_index, row in raw_dataframe.iterrows():
                        row_text = " ".join(
                            re.sub(r"\s+", " ", str(value)).strip()
                            for value in row.dropna()
                        ).upper()
                        if all(
                            term in row_text
                            for term in ("SERIE", "FECHA", "VALOR CUOTA")
                        ):
                            if raw_dataframe.shape[1] < len(
                                canonical_headers
                            ):
                                raise ValueError(
                                    "The source table has fewer columns than "
                                    "expected."
                                )
                            table = raw_dataframe.iloc[
                                row_index + 1:,
                                :len(canonical_headers),
                            ].copy()
                            table.columns = canonical_headers
                            current_page_number = sheet_index + 1
                            break
                    if table is not None:
                        break

                if table is None:
                    raise ValueError(
                        f"The fund table was not found in {source_path.name}."
                    )

                table = table.loc[
                    table["Serie"].notna() & table["Fecha"].notna()
                ].copy()
                table["Serie"] = (
                    table["Serie"].astype(str).str.strip()
                )
                table = table.loc[table["Serie"].ne("")].copy()
                if table.empty:
                    raise ValueError(
                        f"No fund records were found in {source_path.name}."
                    )

                if pd.api.types.is_numeric_dtype(table["Fecha"]):
                    parsed_dates = pd.to_datetime(
                        table["Fecha"],
                        unit="D",
                        origin="1899-12-30",
                        errors="coerce",
                    )
                else:
                    parsed_dates = pd.to_datetime(
                        table["Fecha"],
                        errors="coerce",
                    )
                if parsed_dates.isna().any():
                    raise ValueError(
                        f"Invalid report dates in {source_path.name}."
                    )
                table["Fecha"] = parsed_dates.dt.strftime(format)

                for metric, precision in zip(
                    metric_columns, decimal_places
                ):
                    table[metric] = to_numeric_datax(
                        table[metric],
                        ".",
                    ).round(precision)
                    if table[metric].isna().any():
                        raise ValueError(
                            f"Invalid values in {metric} from "
                            f"{source_path.name}."
                        )

                normalized_frame = (
                    table.set_index(["Serie", "Fecha"])[metric_columns]
                    .stack(future_stack=True)
                    .rename("valor")
                    .reset_index()
                    .rename(columns={"level_2": "nv2"})
                ).rename(
                    columns={"Serie": "nv1", "Fecha": "fecha"}
                )
                normalized_frame["nv1"] = normalized_frame["nv1"].astype(
                    str
                )
                normalized_frame["nv2"] = normalized_frame["nv2"].astype(
                    str
                )
                normalized_frame["fecha"] = normalized_frame[
                    "fecha"
                ].astype(str)
                normalized_frames.append(
                    normalized_frame[["nv1", "nv2", "fecha", "valor"]]
                )
                if found_page_number is None:
                    found_page_number = current_page_number

            dataframe = pd.concat(normalized_frames, ignore_index=True)
            duplicate_keys = ["nv1", "nv2", "fecha"]
            conflicting_values = (
                dataframe.groupby(duplicate_keys, dropna=False)["valor"]
                .nunique(dropna=False)
                .gt(1)
                .any()
            )
            if conflicting_values:
                raise ValueError(
                    "Conflicting values were found for the same fund, "
                    "metric, and date."
                )
            dataframe = dataframe.drop_duplicates(
                subset=duplicate_keys,
                keep="first",
                ignore_index=True,
            )

            if dataframe.empty:
                raise ValueError("No normalized fund data was generated.")

            first_source = unique_paths[0].name
            metadata = {
                "file_name": first_source,
                "titles": ["EVOLUTIVO FONDOS DE INVERSIÓN"],
                "page_number": int(found_page_number or 1),
            }
            return metadata, dataframe

        except Exception as error:
            print(f"Could not extract report from {file_path}: {error}")
            traceback.print_exc()
            return ""

    def validate_data_results(
        self,
        dataframe,
        decimal_separator,
        TOLERANCE=6.0,
    ):
        """Validate the normalized investment fund values."""
        del decimal_separator, TOLERANCE
        try:
            if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return True

            required_columns = {"nv1", "nv2", "fecha", "valor"}
            if not required_columns.issubset(dataframe.columns):
                return True
            if dataframe[list(required_columns)].isna().any().any():
                return True
            if dataframe.duplicated(
                subset=["nv1", "nv2", "fecha"]
            ).any():
                return True

            parsed_dates = pd.to_datetime(
                dataframe["fecha"],
                format="%Y-%m-%d",
                errors="coerce",
            )
            if parsed_dates.isna().any():
                return True

            return False

        except Exception as error:
            print(f"Could not validate the investment fund report: {error}")
            traceback.print_exc()
            return True


Robot = D_BO_000000058_01
