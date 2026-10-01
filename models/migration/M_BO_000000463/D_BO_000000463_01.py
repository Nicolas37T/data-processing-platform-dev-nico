"""Migration robot for report D_BO_000000463_01: Reservas Internacionales Netas del Banco Central de Bolivia."""

import re
from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000463_01(Migration_Base):
    """Migration robot for D_BO_000000463_01."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with clean columns and metric metadata.
        - metrica: 'moneda'
        - unidad_metrica: 'USD'
        - conversion_factor: 1000000
        """
        dataframe.columns = [re.sub(r"[\t\xa0]+", "", str(c)).strip() for c in dataframe.columns]

        for col in dataframe.columns:
            if col not in ["valor", "fecha"]:
                dataframe[col] = dataframe[col].apply(
                    lambda x: str(x).strip() if pd.notna(x) and str(x).strip().lower() not in ["none", "nan", ""] else None
                )

        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value="moneda")
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value="USD")

        dataframe["valor"] = pd.to_numeric(
            dataframe["valor"].astype(str).str.replace(",", ".", regex=False),
            errors="coerce"
        )

        try:
            factor_val = int(conversion_factor) if conversion_factor is not None else 1000000
        except (ValueError, TypeError):
            factor_val = 1000000

        if factor_val <= 1 and 1000000 > 1:
            factor_val = 1000000

        if factor_val > 1 and "moneda" == "moneda":
            dataframe["valor"] = dataframe["valor"] * factor_val

        return ({"conversion_factor": factor_val}, dataframe)


Robot = D_BO_000000463_01
