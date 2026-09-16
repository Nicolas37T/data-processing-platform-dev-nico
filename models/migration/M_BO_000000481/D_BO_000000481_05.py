"""Migration robot for report D_BO_000000481_05: Montos Negociados en Bolsa - Resumen Diario (BBV)."""

import re
from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000481_05(Migration_Base):
    """Migration robot for D_BO_000000481_05."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with metric and metric unit metadata based on nv5.
        - Part % / participacion: metrica = 'porcentaje', unidad_metrica = '%'
        - Monto / negociado: metrica = 'moneda', unidad_metrica = 'USD'
        - conversion_factor = 1
        """
        dataframe.columns = [re.sub(r"[\t\xa0]+", "", str(c)).strip() for c in dataframe.columns]

        for col in ["titulo1", "nv1", "nv2", "nv3", "nv4", "nv5"]:
            if col in dataframe.columns:
                dataframe[col] = dataframe[col].astype(str).str.strip()

        def get_metric(val: str) -> str:
            v = str(val).lower()
            if "%" in v or "part" in v:
                return "porcentaje"
            return "moneda"

        def get_unit(val: str) -> str:
            v = str(val).lower()
            if "%" in v or "part" in v:
                return "%"
            return "USD"

        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value=dataframe["nv5"].apply(get_metric))
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value=dataframe["nv5"].apply(get_unit))

        factor = 1

        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000481_05
