import os
import traceback
import pandas as pd
import numpy as np

from models.conversion.Conversion_Base import Conversion_Base


class D_BO_000000250_01(Conversion_Base):
    """
    Type III Conversion Robot for Ticket D_BO_000000250_01.
    Processes daily weather forecast data, transforming a wide Excel format
    into a strict vertical (melted) structure following DATAX rules.
    """

    def extraction(
        self, 
        file_path: str, 
        key_words: str, 
        template_path: str = "", 
        page_number: int = 1, 
        format: str = '%Y-%m-%d'
    ) -> tuple:
        """
        Reads the Excel file, melts the weather measurement columns into 
        'nv4' and 'valor', and structures it according to DATAX rules.
        """
        del template_path, key_words
        try:
            df_raw = pd.read_excel(file_path)

            id_vars = ['Departamento', 'Estacion', 'Estado_Cielo', 'Fecha']
            value_vars = [
                'Temperatura [°C]', 
                'Precipitación [mm]', 
                'Humedad_Relativa [%]', 
                'Velocidad_Viento [Km/h]'
            ]

            present_id_vars = [col for col in id_vars if col in df_raw.columns]
            present_val_vars = [col for col in value_vars if col in df_raw.columns]

            df_melted = pd.melt(
                df_raw,
                id_vars=present_id_vars,
                value_vars=present_val_vars,
                var_name='nv4',
                value_name='valor'
            )

            df_melted = df_melted.rename(columns={
                'Departamento': 'nv1',
                'Estacion': 'nv2',
                'Estado_Cielo': 'nv3',
                'Fecha': 'fecha'
            })

            # Ensure all standard columns exist
            for col in ['nv1', 'nv2', 'nv3', 'nv4']:
                if col not in df_melted.columns:
                    df_melted[col] = '-'

            df_melted = df_melted[['nv1', 'nv2', 'nv3', 'nv4', 'fecha', 'valor']]
            df_melted['fecha'] = pd.to_datetime(df_melted['fecha']).dt.strftime(format)
            df_melted['valor'] = pd.to_numeric(df_melted['valor'], errors='coerce')
            df_melted['valor'] = df_melted['valor'].replace({np.nan: pd.NA})

            for col in ['nv1', 'nv2', 'nv3', 'nv4']:
                df_melted[col] = df_melted[col].astype(str).str.strip()

            file_name = os.path.basename(file_path)
            metadata_dict = {
                "file_name": file_name,
                "titles": ["Datos en Tiempo Real - Pronóstico Diario"],
                "page_number": int(page_number)
            }

            return metadata_dict, df_melted

        except Exception as error:
            print(f"Could not extract report from {file_path}: {error}")
            traceback.print_exc()
            return ""

    def validate_data_results(
        self, 
        dataframe: pd.DataFrame, 
        decimal_separator: str, 
        TOLERANCE: float = 6.0
    ) -> bool:
        """
        Validates the integrity of extracted numerical data.
        Returns False as there are no printed totals in the source file to validate against.
        """
        del decimal_separator, TOLERANCE
        try:
            return False
        except Exception as error:
            print(f"Validation error: {error}")
            traceback.print_exc()
            return True


# Compatibility alias
Robot = D_BO_000000250_01
