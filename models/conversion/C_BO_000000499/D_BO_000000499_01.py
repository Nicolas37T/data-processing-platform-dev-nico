from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import traceback
import pandas as pd
from models.conversion.tools.conversion_tools import get_xlsx_report_dataframe, get_date, to_numeric_datax

class D_BO_000000499_01(Conversion_Base):

    def extraction(self, file_path: str, key_words: str, template_path: str, page_number: int, format_date: str = "%Y-%m-%d"):
        """
        Extract and process hydrological data from Excel file maintaining 
        hierarchical structure.

        Parameters:
            file_path (str): Excel file path
            key_words (str): Keywords to search for data start
            template_path (str): Template path (currently unused)
            page_number (int): Sheet/page number
            format_date (str): Date format

        Returns:
            tuple: (metadata, dataframe) or empty string on error
        """
        try:
            file_name = os.path.basename(file_path)
            result = get_xlsx_report_dataframe(
                file_path, key_words, page_number)
            if not result:
                return ""

            raw_df, found_page = result
            clean_df = raw_df.dropna(how="all").dropna(
                axis=1, how="all").reset_index(drop=True)
            # Extract titles (first 4 rows) and date
            titles = [
                ' '.join([str(val) for val in clean_df.iloc[idx].dropna()
                         if str(val).strip() not in ['nan', '']]).strip()
                for idx in range(min(4, len(clean_df)))
                if ' '.join([str(val) for val in clean_df.iloc[idx].dropna()
                             if str(val).strip() not in ['nan', '']]).strip()
            ]

            date_extracted = get_date(file_name)
            data_df = clean_df.iloc[4:].reset_index(drop=True)

            # Find headers, units and subconcepts
            main_concepts, units, subconcepts, data_start_idx = [], [], [], 0

            for idx, row in data_df.iterrows():
                row_text = ' '.join([
                    str(val) for val in row.dropna()
                    if str(val).strip() not in ['nan', '']
                ]).strip()

                if any(keyword in row_text.upper()
                       for keyword in ['CAUDALES', 'CAPACIDAD', 'VOLUMENES']):
                    main_concepts = [
                        str(val).strip() for val in row.tolist()
                        if str(val).strip() not in ['nan', '']
                    ]

                    if idx + 1 < len(data_df):
                        units = [
                            str(val).strip() for val in data_df.iloc[idx + 1].tolist()
                            if str(val).strip() not in ['nan', '']
                        ]

                    data_start_idx = idx + 2
                    break

            # Find subconcepts
            if data_start_idx < len(data_df):
                subconcepts = [
                    str(val).strip() if not pd.isna(val) and str(
                        val).strip() not in ['nan', ''] else ""
                    for val in data_df.iloc[data_start_idx].tolist()
                ]
                if any(subconcepts):
                    data_start_idx += 1

            # Create dynamic column mapping
            column_mapping = [("MUNICIPALITY", "", "")]
            col_idx = 1

            for i, concept in enumerate(main_concepts):
                if concept and concept.strip():
                    unit = units[i] if i < len(units) else ""

                    if "VOLUMEN" in concept.upper() and col_idx < len(subconcepts):
                        while col_idx < len(subconcepts) and subconcepts[col_idx]:
                            column_mapping.append(
                                (concept, unit, subconcepts[col_idx]))
                            col_idx += 1
                    else:
                        column_mapping.append((concept, unit, ""))
                        col_idx += 1

            # Process data
            actual_data_df = data_df.iloc[data_start_idx:].reset_index(
                drop=True)
            result_rows = []
            current_nv1 = ""

            for idx, row in actual_data_df.iterrows():
                row_values = [val for val in row.tolist() if not pd.isna(val)]
                if not row_values:
                    continue

                first_col = str(row_values[0]).strip()

                if re.search(r'\bSISTEMA\b', first_col, re.IGNORECASE):
                    current_nv1 = first_col
                    continue

                if len(row_values) >= 2:
                    municipality = first_col
                    nv1, nv2 = (
                        (municipality, None)
                        if municipality.upper() in ['KANATA', 'SAN JACINTO']
                        else (current_nv1, municipality)
                    )

                    for col_idx, value in enumerate(row.tolist()[1:], 1):
                        if (not pd.isna(value) and str(value).strip() != ''
                                and col_idx < len(column_mapping)):
                            main_concept, unit, subconcept = column_mapping[col_idx]

                            result_rows.append({
                                'nv1': nv1,
                                'nv2': nv2,
                                'nv3': main_concept,
                                'nv4': unit,
                                'nv5': subconcept if subconcept else None,
                                'fecha': date_extracted,
                                'valor': value
                            })

            if result_rows:
                result_df = pd.DataFrame(result_rows)
                result_df = result_df.reindex(
                    columns=['nv1', 'nv2', 'nv3',
                             'nv4', 'nv5', 'fecha', 'valor']
                )

                metadata = {
                    "file_name": file_name,
                    "titles": [title for title in titles
                               if title.strip() and title.lower() != 'nan'],
                    "page_number": found_page
                }
                return (metadata, result_df)
            return ""

        except Exception as e:
            print(f"Error in extraction: {e}")
            traceback.print_exc()
            return ""

    def validate_data_results(self, dataframe: pd.DataFrame, decimal_separator: str, tolerance: float = 6.0) -> bool:
        """
        Validate data integrity and coherence according to DATAX Conversion Manual.

        Parameters:
            dataframe (pd.DataFrame): DataFrame structured according to DATAX 
            decimal_separator: Character representing decimal separator (e.g., '.' or ',')

        Returns:
            bool: True if any validation failed or inconsistencies detected,
                  False if all validations successful
        """
        try:
            # Convert values to numeric using specified decimal separator
            numeric_values = to_numeric_datax(
                dataframe['valor'], decimal_separator)

            # Verify all values are numeric
            if numeric_values.isna().any():
                print("Error: Non-numeric values found in 'valor' column")
                return True

            return False

        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"Error during validation: {e}")
            return True

Executor_D_BO_000000499_01 = D_BO_000000499_01
Robot = D_BO_000000499_01
