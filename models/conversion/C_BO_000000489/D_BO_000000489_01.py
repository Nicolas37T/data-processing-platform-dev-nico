"""Conversion robot for report D_BO_000000489_01.

Code: D_BO_000000489_01
Name: Precios Pizarra - Bolsa de Comercio de Rosario
Page: 1
Periodicity: Daily
Decimal Separator: ,
Conversion Factor: 1
"""

import os
import traceback
from typing import Any, Dict, Tuple, Union

import pandas as pd
from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import to_numeric_datax


class D_BO_000000489_01(Conversion_Base):
    """Conversion robot for report D_BO_000000489_01."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> Union[Tuple[Dict[str, Any], pd.DataFrame], str]:
        del template_path, key_words
        try:
            if not os.path.isfile(file_path):
                print(f"File not found: {file_path}")
                return ""

            df = pd.read_excel(file_path)

            if df.empty:
                print(f"DataFrame is empty for {file_path}")
                return ""

            col_map = {}
            for col in df.columns:
                col_u = str(col).strip().upper()
                if "PROD" in col_u or "NV1" in col_u:
                    col_map[col] = "nv1"
                elif "ESTIM" in col_u or "NV2" in col_u or "SPEC" in col_u or "DESCRIP" in col_u:
                    col_map[col] = "nv2"
                elif "FECHA" in col_u:
                    col_map[col] = "fecha"
                elif "PRECIO" in col_u or "VALOR" in col_u or "MONTO" in col_u:
                    col_map[col] = "valor"

            df = df.rename(columns=col_map)

            for c in ["nv1", "nv2", "fecha", "valor"]:
                if c not in df.columns:
                    if c == "nv2":
                        df["nv2"] = ""
                    else:
                        print(f"Missing required column '{c}' in {file_path}")
                        return ""

            df_final = df[["nv1", "nv2", "fecha", "valor"]].copy()

            df_final["nv1"] = df_final["nv1"].astype(str).str.strip()
            df_final["nv2"] = df_final["nv2"].fillna("").astype(str).str.strip()
            df_final["nv2"] = df_final["nv2"].replace({"nan": "", "None": "", "-": ""})

            df_final["fecha"] = pd.to_datetime(df_final["fecha"]).dt.strftime(format)

            df_final["valor"] = to_numeric_datax(
                serie=df_final["valor"], decimal_separator=","
            )

            df_final = df_final.dropna(subset=["valor"])

            metadata = {
                "file_name": os.path.basename(file_path),
                "titles": ["CÁMARA ARBITRAL DE CEREALES - BCR", "PRECIOS ESTIMATIVOS"],
                "page_number": int(page_number) if int(page_number) > 0 else 1,
            }

            return (metadata, df_final)

        except Exception as error:
            print(f"Could not extract report from {file_path}: {error}")
            traceback.print_exc()
            return ""

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str = ",",
        TOLERANCE: float = 6.0,
    ) -> bool:
        del decimal_separator, TOLERANCE
        try:
            if dataframe is None or (
                isinstance(dataframe, pd.DataFrame) and dataframe.empty
            ):
                return False
            return False
        except Exception:
            traceback.print_exc()
            return True


# Alias for compatibility
Robot = D_BO_000000489_01
