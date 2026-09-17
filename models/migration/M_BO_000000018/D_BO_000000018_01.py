"""Migration robot for report D_BO_000000018_01: Bolivia - Ventas de Cemento por Departamento (INE)."""

import re
from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000018_01(Migration_Base):
    """Migration robot for D_BO_000000018_01."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with metric and metric unit metadata.
        - metrica: 'volumen'
        - unidad_metrica: 'Tn'
        - conversion_factor: 1 (los datos vienen en toneladas métricas completas)
        """
        dataframe.columns = [re.sub(r"[\t\xa0]+", "", str(c)).strip() for c in dataframe.columns]

        for col in dataframe.columns:
            if col not in ["valor", "fecha"]:
                dataframe[col] = dataframe[col].astype(str).str.strip()

        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value="volumen")
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value="Tn")

        factor = 1
        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000018_01
