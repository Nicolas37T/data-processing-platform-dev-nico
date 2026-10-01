"""Migration robot for report D_BO_000000289_01: Reclamos Recibidos en Segunda Instancia por Tipo de Entidad."""

import re
from typing import Tuple
import pandas as pd
from models.migration.Migration_Base import Migration_Base


class D_BO_000000289_01(Migration_Base):
    """Migration robot for D_BO_000000289_01."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enrich dataframe with metric and metric unit metadata.
        Mapeo dinamico de metricas y unidades (BOB, USD, UFV, tipos de cambio, ratios y porcentajes).
        """
        dataframe.columns = [re.sub(r"[\t\xa0]+", "", str(c)).strip() for c in dataframe.columns]

        for col in dataframe.columns:
            if col not in ["valor", "fecha"]:
                dataframe[col] = dataframe[col].apply(
                    lambda x: str(x).strip() if pd.notna(x) and str(x).strip().lower() not in ["none", "nan", ""] else None
                )

        def get_metric(row) -> str:
            texts = [str(row.get(c, "")).upper() for c in reversed(['titulo1', 'titulo2', 'titulo3', 'titulo4', 'nv1', 'nv2', 'nv3', 'nv4'])]
            combined = " ".join(texts)
            if any(tok in combined for tok in ["%", "PORCENTAJ", "PARTICIPACI", "PROPORCION"]):
                return "porcentaje"
            if "VECES" in combined or "RATIO" in combined:
                return "ratio"
            if any(tok in combined for tok in ["INDICE", "ÍNDICE", "BASE 20", "BASE 19"]):
                return "indice"
            if any(tok in combined for tok in ["TASA", "RENDIMIENTO"]):
                return "tasa"
            if any(tok in combined for tok in ["TIPO DE CAMBIO", "COTIZACION", "COTIZACIÓN", "BS/USD", "BOB/USD", "BS/UFV", "BOB/UFV"]):
                return "tipo_cambio"
            if any(tok in combined for tok in ["GWH", "MWH", "KWH", "ENERGIA", "ENERGÍA"]):
                return "energia"
            if any(tok in combined for tok in ["POTENCIA", " MW", "(MW)", " GW", "(GW)", " KW", "(KW)"]):
                return "potencia"
            for t in texts:
                words = set(re.split(r"[\s/()]+", t))
                if any(w in ["ME", "M.E.", "USD", "DOLARES", "DÓLARES", "$US"] for w in words) or "MONEDA EXTRANJERA" in t or "DEL EXTERIOR" in t:
                    return "moneda"
                if any(w in ["MN", "M.N.", "BOB", "BS", "BOLIVIANOS"] for w in words) or "MONEDA NACIONAL" in t:
                    return "moneda"
                if "UFV" in words:
                    return "moneda"
            return "conteo"

        def get_unit(row) -> str:
            texts = [str(row.get(c, "")).upper() for c in reversed(['titulo1', 'titulo2', 'titulo3', 'titulo4', 'nv1', 'nv2', 'nv3', 'nv4'])]
            combined = " ".join(texts)
            if any(tok in combined for tok in ["%", "PORCENTAJ", "PARTICIPACI", "PROPORCION"]):
                return "%"
            if "VECES" in combined or "RATIO" in combined:
                return "veces"
            match_base = re.search(r"(\d{4}\s*=\s*100)", combined)
            if match_base:
                return match_base.group(1).replace(" ", "")
            for t in texts:
                words = set(re.split(r"[\s/()]+", t))
                if "GWH" in words:
                    return "GWh"
                if "MWH" in words:
                    return "MWh"
                if "KWH" in words:
                    return "kWh"
                if "MW" in words:
                    return "MW"
                if "GW" in words:
                    return "GW"
                if "KW" in words:
                    return "kW"
            for t in texts:
                if any(tok in t for tok in ["BS/USD", "BOB/USD", "BS / USD", "BOB / USD"]) or ("TIPO DE CAMBIO" in t and any(tok in t for tok in ["USD", "DOLAR", "DÓLAR"])):
                    return "BOB/USD"
                if any(tok in t for tok in ["BS/UFV", "BOB/UFV", "BS / UFV", "BOB / UFV"]) or ("UFV" in t and "TIPO DE CAMBIO" in t) or ("BS/UFV" in t):
                    return "BOB/UFV"
            for t in texts:
                words = set(re.split(r"[\s/()]+", t))
                if "UFV" in words:
                    return "UFV"
                if any(w in ["ME", "M.E.", "USD", "DOLARES", "DÓLARES", "$US"] for w in words) or "MONEDA EXTRANJERA" in t or "DEL EXTERIOR" in t:
                    return "USD"
                if any(w in ["MN", "M.N.", "BOB", "BS", "BOLIVIANOS"] for w in words) or "MONEDA NACIONAL" in t:
                    return "BOB"
            return "reclamos"

        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value=dataframe.apply(get_metric, axis=1))
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value=dataframe.apply(get_unit, axis=1))

        dataframe["valor"] = pd.to_numeric(dataframe["valor"], errors="coerce")

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


Robot = D_BO_000000289_01
