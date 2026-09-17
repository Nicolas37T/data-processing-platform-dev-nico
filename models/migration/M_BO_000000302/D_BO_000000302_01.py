"""Migration robot for report D_BO_000000302_01: Bmu-Ranking de Contingente (ASFI)."""

import re
from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000302_01(Migration_Base):
    """Migration robot for D_BO_000000302_01."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with metric and metric unit metadata based on nv3:
        - Total Contingente: metrica = 'moneda', unidad_metrica = 'BOB' (o miles de BOB)
        - % de Particip.: metrica = 'porcentaje', unidad_metrica = '%'
        - Lugar Ranking: metrica = 'posicion', unidad_metrica = 'puesto'
        - conversion_factor = 1
        """
        # Clean column names
        dataframe.columns = [re.sub(r"[\t\xa0]+", "", str(c)).strip() for c in dataframe.columns]

        # Standardize strings in hierarchy columns
        for col in dataframe.columns:
            if col not in ["valor", "fecha"]:
                dataframe[col] = dataframe[col].astype(str).str.strip()

        def get_metric(val: str) -> str:
            v = str(val).lower()
            if "%" in v or "particip" in v:
                return "porcentaje"
            elif "ranking" in v or "lugar" in v:
                return "posicion"
            elif "contingente" in v or "monto" in v:
                return "moneda"
            return "numero"

        def get_unit(val: str) -> str:
            v = str(val).lower()
            if "%" in v or "particip" in v:
                return "%"
            elif "ranking" in v or "lugar" in v:
                return "puesto"
            elif "contingente" in v or "monto" in v:
                return "BOB"
            return "unidades"

        # Insert 'metrica' and 'unidad_metrica' right before 'valor'
        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value=dataframe["nv3"].apply(get_metric))
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value=dataframe["nv3"].apply(get_unit))

        factor = 1

        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000302_01
