"""Migration robot for report D_BO_000000300_01: Bmu-ranking de Depósitos del Público y de Empresas Públicas."""

import re
from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000300_01(Migration_Base):
    """Migration robot for D_BO_000000300_01."""

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
            nv3 = str(row.get('nv3', '')).lower()
            if '%' in nv3 or 'particip' in nv3:
                return 'porcentaje'
            if 'lugar' in nv3 or 'ranking' in nv3:
                return 'indice'
            return 'moneda'

        def get_unit(row) -> str:
            nv3 = str(row.get('nv3', '')).lower()
            if '%' in nv3 or 'particip' in nv3:
                return '%'
            if 'lugar' in nv3 or 'ranking' in nv3:
                return 'unidad'
            return 'BOB'

        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value=dataframe.apply(get_metric, axis=1))
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value=dataframe.apply(get_unit, axis=1))

        dataframe["valor"] = pd.to_numeric(
            dataframe["valor"].astype(str).str.replace(",", ".", regex=False),
            errors="coerce"
        )

        try:
            factor_val = float(conversion_factor) if conversion_factor is not None else 1000.0
        except (ValueError, TypeError):
            factor_val = 1000.0

        if factor_val <= 1.0 and 1000.0 > 1.0:
            factor_val = 1000.0

        if factor_val > 1.0:
            mask_moneda = dataframe["metrica"] == "moneda"
            dataframe.loc[mask_moneda, "valor"] = dataframe.loc[mask_moneda, "valor"] * factor_val

        return ({"conversion_factor": 1}, dataframe)


Robot = D_BO_000000300_01
