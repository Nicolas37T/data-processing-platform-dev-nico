"""Migration robot for report D_BO_000000019_01: Consumo de Cemento por Departamento (INE)."""

import re
from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000019_01(Migration_Base):
    """Migration robot for D_BO_000000019_01."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Standardize report dataframe for D_BO_000000019_01.

        Metric: consumo
        Metric Unit: TM (Toneladas Métricas)
        Conversion Factor: 1 (valores ya vienen en toneladas métricas completas)
        """
        # Limpieza de nombres de columnas
        dataframe.columns = [re.sub(r"[\t\xa0]+", "", str(c)).strip() for c in dataframe.columns]

        # Limpiar strings en columnas categóricas
        for col in dataframe.columns:
            if col not in ["valor", "fecha"]:
                dataframe[col] = dataframe[col].astype(str).str.strip()

        # Insertar metrica y unidad_metrica inmediatamente antes de 'valor'
        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value="consumo")
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value="TM")

        factor = 1

        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000019_01
