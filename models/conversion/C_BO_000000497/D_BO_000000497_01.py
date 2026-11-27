from models.conversion.Conversion_Base import Conversion_Base
import os
import traceback
import pandas as pd
from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000497_01(Conversion_Base):

    def extraction(self, file_path, key_words, template_path="", page_number=1, format='%Y-%m-%d'):
        """
        Extrae datos de tasas prime desde el archivo Excel generado por la descarga.
        """
        file_name = os.path.basename(file_path)

        try:
            # El archivo generado por la descarga es un libro de Excel (.xlsx)
            df = pd.read_excel(file_path, header=None)

            # Localizar la fila de encabezados de datos ('Date' / 'Values')
            date_mask = df[0].astype(str).str.lower().str.strip() == 'date'
            if not date_mask.any():
                raise ValueError("No se encontró la cabecera 'Date' en el archivo Excel")
            
            date_idx = df[date_mask].index[0]

            # Extraer títulos previos a 'Date'
            raw_titles = df.iloc[:date_idx, 0].dropna().tolist()
            titles_clean = [str(t).strip() for t in raw_titles if str(t).strip()]

            metadata_titles = [titles_clean[0]] if titles_clean else ['Prime Rate']
            nv1_name = titles_clean[1] if len(titles_clean) > 1 else (titles_clean[0] if titles_clean else 'Operaciones en US dólares')

            # Extraer filas de datos
            df_data = df.iloc[date_idx + 1:].copy()
            df_data.columns = ['fecha', 'valor']

            # Formatear fecha y filtrar filas válidas
            df_data['fecha'] = pd.to_datetime(df_data['fecha']).dt.strftime(format)
            df_data = df_data.dropna(subset=['fecha', 'valor']).copy()

            # Normalizar valores numéricos
            df_data['valor'] = to_numeric_datax(serie=df_data['valor'], decimal_separator=',')
            df_data['nv1'] = nv1_name

            df_melted = df_data[['nv1', 'fecha', 'valor']].reset_index(drop=True)

            return ({
                "file_name": file_name,
                "titles": metadata_titles,
                "page_number": int(page_number)
            }, df_melted)

        except ValueError as e:
            print(f"Validation error: {e}")
            traceback.print_exc()                        
        except Exception as e:            
            print(f"An error ocurred: {e}")            
            traceback.print_exc()
        return ""
    
    def validate_data_results(self, dataframe: pd.DataFrame, decimal_separator: str = ",", TOLERANCE: float = 6.0) -> bool:
        """
        Valida que el DataFrame contenga datos numéricos válidos.
        Retorna False si la validación es exitosa, True si detecta error.
        """
        try:
            cleaned_df = dataframe.copy()
            cleaned_df['valor'] = to_numeric_datax(serie=cleaned_df['valor'], decimal_separator=decimal_separator)
            cleaned_df = cleaned_df.dropna(subset=['valor'])

            if cleaned_df.empty:
                print("Error: DataFrame vacío tras limpieza de valores.")
                return True

            print("All validations passed. Returning False (Validación exitosa).")
            return False
        except Exception as e:
            print(f"Error en validación: {e}")
            return True

Executor_D_BO_000000497_01 = D_BO_000000497_01
Robot = D_BO_000000497_01

Robot = D_BO_000000497_01
