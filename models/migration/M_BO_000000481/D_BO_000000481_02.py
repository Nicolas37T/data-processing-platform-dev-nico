"""Migration robot for report D_BO_000000481_02: Acciones Inscritas en Bolsa (BBV)."""

import re
from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000481_02(Migration_Base):
    """Migration robot for D_BO_000000481_02."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with metric and metric unit metadata.
        Columnas: nv1, nv2, emisor, fecha_inscripcion, tipo, fecha, valor
        - Capitalización / valor: metrica = 'moneda', unidad_metrica = 'BOB'
        - conversion_factor = 1
        """
        dataframe.columns = [re.sub(r"[\t\xa0]+", "", str(c)).strip() for c in dataframe.columns]

        for col in ["titulo1", "nv1", "nv2", "emisor", "fecha_inscripcion", "tipo"]:
            if col in dataframe.columns:
                dataframe[col] = dataframe[col].astype(str).str.strip()

        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value="moneda")
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value="BOB")

        factor = 1

        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000481_02
