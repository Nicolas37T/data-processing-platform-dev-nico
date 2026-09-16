"""Migration robot for report D_BO_000000481_01: Fondos de Inversión (Bolsa Boliviana de Valores)."""

import re
from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000481_01(Migration_Base):
    """Migration robot for D_BO_000000481_01."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with metric and metric unit metadata based on nv8.
        - Rendimientos: metrica = 'tasa', unidad_metrica = '%'
        - Cartera / Montos: metrica = 'moneda', unidad_metrica = 'USD' o 'BOB' (o 'unidades')
        - conversion_factor = 1
        """
        dataframe.columns = [re.sub(r"[\t\xa0]+", "", str(c)).strip() for c in dataframe.columns]

        for col in ["titulo1", "nv1", "nv2", "nv3", "nv4", "nv5", "nv6", "nv7", "nv8"]:
            if col in dataframe.columns:
                dataframe[col] = dataframe[col].astype(str).str.strip()

        def get_metric(val: str) -> str:
            v = str(val).lower()
            if "rend" in v or "%" in v or "tasa" in v:
                return "tasa"
            elif "cartera" in v or "monto" in v or "patrimonio" in v:
                return "moneda"
            return "numero"

        def get_unit(val: str) -> str:
            v = str(val).lower()
            if "rend" in v or "%" in v or "tasa" in v:
                return "%"
            return "unidades"

        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value=dataframe["nv8"].apply(get_metric))
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value=dataframe["nv8"].apply(get_unit))

        factor = 1

        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000481_01
