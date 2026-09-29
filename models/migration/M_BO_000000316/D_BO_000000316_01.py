"""Migration robot for report D_BO_000000316_01: Bancos Pyme - Financiamiento de Entidades del Exterior (ASFI)."""

import re
from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000316_01(Migration_Base):
    """Migration robot for D_BO_000000316_01."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with metric and metric unit metadata.
        - Porcentajes / Participación (% PASIVO, PARTICIPACIÓN):
            metrica = 'porcentaje', unidad_metrica = '%' (factor 1)
        - Ratios (Financ. Externo Directo / Patrimonio):
            metrica = 'ratio', unidad_metrica = 'veces' (factor 1)
        - Montos de financiamiento (PEF, PCO, TOTAL SISTEMA):
            metrica = 'moneda', unidad_metrica = 'BOB' (escalados por conversion_factor, default 1000 por 'miles de BOB')
        """
        dataframe.columns = [re.sub(r"[\t\xa0]+", "", str(c)).strip() for c in dataframe.columns]

        for col in dataframe.columns:
            if col not in ["valor", "fecha"]:
                dataframe[col] = dataframe[col].apply(
                    lambda x: str(x).strip() if pd.notna(x) and str(x).strip().lower() not in ["none", "nan", ""] else None
                )

        def get_metric(row) -> str:
            nv2_str = str(row.get("nv2", "")).lower()
            nv3_str = str(row.get("nv3", "")).lower()
            if "%" in nv2_str or "participaci" in nv2_str:
                return "porcentaje"
            if "veces" in nv3_str or "patrimo" in nv3_str:
                return "ratio"
            return "moneda"

        def get_unit(row) -> str:
            nv2_str = str(row.get("nv2", "")).lower()
            nv3_str = str(row.get("nv3", "")).lower()
            if "%" in nv2_str or "participaci" in nv2_str:
                return "%"
            if "veces" in nv3_str or "patrimo" in nv3_str:
                return "veces"
            return "BOB"

        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value=dataframe.apply(get_metric, axis=1))
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value=dataframe.apply(get_unit, axis=1))

        # Asegurar tipo numérico en 'valor'
        dataframe["valor"] = pd.to_numeric(dataframe["valor"], errors="coerce")

        # Escalar únicamente las filas monetarias según conversion_factor (default 1000)
        try:
            factor = float(conversion_factor) if conversion_factor is not None else 1000.0
        except (ValueError, TypeError):
            factor = 1000.0

        if factor <= 1.0:
            factor = 1000.0

        mask_moneda = dataframe["metrica"] == "moneda"
        dataframe.loc[mask_moneda, "valor"] = dataframe.loc[mask_moneda, "valor"] * factor

        # Se retorna factor 1 en df_dict para que process_numeric_column no vuelva a multiplicar porcentajes/ratios
        return ({"conversion_factor": 1}, dataframe)


Robot = D_BO_000000316_01
