"""Migration robot for report D_BO_000000577_01: BCB Cotizaciones de Plata."""

from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000577_01(Migration_Base):
    """Migration robot for D_BO_000000577_01."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with metric and metric unit metadata.
        For silver quotations:
        - Dollar quotations ('DOLAR' or 'USD' in nv1) -> unidad_metrica = 'USD'
        - Boliviano quotations ('Bs' in nv1) -> unidad_metrica = 'BOB'
        - metrica = 'moneda'
        - conversion_factor = 1 (values are already in direct quotation units)
        """
        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value="moneda")

        def get_unit(nv1_str: str) -> str:
            val = str(nv1_str).upper()
            if "DOLAR" in val or "USD" in val:
                return "USD"
            elif "BS" in val or "BOLIVIANO" in val:
                return "BOB"
            return "BOB"

        dataframe.insert(idx_valor + 1, column="unidad_metrica", value=dataframe["nv1"].apply(get_unit))

        factor = 1

        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000577_01
