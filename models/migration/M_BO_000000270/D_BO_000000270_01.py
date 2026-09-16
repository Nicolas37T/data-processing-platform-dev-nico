"""Migration robot for report D_BO_000000270_01: Saldo de la Deuda Publica Interna del TGN (En Bs.)."""

from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000270_01(Migration_Base):
    """Migration robot for D_BO_000000270_01."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with metric and metric unit metadata,
        and define the conversion factor (1,000,000 to convert millions to complete BOB units).
        """
        metric_type = "moneda"
        metric_unit = "BOB"
        factor = 1000000

        # Insert 'metrica' and 'unidad_metrica' right before 'valor'
        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value=metric_type)
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value=metric_unit)

        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000270_01
