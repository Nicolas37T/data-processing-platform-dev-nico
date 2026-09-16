"""Migration robot for report D_BO_000000572_01: Inyecciones de Energía y Costo Marginal (CNDC)."""

import re
from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000572_01(Migration_Base):
    """Migration robot for D_BO_000000572_01."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with metric and metric unit metadata based on nv2:
        - Inyección / Energía: metrica = 'energia', unidad_metrica = 'MWh'
        - Costo Marginal: metrica = 'costo_marginal', unidad_metrica = 'USD/MWh'
        - conversion_factor = 1
        """
        # Clean column names
        dataframe.columns = [re.sub(r"[\t\xa0]+", "", str(c)).strip() for c in dataframe.columns]

        # Standardize strings in hierarchy columns
        for col in ["titulo1", "nv1", "nv2", "nv3"]:
            if col in dataframe.columns:
                dataframe[col] = dataframe[col].astype(str).str.strip()

        def get_metric(val: str) -> str:
            v = str(val).lower()
            if "costo" in v or "marginal" in v or "us$" in v:
                return "costo_marginal"
            return "energia"

        def get_unit(val: str) -> str:
            v = str(val).lower()
            if "costo" in v or "marginal" in v or "us$" in v:
                return "USD/MWh"
            return "MWh"

        # Insert 'metrica' and 'unidad_metrica' right before 'valor'
        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value=dataframe["nv2"].apply(get_metric))
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value=dataframe["nv2"].apply(get_unit))

        factor = 1

        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000572_01
