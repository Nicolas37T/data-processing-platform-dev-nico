datax-pds@plat-dev-server:~$ ls
CopiaBaseDatos  datax  mongo-panel  yes  yes.pub
datax-pds@plat-dev-server:~$ cd datax/
datax-pds@plat-dev-server:~/datax$ ls
Archivo_Prueba_SSD.xlsx           data-processing-platform-dev   data_migration_db_tool
data-processin-platform-template  data-processing-platform-prod  datax-pipeline-monitor
datax-pds@plat-dev-server:~/datax$ cd data-processing-platform-dev/
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev$ ls
AIRFLOW3_MIGRATION.md  Dockerfile  config  data    docker-compose.yaml  logs    platform_db.backup  requirements.txt
CLAUDE.md              README.md   dags    docker  include              models  plugins
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev$ cd models/
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev/models$ ls
conversion  download  migration  product  tools
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev/models$ cd conversion/
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev/models/conversion$ ls
C_BO_000000017  C_BO_000000250  C_BO_000000418  C_BO_000000481  C_BO_000000487  C_BO_000000572  Conversion_Base.py  tools
C_BO_000000057  C_BO_000000255  C_BO_000000419  C_BO_000000484  C_BO_000000489  C_BO_000000573  __pycache__
C_BO_000000058  C_BO_000000270  C_BO_000000462  C_BO_000000485  C_BO_000000568  C_BO_000000577  tests
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev/models/conversion$ cd C_BO_000000017/

datax-pds@plat-dev-server:~/datax/data-processing-platform-dev/models/conversion/C_BO_000000017$ sudo nano D_BO_000000017_01.py
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev/models/conversion/C_BO_000000017$ cat D_BO_000000017_01.py
"""Robot for D_BO_000000017_01: Bolivia - Producción de Cemento por Departamento según Año y Mes.

Fuente: INE (Instituto Nacional de Estadística)
"""
import datetime
import os
import re
import traceback
from typing import Tuple, Union

import pandas as pd

from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import (
    extract_report_df,
    get_xlsx_report_dataframe,
    to_numeric_datax,
)
from models.download.tools.download_tools import last_day_month, month_to_number


