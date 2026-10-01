"""Migration robot for report D_BO_000000043_01: Cocoa Daily Prices."""

import re
from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000043_01(Migration_Base):
    """Migration robot for D_BO_000000043_01."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with metric and metric unit metadata (Generado con Agente Inteligente DATAX).
        """
        dataframe.columns = [re.sub(r"[\t\xa0]+", "", str(c)).strip() for c in dataframe.columns]

        for col in dataframe.columns:
            if col not in ["valor", "fecha"]:
                dataframe[col] = dataframe[col].apply(
                    lambda x: str(x).strip() if pd.notna(x) and str(x).strip().lower() not in ["none", "nan", ""] else None
                )

        def get_metric(row) -> str:
            return 'precio'

        def get_unit(row) -> str:
            combined = ' '.join([str(v) for v in row.values if pd.notna(v)]).lower()
            if 'euro' in combined or 'eur' in combined or '€' in combined:
                return 'EUR/Tn'
            if '£' in combined or 'sterling' in combined:
                return 'GBP/Tn'
            if any(k in combined for k in ['us$', '$us', 'usd']):
                return 'USD/Tn'
            return 'USD/Tn'

        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value=dataframe.apply(get_metric, axis=1))
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value=dataframe.apply(get_unit, axis=1))

        dataframe["valor"] = pd.to_numeric(
            dataframe["valor"].astype(str).str.replace(",", ".", regex=False),
            errors="coerce"
        )

        try:
            factor_val = float(conversion_factor) if conversion_factor is not None else 1.0
        except (ValueError, TypeError):
            factor_val = 1.0

        if factor_val <= 1.0 and 1.0 > 1.0:
            factor_val = 1.0

        if factor_val > 1.0:
            mask_moneda = dataframe["metrica"] == "moneda"
            dataframe.loc[mask_moneda, "valor"] = dataframe.loc[mask_moneda, "valor"] * factor_val

        return ({"conversion_factor": 1}, dataframe)


Robot = D_BO_000000043_01
