"""Migration robot for report D_BO_000000419_01: Operaciones con el exterior (BCB)."""

import re
from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000419_01(Migration_Base):
    """Migration robot for D_BO_000000419_01."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with metric and metric unit metadata.
        Saldos y flujos en millones de USD:
        - metrica = 'moneda'
        - unidad_metrica = 'USD'
        - factor = 1,000,000 (para convertir millones de USD a USD completos)
        """
        # Clean column names
        dataframe.columns = [re.sub(r"[\t\xa0]+", "", str(c)).strip() for c in dataframe.columns]

        # Standardize strings in hierarchy columns
        for col in ["titulo1", "nv1", "nv2", "nv3", "nv4", "nv5"]:
            if col in dataframe.columns:
                dataframe[col] = dataframe[col].astype(str).str.strip()

        # Insert 'metrica' and 'unidad_metrica' right before 'valor'
        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value="moneda")
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value="USD")

        factor = 1000000

        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000419_01
