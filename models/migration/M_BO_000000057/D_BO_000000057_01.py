"""Migration robot for report D_BO_000000057_01: Informacion de Fondos de Inversion."""

import re
from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000057_01(Migration_Base):
    """Migration robot for D_BO_000000057_01."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with clean column names and metric metadata.
        - nv1 == 'Porcentaje' -> metrica = 'porcentaje', unidad_metrica = '%'
        - nv1 == 'Total' -> metrica = 'moneda', unidad_metrica = 'BOB'
        - conversion_factor = 1
        """
        # Limpiar caracteres de espacio / tabs no estandar en nombres de columnas
        clean_cols = {}
        for col in dataframe.columns:
            cleaned = re.sub(r"[\t\xa0]+", "", str(col)).strip()
            if cleaned.lower() == "emisor":
                clean_cols[col] = "emisor"
            else:
                clean_cols[col] = cleaned
        dataframe = dataframe.rename(columns=clean_cols)

        # Insertar metrica y unidad_metrica antes de 'valor'
        idx_valor = dataframe.columns.get_loc("valor")

        def get_metric(val):
            val_str = str(val).lower()
            if "porcentaje" in val_str or "%" in val_str:
                return "porcentaje"
            return "moneda"

        def get_unit(val):
            val_str = str(val).lower()
            if "porcentaje" in val_str or "%" in val_str:
                return "%"
            return "BOB"

        dataframe.insert(idx_valor, column="metrica", value=dataframe["nv1"].apply(get_metric))
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value=dataframe["nv1"].apply(get_unit))

        factor = 1

        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000057_01
