"""Migration robot for report D_BO_000000219_01: Tipos de Cambio."""

import re
from typing import Any, Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000219_01(Migration_Base):
    """Migration robot for D_BO_000000219_01."""

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
            nv5 = str(row.get('nv5', '')).lower()
            nv1 = str(row.get('nv1', '')).lower()
            if 'tasa' in nv5 or 'sofr' in nv1:
                return 'tasa'
            if 'o.t.f.' in nv5 or 'metales' in nv1:
                return 'precio'
            return 'tipo_cambio'

        def get_unit(row) -> str:
            nv5 = str(row.get('nv5', '')).lower()
            nv4 = str(row.get('nv4', '')).upper()
            if 'tasa' in nv5:
                return '%'
            if 'o.t.f.' in nv5:
                return 'USD/Oz'
            if 'd.e.g.' in nv5:
                return 'USD/SDR'
            if 'bs/usd' in nv5:
                return 'BOB/USD'
            if 'bs/ufv' in nv5:
                return 'BOB/UFV'
            if 'bs por unidad' in nv5:
                return f'BOB/{nv4}'
            if 'm.e.' in nv5:
                return f'{nv4}/USD'
            return 'BOB/USD'

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


Robot = D_BO_000000219_01
