"""Migration robot for report D_BO_000000255_01: Precios de Pollo, Gallina y Huevos (ADASCZ)."""

import re
from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000255_01(Migration_Base):
    """Migration robot for D_BO_000000255_01."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with metric and metric unit metadata.
        - Pollo / Gallina: metrica = 'moneda', unidad_metrica = 'BOB/kg'
        - Huevo: metrica = 'moneda', unidad_metrica = 'BOB'
        - conversion_factor = 1
        """
        # Clean column names from hidden or trailing whitespace characters
        dataframe.columns = [re.sub(r"[\t\xa0]+", "", str(c)).strip() for c in dataframe.columns]

        # Standardize strings in hierarchy columns
        for col in ["titulo1", "nv1", "nv2", "nv3"]:
            if col in dataframe.columns:
                dataframe[col] = dataframe[col].astype(str).str.strip()

        def get_metric(row) -> str:
            return "moneda"

        def get_unit(row) -> str:
            nv1_lower = str(row.get("nv1", "")).lower()
            if "kg" in nv1_lower or "vivo" in nv1_lower or "descarte" in nv1_lower:
                return "BOB/kg"
            return "BOB"

        # Insert 'metrica' and 'unidad_metrica' right before 'valor'
        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value=dataframe.apply(get_metric, axis=1))
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value=dataframe.apply(get_unit, axis=1))

        factor = 1

        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000255_01
