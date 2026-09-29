from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import traceback
import pandas as pd
import numpy as np
from models.download.tools.download_tools import read_excel
from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000494_01(Conversion_Base):

    def extraction(self, file_path, key_words, template_path, page_number, format='%Y-%m-%d'):
        """
        Extracts a table from a file using user-defined keywords to locate the report section.
        The extraction follows the DATAX Conversion Manual: metadata columns (file_name, titles) are returned separately.
        The DataFrame is only cleaned selectively: fully empty rows/columns are removed, but cell values are not normalized or formatted.
        
        Parameters:
        - file_path (str): Absolute path to the file to extract from
        - key_words (str): Keywords to locate the report section
        - template_path (str): Path to a template file for validation/structure
        - page_number (int): Reference page number for faster search
        - format (str, optional): Date format. Default: '%Y-%m-%d'
        
        Returns:
        - tuple: (metadata_dict, dataframe) or empty string on error
        """
        file_name = os.path.basename(file_path)
        try:
            # Load Excel file
            df = read_excel(file_name=file_path)
            # Remove fully empty rows and columns
            df = df.dropna(how='all').dropna(axis=1, how='all').reset_index(drop=True)

            # Extract date from filename
            fecha_match = re.search(r"\d{4}-\d{2}-\d{2}", file_name)
            fecha = fecha_match.group(0) if fecha_match else ""

            # Hardcoded titles for this report type
            titles = [
                "OFERTA DIARIA DE POTENCIA (MW)",
                f"Despacho de carga del {fecha}" if fecha else "Despacho de carga"
            ]

            # Find the header row (row with numbers 1, 2, 3, ... representing hours)
            header_row_idx = None
            for i, row in df.iterrows():
                numeric_values = []
                for j, val in enumerate(row.values):
                    if pd.notna(val) and j > 0:  # Skip first column
                        try:
                            num_val = float(val)
                            if 1 <= num_val <= 24 and abs(num_val - round(num_val)) < 0.01:
                                numeric_values.append(int(round(num_val)))
                        except (ValueError, TypeError):
                            pass
                if len(numeric_values) >= 10 and 1 in numeric_values and 2 in numeric_values:
                    header_row_idx = i
                    break

            if header_row_idx is None:
                raise ValueError('Header row with hours (1, 2, 3, ...) not found')

            # Extract hour values from header row (columns 1 onwards)
            horas = []
            for val in df.iloc[header_row_idx].values[1:25]:
                if pd.notna(val):
                    try:
                        hora_num = int(round(float(val)))
                        if 1 <= hora_num <= 24:
                            horas.append(str(hora_num))
                    except:
                        import traceback; traceback.print_exc()
                        pass

            # Data starts in the next row after header
            data_start = header_row_idx + 1

            # Find where data ends (look for rows with category names and numeric values)
            data_end = data_start
            for i in range(data_start, len(df)):
                row = df.iloc[i]
                first_col = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                if not first_col:
                    break
                has_numeric = False
                for j in range(1, min(len(horas) + 1, len(row))):
                    val = row.iloc[j]
                    if pd.notna(val):
                        try:
                            float(val)
                            has_numeric = True
                            break
                        except:
                            import traceback; traceback.print_exc()
                            pass
                if has_numeric:
                    data_end = i + 1
                else:
                    break

            # Extract the data rows, preserving original cell values
            registros = []
            for idx in range(data_start, data_end):
                row = df.iloc[idx]
                row_name = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                if not row_name:
                    continue
                for hora_idx, hora in enumerate(horas, start=1):
                    if hora_idx < len(row):
                        valor = row.iloc[hora_idx]
                        if pd.notna(valor):
                            registros.append({
                                "tipo": row_name,
                                "hora": hora,
                                "fecha": fecha,
                                "valor": valor
                            })

            if len(registros) == 0:
                raise ValueError("No data records were extracted")

            # Build DataFrame, drop only nulls in 'valor'
            df_final = pd.DataFrame(registros)
            df_final = df_final[df_final['valor'].notna()].reset_index(drop=True)

            # Return metadata and cleaned DataFrame
            return ({
                "file_name": file_name,
                "titles": titles,
                "page_number": page_number
            }, df_final)

        except Exception as e:
            print(f"An error occurred: {e}")
            traceback.print_exc()
            return ""
    
    def validate_data_results(self, dataframe: pd.DataFrame, decimal_separator: str, TOLERANCE: float = 6.0):
        """
        Validates the integrity of extracted power data according to DATAX Conversion Manual.
        This function converts textual values to numeric using the specified decimal separator,
        removes rows with null numeric values, and applies specific business validations:
        - OFERTA BRUTA must be greater than OFERTA NETA for each hour.
        - SINCRONIZADA must be greater than GENERADA for each hour.
        No total/subtotal/percentage validation is performed, as the XLSX does not contain such data.
        
        Parameters:
            dataframe (pd.DataFrame): DataFrame with extracted data.
            decimal_separator (str): Decimal separator ('.' or ',').
            TOLERANCE (float, optional): Acceptable margin of error. Default is 6.0.
        
        Returns:
            bool: True if any validation failed or inconsistencies were found, False otherwise.
        """
        try:
            if dataframe.empty:
                print("Validation failed: DataFrame is empty.")
                return True

            dataframe = dataframe.copy()

            # Convert 'valor' column to numeric and drop rows with nulls
            dataframe['valor'] = to_numeric_datax(serie=dataframe['valor'], decimal_separator=decimal_separator)
            dataframe = dataframe[dataframe['valor'].notna()].reset_index(drop=True)

            if dataframe.empty:
                print("Validation failed: No valid numeric data found.")
                return True

            # Pivot table for validation by hour and type
            pivot = dataframe.pivot_table(index='hora', columns='tipo', values='valor', aggfunc='first')

            errors = []

            # Validation: OFERTA BRUTA must be greater than OFERTA NETA
            if 'OFERTA BRUTA' in pivot.columns and 'OFERTA NETA' in pivot.columns:
                for hora in pivot.index:
                    bruta = pivot.at[hora, 'OFERTA BRUTA']
                    neta = pivot.at[hora, 'OFERTA NETA']
                    if pd.notna(bruta) and pd.notna(neta):
                        if bruta <= neta:
                            errors.append(
                                f"OFERTA BRUTA ({bruta:.2f} MW) is not greater than OFERTA NETA ({neta:.2f} MW) at hour {hora}"
                            )

            # Validation: SINCRONIZADA must be greater than GENERADA
            if 'SINCRONIZADA' in pivot.columns and 'GENERADA' in pivot.columns:
                for hora in pivot.index:
                    sincro = pivot.at[hora, 'SINCRONIZADA']
                    generada = pivot.at[hora, 'GENERADA']
                    if pd.notna(sincro) and pd.notna(generada):
                        if sincro <= generada:
                            errors.append(
                                f"SINCRONIZADA ({sincro:.2f} MW) is not greater than GENERADA ({generada:.2f} MW) at hour {hora}"
                            )

            # Print validation errors if any
            if errors:
                print("VALIDATION ERRORS:")
                for err in errors:
                    print(f"  ERROR: {err}")
                return True

            print("All validations passed successfully.")
            return False

        except Exception as e:
            print(f"Validation error: {e}")
            traceback.print_exc()
            return True

Executor_D_BO_000000494_01 = D_BO_000000494_01
Robot = D_BO_000000494_01