class D_BO_000000017_01(Conversion_Base):
    """Robot de conversión para D_BO_000000017_01."""

    def extraction(
        self,
        file_path: str,
        key_words: str,
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d"
    ) -> Union[Tuple[dict, pd.DataFrame], str]:
        """
        Extrae la tabla de producción de cemento del archivo XLSX.

        Args:
            file_path (str): Ruta al archivo Excel descargado.
            key_words (str): Palabras clave para ubicar la hoja/tabla.
            template_path (str, optional): Ruta de la plantilla previa. Defaults to "".
            page_number (int, optional): Número de página/hoja inicial. Defaults to 1.
            format (str, optional): Formato de fecha esperado. Defaults to "%Y-%m-%d".

        Returns:
            Union[Tuple[dict, pd.DataFrame], str]: Metadatos y DataFrame con columnas [nv1, fecha, valor], o "" si falla.
        """
        try:
            # 1. Retrieve the sheet dataframe using existing conversion_tools
            result = get_xlsx_report_dataframe(
                file_path=file_path,
                key_words=key_words,
                page_number=page_number
            )
            if result is None:
                raise ValueError(
                    f"Could not find table matching keywords in {file_path}"
                )

            table_df, detected_page = result

            # 2. Extract titles and split table starting from the header pivot
            splited_df, titles = extract_report_df(
                table_df,
                pivot_keywords="periodo"
            )

            # Department columns are in row 0, from index 1 to the end
            header_row = splited_df.iloc[0]
            dept_cols = [str(col).strip() for col in header_row.iloc[1:]]

            # 3. Iterate through rows to extract monthly records
            records = []
            current_year = None

            for idx in range(1, len(splited_df)):
                cell_val = splited_df.iloc[idx, 0]
                if pd.isna(cell_val):
                    continue

                cell_str = str(cell_val).strip()

                if "fuente" in cell_str.lower():
                    break

                month_num = month_to_number(cell_str.lower())
                year_match = re.search(r"(\d{4})", cell_str)

                if month_num is None and year_match:
                    current_year = int(year_match.group(1))
                    continue

                if month_num is not None and current_year is not None:
                    day = last_day_month(year=current_year, month=month_num)
                    date_val = datetime.date(current_year, month_num, day)
                    fecha_str = date_val.strftime(format)

                    for c_idx, dept in enumerate(dept_cols):
                        val = splited_df.iloc[idx, c_idx + 1]
                        records.append({
                            "nv1": dept,
                            "fecha": fecha_str,
                            "valor": val
                        })

            report_df = pd.DataFrame(records)

            file_name = os.path.basename(file_path)
            report_dict = {
                "file_name": file_name,
                "titles": titles,
                "page_number": detected_page
            }

            return report_dict, report_df

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
        Valida que la suma de los componentes coincida con el total impreso.

        Args:
            dataframe (pd.DataFrame): DataFrame con metadatos y valores.
            decimal_separator (str): Separador decimal usado en el reporte.
            TOLERANCE (float, optional): Tolerancia permitida en la diferencia. Defaults to 6.0.

        Returns:
            bool: True si hay error/discrepancia, False si la validación es exitosa.
        """
        numeric_series = to_numeric_datax(dataframe["valor"], decimal_separator)
        temp_df = dataframe.copy()
        temp_df["_numeric_valor"] = numeric_series

        # Find the categorical column containing 'TOTAL'
        exclude_cols = {"valor", "_numeric_valor", "fecha", "file"}
        cat_cols = [
            col for col in temp_df.columns
            if col not in exclude_cols and not str(col).startswith("titulo")
        ]

        total_col = None
        for col in cat_cols:
            is_total_mask = (
                temp_df[col].astype(str).str.strip().str.upper() == "TOTAL"
            )
            if is_total_mask.any():
                total_col = col
                break

        # If no total column exists, there are no printed totals to validate
        if not total_col:
            return False

        # Group by date to compare printed totals against calculated sums
        total_mask = (
            temp_df[total_col].astype(str).str.strip().str.upper() == "TOTAL"
        )
        totals = temp_df[total_mask].groupby("fecha")["_numeric_valor"].sum()
        components = (
            temp_df[~total_mask].groupby("fecha")["_numeric_valor"].sum()
        )

        comparison = pd.concat(
            [totals.rename("total_printed"), components.rename("total_calc")],
            axis=1
        ).dropna()

        discrepancies = (
            comparison["total_printed"] - comparison["total_calc"]
        ).abs()

        has_error = (discrepancies > TOLERANCE).any()
        if has_error:
            failed = comparison[discrepancies > TOLERANCE]
            print(f"Validation failed for dates:\n{failed}")

        return bool(has_error)
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev/models/conversion/C_BO_000000017$ ls
D_BO_000000017_01.py

datax-pds@plat-dev-server:~/datax/data-processing-platform-dev/models/conversion/C_BO_000000017$ docker exec -it data-processing-platform-dev-airflow-worker
-1 python include/main-generate.py
[INFO] === DAG Generator ===
[INFO] Choose a process to generate DAGs for:
1. Download
2. Conversion
3. Migration
4. Product
5. Cancel
>> 2
[SUCCESS] Selected: CONVERSION
[INFO] Selected process: CONVERSION
[INFO] Choose an option:
1. Enter robot code(s) separated by ';'
2. Process ALL available robots
3. Cancel
>> 1
Enter code(s):
>> C_BO_000000017
[SUCCESS] Valid codes to be processed: ['C_BO_000000017']
[SUCCESS] Generated: /opt/airflow/dags/conversion/C_BO_000000017.py
[SUCCESS] Done! 1 DAG(s) generated.

# aqui ejecute este cimando para iniciar por consola el proceso de conversion en airflow

 docker exec data-processing-platform-dev-airflow-worker-1 airflow dags trigger C_BO_000000017 --conf '{"code": "D_BO_000000017_01", "id_download": 218, "file": "\\\\10.0.0.16\\downloaded_files\\BO\\D_BO_000000017\\2026"}'
2026-09-15T15:36:59.996571Z [info     ] setup plugin alembic.autogenerate.schemas [alembic.runtime.plugins] loc=plugins.py:37
2026-09-15T15:36:59.996696Z [info     ] setup plugin alembic.autogenerate.tables [alembic.runtime.plugins] loc=plugins.py:37
2026-09-15T15:36:59.996752Z [info     ] setup plugin alembic.autogenerate.types [alembic.runtime.plugins] loc=plugins.py:37
2026-09-15T15:36:59.996795Z [info     ] setup plugin alembic.autogenerate.constraints [alembic.runtime.plugins] loc=plugins.py:37
2026-09-15T15:36:59.996835Z [info     ] setup plugin alembic.autogenerate.defaults [alembic.runtime.plugins] loc=plugins.py:37
2026-09-15T15:36:59.996876Z [info     ] setup plugin alembic.autogenerate.comments [alembic.runtime.plugins] loc=plugins.py:37
2026-09-15T15:37:00.543413Z [info     ] creating dag run               [airflow.serialization.definitions.dag] loc=dag.py:526 logical_date=None partition_key=None run_after=datetime.datetime(2026, 9, 15, 15, 37, 0, 212936, tzinfo=Timezone('UTC')) run_id=manual__2026-09-15T15:37:00.212936+00:00
                    |                |                    | data_interval_star |                   |          | last_scheduling_de |              |          |            |        | triggering_user_nam
conf                | dag_id         | dag_run_id         | t                  | data_interval_end | end_date | cision             | logical_date | run_type | start_date | state  | e
====================+================+====================+====================+===================+==========+====================+==============+==========+============+========+====================
{'code':            | C_BO_000000017 | manual__2026-09-15 | None               | None              | None     | None               | None         | manual   | None       | queued | airflow
'D_BO_000000017_01' |                | T15:37:00.212936+0 |                    |                   |          |                    |              |          |            |        |
, 'id_download':    |                | 0:00               |                    |                   |          |                    |              |          |            |        |
218, 'file':        |                |                    |                    |                   |          |                    |              |          |            |        |
'\\\\10.0.0.16\\dow |                |                    |                    |                   |          |                    |              |          |            |        |
nloaded_files\\BO\\ |                |                    |                    |                   |          |                    |              |          |            |        |
D_BO_000000017\\202 |                |                    |                    |                   |          |                    |              |          |            |        |
6'}                 |                |                    |                    |                   |          |                    |              |          |            |        |


# la subida del sql
datax-pds@plat-dev-server:~$ cd /mnt/
datax-pds@plat-dev-server:/mnt$ ls
datax  datos1
datax-pds@plat-dev-server:/mnt$ cd datos1/
datax-pds@plat-dev-server:/mnt/datos1$ ls
data_process  downloaded_files  lost+found  spim  taiga_back_up
datax-pds@plat-dev-server:/mnt/datos1$ cd data_process/
datax-pds@plat-dev-server:/mnt/datos1/data_process$ ls
BO  BR  CL  PE  PY
datax-pds@plat-dev-server:/mnt/datos1/data_process$ cd BO
datax-pds@plat-dev-server:/mnt/datos1/data_process/BO$ ls
D_BO_000000057  D_BO_000000250  D_BO_000000270  D_BO_000000419  D_BO_000000481  D_BO_000000487  D_BO_000000568  D_BO_000000573
D_BO_000000058  D_BO_000000255  D_BO_000000418  D_BO_000000462  D_BO_000000485  D_BO_000000489  D_BO_000000572  D_BO_000000577
datax-pds@plat-dev-server:/mnt/datos1/data_process/BO$ sudo mkdir D_BO_000000017
[sudo: authenticate] Password:
datax-pds@plat-dev-server:/mnt/datos1/data_process/BO$ ls
D_BO_000000017  D_BO_000000058  D_BO_000000255  D_BO_000000418  D_BO_000000462  D_BO_000000485  D_BO_000000489  D_BO_000000572  D_BO_000000577
D_BO_000000057  D_BO_000000250  D_BO_000000270  D_BO_000000419  D_BO_000000481  D_BO_000000487  D_BO_000000568  D_BO_000000573
datax-pds@plat-dev-server:/mnt/datos1/data_process/BO$ sudo chmod 777 D_BO_000000017/
datax-pds@plat-dev-server:/mnt/datos1/data_process/BO$ ls -la D_BO_000000017/
total 8
drwxrwxrwx  2 root      root      4096 Sep 15 10:59 .
drwxrwxrwx 19 datax-pds datax-pds 4096 Sep 15 10:59 ..
datax-pds@plat-dev-server:/mnt/datos1/data_process/BO$ cd D_BO_000000017/
datax-pds@plat-dev-server:/mnt/datos1/data_process/BO/D_BO_000000017$ ls
datax-pds@plat-dev-server:/mnt/datos1/data_process/BO/D_BO_000000017$ ls
D_BO_000000017_01.sqlite