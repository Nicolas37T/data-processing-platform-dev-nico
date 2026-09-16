"""Migration robot for report D_BO_000000250_01: Pronostico Diario y Datos Meteorologicos."""

import re
from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000250_01(Migration_Base):
    """Migration robot for D_BO_000000250_01."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with metric and metric unit metadata based on nv4.
        Standardizes nv4 and clean texts.
        - Temperatura -> metrica = 'temperatura', unidad_metrica = '°C'
        - Precipitacion -> metrica = 'precipitacion', unidad_metrica = 'mm'
        - Humedad -> metrica = 'porcentaje', unidad_metrica = '%'
        - Viento -> metrica = 'velocidad', unidad_metrica = 'km/h'
        - conversion_factor = 1
        """
        # Clean column names
        dataframe.columns = [re.sub(r"[\t\xa0]+", "", str(c)).strip() for c in dataframe.columns]

        # Standardize text in string columns
        for col in ["nv1", "nv2", "nv3", "nv4"]:
            if col in dataframe.columns:
                dataframe[col] = dataframe[col].astype(str).str.strip()

        # Clean corrupted characters in nv4 if present
        def clean_nv4(val: str) -> str:
            v = str(val).strip()
            if "temperatura" in v.lower():
                return "Temperatura [°C]"
            elif "precipita" in v.lower():
                return "Precipitación [mm]"
            elif "humedad" in v.lower():
                return "Humedad_relativa [%]"
            elif "viento" in v.lower():
                return "Velocidad_viento [km/h]"
            return v

        dataframe["nv4"] = dataframe["nv4"].apply(clean_nv4)

        if "titulo1" in dataframe.columns:
            dataframe["titulo1"] = dataframe["titulo1"].astype(str).str.strip()

        def get_metric(val: str) -> str:
            val_lower = str(val).lower()
            if "temperatura" in val_lower or "°c" in val_lower:
                return "temperatura"
            elif "precipita" in val_lower or "mm" in val_lower:
                return "precipitacion"
            elif "humedad" in val_lower or "%" in val_lower:
                return "porcentaje"
            elif "viento" in val_lower or "km/h" in val_lower:
                return "velocidad"
            return "numero"

        def get_unit(val: str) -> str:
            val_lower = str(val).lower()
            if "temperatura" in val_lower or "°c" in val_lower:
                return "°C"
            elif "precipita" in val_lower or "mm" in val_lower:
                return "mm"
            elif "humedad" in val_lower or "%" in val_lower:
                return "%"
            elif "viento" in val_lower or "km/h" in val_lower:
                return "km/h"
            return "unidades"

        # Insert 'metrica' and 'unidad_metrica' right before 'valor'
        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value=dataframe["nv4"].apply(get_metric))
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value=dataframe["nv4"].apply(get_unit))

        factor = 1

        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000250_01
