"""Migration robot for report D_BO_000000047_01: Variacion 12 Meses IGAE."""

from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000047_01(Migration_Base):
    """Migration robot for D_BO_000000047_01."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with metric and metric unit metadata,
        and define the conversion factor (1 for variation percentage rates).
        """
        metric_type = "tasa"
        metric_unit = "%"
        factor = 1

        # Insert 'metrica' and 'unidad_metrica' right before 'valor'
        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value=metric_type)
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value=metric_unit)

        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000047_01
