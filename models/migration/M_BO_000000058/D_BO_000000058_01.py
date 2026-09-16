"""Migration robot for report D_BO_000000058_01: Evolutivo Fondos de Inversion."""

from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000058_01(Migration_Base):
    """Migration robot for D_BO_000000058_01."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with metric and metric unit metadata based on indicator (nv2).
        - 'Tasa...' -> metrica = 'tasa', unidad_metrica = '%'
        - 'Cuota Vigente' -> metrica = 'cantidad', unidad_metrica = 'cuotas'
        - 'Participantes' -> metrica = 'cantidad', unidad_metrica = 'personas'
        - 'Valor Cuota', 'Liquidez', 'Cartera' -> metrica = 'moneda', unidad_metrica = 'BOB'
        - conversion_factor = 1
        """
        idx_valor = dataframe.columns.get_loc("valor")

        def get_metric(nv2_val: str) -> str:
            val = str(nv2_val).lower().strip()
            if "tasa" in val:
                return "tasa"
            elif "cuota vigente" in val or "participantes" in val:
                return "cantidad"
            elif "valor cuota" in val or "liquidez" in val or "cartera" in val:
                return "moneda"
            return "numero"

        def get_unit(nv2_val: str) -> str:
            val = str(nv2_val).lower().strip()
            if "tasa" in val:
                return "%"
            elif "cuota vigente" in val:
                return "cuotas"
            elif "participantes" in val:
                return "personas"
            elif "valor cuota" in val or "liquidez" in val or "cartera" in val:
                return "BOB"
            return "unidades"

        dataframe.insert(idx_valor, column="metrica", value=dataframe["nv2"].apply(get_metric))
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value=dataframe["nv2"].apply(get_unit))

        factor = 1

        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000058_01
