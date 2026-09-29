"""Migration robot for report D_BO_000000079_01: Cuentas Monetarias de Bancos (BCB)."""

import re
from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000079_01(Migration_Base):
    """Migration robot for D_BO_000000079_01."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with metric and metric unit metadata.
        Report: Cuentas Monetarias de Bancos (En millones de bolivianos).
        """
        # Clean column names
        dataframe.columns = [re.sub(r"[\t\xa0]+", "", str(c)).strip() for c in dataframe.columns]

        # Standardize strings in hierarchy and text columns
        for col in dataframe.columns:
            if col not in ["valor", "fecha"]:
                dataframe[col] = dataframe[col].where(dataframe[col].notna(), None)
                dataframe[col] = dataframe[col].apply(lambda x: str(x).strip() if x is not None else None)

        metric_type = "moneda"
        metric_unit = "BOB"
        factor = int(conversion_factor) if conversion_factor else 1000000

        # Insert 'metrica' and 'unidad_metrica' right before 'valor'
        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value=metric_type)
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value=metric_unit)

        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000079_01
