"""Migration robot for report D_BO_000000419_06: Tipos de cambio y valor de la UFV (BCB)."""

import re
from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000419_06(Migration_Base):
    """Migration robot for D_BO_000000419_06."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with metric and metric unit metadata.
        - Tipos de cambio / UFV: metrica = 'tipo_cambio' o 'indice', factor = 1
        """
        # Clean column names
        dataframe.columns = [re.sub(r"[\t\xa0]+", "", str(c)).strip() for c in dataframe.columns]

        # Standardize strings in hierarchy columns
        for col in ["titulo1", "nv1", "nv2"]:
            if col in dataframe.columns:
                dataframe[col] = dataframe[col].astype(str).str.strip()

        def get_metric(val: str) -> str:
            v = str(val).lower()
            if "ufv" in v:
                return "indice"
            return "tipo_cambio"

        def get_unit(val: str) -> str:
            v = str(val).lower()
            if "ufv" in v:
                return "BOB/UFV"
            return "BOB/USD"

        # Insert 'metrica' and 'unidad_metrica' right before 'valor'
        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value=dataframe["nv2"].apply(get_metric))
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value=dataframe["nv2"].apply(get_unit))

        factor = 1

        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000419_06
