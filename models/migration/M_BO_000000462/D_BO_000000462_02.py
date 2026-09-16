"""Migration robot for report D_BO_000000462_02: Precios de Insumos Avícolas (ADA SCZ)."""

import re
from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000462_02(Migration_Base):
    """Migration robot for D_BO_000000462_02."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with metric and metric unit metadata based on nv4.
        nv4 contains currency/unit (e.g. 'Bs./Kg.', '$us./Tn.', 'Bs./Tn.')
        - conversion_factor = 1
        """
        # Clean column names
        dataframe.columns = [re.sub(r"[\t\xa0]+", "", str(c)).strip() for c in dataframe.columns]

        # Standardize strings in hierarchy columns
        for col in ["titulo1", "nv1", "nv2", "nv3", "nv4"]:
            if col in dataframe.columns:
                dataframe[col] = dataframe[col].astype(str).str.strip()

        def get_metric(val: str) -> str:
            return "moneda"

        def get_unit(val: str) -> str:
            v = str(val).lower()
            if "$us" in v or "usd" in v:
                return "USD/Tn" if "tn" in v else "USD"
            elif "bs" in v or "bob" in v:
                return "BOB/Tn" if "tn" in v else ("BOB/kg" if "kg" in v else "BOB")
            return "BOB"

        # Insert 'metrica' and 'unidad_metrica' right before 'valor'
        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value=dataframe["nv4"].apply(get_metric))
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value=dataframe["nv4"].apply(get_unit))

        factor = 1

        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000462_02
