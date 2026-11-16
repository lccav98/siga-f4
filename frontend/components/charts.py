"""Gráficos analíticos (Vega-Lite interativo do Streamlit) para o SIGA-F4."""

from typing import Any, Dict, Tuple

import pandas as pd
import streamlit as st


def _preparar_controles_zoom(
    df_plot: pd.DataFrame,
    chave: str,
    titulo_x: str,
    campo_x: str,
) -> Tuple[Tuple[float, float], Tuple[float, float], int]:
    """Renderiza predefinições e sliders de zoom para ampliar clusters sem sobreposição."""
    max_spu = max(float(df_plot["valor_spu_milhoes"].max()), 50.0)
    teto_spu = float(((int(max_spu) // 50) + 1) * 50)

    c_preset, c_x, c_y, c_h = st.columns([1.4, 1.4, 1.4, 0.8])
    with c_preset:
        preset = st.selectbox(
            "Modo de Zoom",
            options=[
                "Visão Completa",
                "Ampliar Base SPU (≤ R$ 250 Mi)",
                "Ampliar Micro-OMs / TGs (≤ R$ 60 Mi)",
                f"Alta Performance ({campo_x.upper()} ≥ 60)",
                "Personalizado",
            ],
            key=f"zoom_preset_{chave}",
            help="Use também a roda do mouse sobre o gráfico para dar zoom e arraste para mover.",
        )

    if preset == "Ampliar Base SPU (≤ R$ 250 Mi)":
        def_x = (0.0, 105.0)
        def_y = (0.0, min(250.0, teto_spu))
    elif preset == "Ampliar Micro-OMs / TGs (≤ R$ 60 Mi)":
        def_x = (0.0, 105.0)
        def_y = (0.0, min(60.0, teto_spu))
    elif preset.startswith("Alta Performance"):
        def_x = (55.0, 105.0)
        def_y = (0.0, teto_spu)
    else:
        def_x = (0.0, 105.0)
        def_y = (0.0, teto_spu)

    with c_x:
        if preset == "Personalizado":
            faixa_x = st.slider(
                f"Zoom {titulo_x}",
                min_value=0.0,
                max_value=105.0,
                value=def_x,
                step=5.0,
                key=f"zoom_x_{chave}",
            )
        else:
            faixa_x = def_x
            st.caption(f"Eixo X: **{faixa_x[0]:.0f} – {faixa_x[1]:.0f}**")

    with c_y:
        if preset == "Personalizado":
            faixa_y = st.slider(
                "Zoom Valor SPU (R$ Mi)",
                min_value=0.0,
                max_value=teto_spu,
                value=def_y,
                step=10.0,
                key=f"zoom_y_{chave}",
            )
        else:
            faixa_y = def_y
            st.caption(f"Eixo Y (SPU): **R$ {faixa_y[0]:,.0f} – {faixa_y[1]:,.0f} Mi**")

    with c_h:
        altura = st.select_slider(
            "Altura",
            options=[420, 520, 660],
            value=520,
            key=f"altura_{chave}",
        )

    return faixa_x, faixa_y, altura


def _renderizar_dispersao_base(
    df: pd.DataFrame,
    chave: str,
    campo_x: str,
    titulo_x: str,
    campo_cor: str,
    titulo_cor: str,
    dominio_cor: list[str],
    faixa_cores: list[str],
    titulo_y: str,
    tooltips: list[Dict[str, Any]],
    incluir_tamanho_ive: bool = False,
) -> None:
    """Renderiza gráfico de dispersão Vega-Lite com zoom/pan, destaque ao clicar e recorte por faixa."""
    if df.empty:
        st.info("Nenhuma OM disponível para plotagem com os filtros atuais.")
        return

    df_plot = df.copy()
    df_plot["valor_spu_milhoes"] = (df_plot["valor_imovel_brl"] / 1_000_000.0).round(2)

    faixa_x, faixa_y, altura = _preparar_controles_zoom(
        df_plot,
        chave=chave,
        titulo_x=campo_x.replace("indice_tecnologia_", "").upper(),
        campo_x="C4ISR" if "c4isr" in campo_x else "IVE",
    )

    encoding: Dict[str, Any] = {
        "x": {
            "field": campo_x,
            "type": "quantitative",
            "title": titulo_x,
            "scale": {"domain": [faixa_x[0], faixa_x[1]]},
        },
        "y": {
            "field": "valor_spu_milhoes",
            "type": "quantitative",
            "title": titulo_y,
            "scale": {"domain": [faixa_y[0], faixa_y[1]]},
        },
        "color": {
            "field": campo_cor,
            "type": "nominal",
            "title": titulo_cor,
            "scale": {"domain": dominio_cor, "range": faixa_cores},
        },
        "opacity": {
            "condition": {"param": "destaque_bolha", "value": 0.9},
            "value": 0.28,
        },
        "stroke": {
            "condition": [{"param": "destaque_bolha", "empty": False, "value": "#0f172a"}],
            "value": "#ffffff",
        },
        "strokeWidth": {
            "condition": [{"param": "destaque_bolha", "empty": False, "value": 2.4}],
            "value": 0.9,
        },
        "tooltip": tooltips,
    }

    if incluir_tamanho_ive:
        encoding["size"] = {
            "field": "nota_ive",
            "type": "quantitative",
            "title": "Nota IVE",
            "scale": {"range": [70, 520]},
        }

    spec: Dict[str, Any] = {
        "params": [
            {
                "name": "zoom_pan",
                "select": {"type": "interval"},
                "bind": "scales",
            },
            {
                "name": "destaque_bolha",
                "select": {
                    "type": "point",
                    "on": "click",
                    "clear": "dblclick",
                    "fields": ["id_om"],
                },
            },
            {
                "name": "filtro_legenda",
                "select": {"type": "point", "fields": [campo_cor]},
                "bind": "legend",
            },
        ],
        "transform": [
            {"filter": {"param": "filtro_legenda"}},
        ],
        "mark": {
            "type": "circle",
            "clip": True,
            **({} if incluir_tamanho_ive else {"size": 135}),
        },
        "encoding": encoding,
        "height": altura,
    }

    st.vega_lite_chart(df_plot, spec, use_container_width=True)
    st.caption(
        "🔎 **Controles do gráfico:** role a **roda do mouse** (ou faça pinça) sobre a área plotada para dar **zoom**, "
        "**clique e arraste** para mover (pan), **clique** em uma bolha ou item da legenda para destacar, "
        "e dê **duplo clique** para redefinir. Use o ícone **⛶** no canto superior direito para tela cheia."
    )


def renderizar_dispersao_tecnologia_spu(df: pd.DataFrame) -> None:
    """Renderiza gráfico de dispersão: Nível Tecnológico (C4ISR) vs. Valor SPU (R$ Mi)."""
    tooltips = [
        {"field": "sigla", "type": "nominal", "title": "OM"},
        {"field": "brigada", "type": "nominal", "title": "Brigada / Sistema"},
        {"field": "uf", "type": "nominal", "title": "UF"},
        {"field": "classificacao_coeb", "type": "nominal", "title": "COEB"},
        {"field": "classificacao_ive", "type": "nominal", "title": "Diagnóstico JEV"},
        {"field": "nota_ive", "type": "quantitative", "title": "IVE", "format": ".1f"},
        {"field": "indice_tecnologia_c4isr", "type": "quantitative", "title": "C4ISR", "format": ".1f"},
        {"field": "valor_spu_milhoes", "type": "quantitative", "title": "Valor SPU (R$ Mi)", "format": ",.2f"},
    ]
    _renderizar_dispersao_base(
        df=df,
        chave="tec_spu",
        campo_x="indice_tecnologia_c4isr",
        titulo_x="Nível Tecnológico C4ISR (0–100)",
        campo_cor="classificacao_coeb",
        titulo_cor="Classificação COEB",
        dominio_cor=["FEI", "FEP", "FEC", "SAUDE", "ENSINO"],
        faixa_cores=["#10b981", "#f59e0b", "#ef4444", "#3b82f6", "#8b5cf6"],
        titulo_y="Custo de Oportunidade — Valor SPU (R$ Milhões)",
        tooltips=tooltips,
        incluir_tamanho_ive=True,
    )


def renderizar_dispersao_ive_spu(df: pd.DataFrame) -> None:
    """Renderiza gráfico complementar: Nota IVE vs. Valor SPU para identificar OMs Zumbi."""
    tooltips = [
        {"field": "sigla", "type": "nominal", "title": "OM"},
        {"field": "brigada", "type": "nominal", "title": "Brigada / Sistema"},
        {"field": "uf", "type": "nominal", "title": "UF"},
        {"field": "classificacao_coeb", "type": "nominal", "title": "COEB"},
        {"field": "classificacao_ive", "type": "nominal", "title": "Diagnóstico JEV"},
        {"field": "nota_ive", "type": "quantitative", "title": "IVE", "format": ".1f"},
        {"field": "valor_spu_milhoes", "type": "quantitative", "title": "Valor SPU (R$ Mi)", "format": ",.2f"},
        {"field": "total_alertas", "type": "quantitative", "title": "Alertas"},
    ]
    _renderizar_dispersao_base(
        df=df,
        chave="ive_spu",
        campo_x="nota_ive",
        titulo_x="Índice de Valor Estratégico — IVE (0–100)",
        campo_cor="classificacao_ive",
        titulo_cor="Classificação JEV",
        dominio_cor=[
            "Ponta de Lança",
            "Zona de Fusão",
            "Sustentação Sanitária",
            "Capacidade Institucional",
            "OM Zumbi",
        ],
        faixa_cores=["#10b981", "#f59e0b", "#3b82f6", "#8b5cf6", "#ef4444"],
        titulo_y="Valor Imobiliário SPU (R$ Milhões)",
        tooltips=tooltips,
        incluir_tamanho_ive=False,
    )
