"""Gráficos analíticos (Vega-Lite nativo do Streamlit) para o SIGA-F4."""

import pandas as pd
import streamlit as st


def renderizar_dispersao_tecnologia_spu(df: pd.DataFrame) -> None:
    """Renderiza gráfico de dispersão: Nível Tecnológico (C4ISR) vs. Valor SPU (R$ Mi)."""
    if df.empty:
        st.info("Nenhuma OM disponível para plotagem com os filtros atuais.")
        return

    df_plot = df.copy()
    df_plot["valor_spu_milhoes"] = (df_plot["valor_imovel_brl"] / 1_000_000.0).round(2)

    spec = {
        "mark": {"type": "circle", "opacity": 0.85, "stroke": "#ffffff", "strokeWidth": 1},
        "encoding": {
            "x": {
                "field": "indice_tecnologia_c4isr",
                "type": "quantitative",
                "title": "Nível Tecnológico C4ISR (0–100)",
                "scale": {"domain": [0, 105]},
            },
            "y": {
                "field": "valor_spu_milhoes",
                "type": "quantitative",
                "title": "Custo de Oportunidade — Valor SPU (R$ Milhões)",
            },
            "color": {
                "field": "classificacao_coeb",
                "type": "nominal",
                "title": "Classificação COEB",
                "scale": {
                    "domain": ["FEI", "FEP", "FEC", "SAUDE"],
                    "range": ["#10b981", "#f59e0b", "#ef4444", "#3b82f6"],
                },
            },
            "size": {
                "field": "nota_ive",
                "type": "quantitative",
                "title": "Nota IVE",
                "scale": {"range": [80, 600]},
            },
            "tooltip": [
                {"field": "sigla", "type": "nominal", "title": "OM"},
                {"field": "classificacao_coeb", "type": "nominal", "title": "COEB"},
                {"field": "classificacao_ive", "type": "nominal", "title": "Diagnóstico JEV"},
                {"field": "nota_ive", "type": "quantitative", "title": "IVE", "format": ".1f"},
                {"field": "indice_tecnologia_c4isr", "type": "quantitative", "title": "C4ISR", "format": ".1f"},
                {"field": "valor_spu_milhoes", "type": "quantitative", "title": "Valor SPU (R$ Mi)", "format": ",.2f"},
            ],
        },
        "height": 380,
    }

    st.vega_lite_chart(df_plot, spec, use_container_width=True)


def renderizar_dispersao_ive_spu(df: pd.DataFrame) -> None:
    """Renderiza gráfico complementar: Nota IVE vs. Valor SPU para identificar OMs Zumbi."""
    if df.empty:
        return

    df_plot = df.copy()
    df_plot["valor_spu_milhoes"] = (df_plot["valor_imovel_brl"] / 1_000_000.0).round(2)

    spec = {
        "mark": {"type": "point", "filled": True, "size": 140, "opacity": 0.9},
        "encoding": {
            "x": {
                "field": "nota_ive",
                "type": "quantitative",
                "title": "Índice de Valor Estratégico — IVE (0–100)",
                "scale": {"domain": [0, 105]},
            },
            "y": {
                "field": "valor_spu_milhoes",
                "type": "quantitative",
                "title": "Valor Imobiliário SPU (R$ Milhões)",
            },
            "color": {
                "field": "classificacao_ive",
                "type": "nominal",
                "title": "Classificação JEV",
                "scale": {
                    "domain": [
                        "Ponta de Lança",
                        "Zona de Fusão",
                        "Sustentação Sanitária",
                        "Capacidade Institucional",
                        "OM Zumbi",
                    ],
                    "range": ["#10b981", "#f59e0b", "#3b82f6", "#8b5cf6", "#ef4444"],
                },
            },
            "tooltip": [
                {"field": "sigla", "type": "nominal", "title": "OM"},
                {"field": "nota_ive", "type": "quantitative", "title": "IVE", "format": ".1f"},
                {"field": "valor_spu_milhoes", "type": "quantitative", "title": "Valor SPU (R$ Mi)", "format": ",.2f"},
                {"field": "total_alertas", "type": "quantitative", "title": "Alertas"},
            ],
        },
        "height": 340,
    }

    st.vega_lite_chart(df_plot, spec, use_container_width=True)
