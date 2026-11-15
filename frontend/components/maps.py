"""Módulo Folium para renderização geoespacial das OMs e do Eixo A2/AD."""

from typing import Any, Dict, List

import folium


COR_CLASSIFICACAO = {
    "Ponta de Lança": "green",
    "Zona de Fusão": "orange",
    "OM Zumbi": "red",
}


def criar_mapa_a2ad(oms: List[Dict[str, Any]]) -> folium.Map:
    """Constrói mapa Folium destacando OMs do Eixo A2/AD e status IVE."""
    mapa = folium.Map(location=[-14.2350, -51.9253], zoom_start=4, tiles="OpenStreetMap")

    camada_a2ad = folium.FeatureGroup(name="Eixo Estratégico A2/AD (Negação de Área)", show=True)
    camada_demais = folium.FeatureGroup(name="Demais OMs", show=True)

    for om in oms:
        lat = om.get("latitude")
        lon = om.get("longitude")
        if lat is None or lon is None:
            continue

        classif_ive = om.get("classificacao_ive", "Zona de Fusão")
        cor = COR_CLASSIFICACAO.get(classif_ive, "blue")
        papel_a2ad = bool(om.get("papel_a2ad", False))
        valor_spu_m = (om.get("valor_imovel_brl", 0.0) or 0.0) / 1_000_000.0
        cma = om.get("comando_militar_area", "-")
        rm = om.get("regiao_militar", "-")
        uf = om.get("uf", "-")
        brigada = om.get("brigada", "-")

        popup_html = f"""
        <div style="font-family: Arial, sans-serif; min-width: 245px;">
            <h4 style="margin:0 0 6px 0;">{om.get('sigla', 'OM')}</h4>
            <b>Local:</b> {uf} • {cma} / {rm}<br>
            <b>Brigada / GU:</b> {brigada}<br>
            <b>UASG:</b> {om.get('codigo_uasg', '-')} | <b>COEB:</b> {om.get('classificacao_coeb')} | <b>A2/AD:</b> {'SIM' if papel_a2ad else 'NÃO'}<br>
            <b>IVE:</b> {om.get('nota_ive', 0):.1f} ({classif_ive})<br>
            <b>C4ISR:</b> {om.get('indice_tecnologia_c4isr', 0):.1f}/100<br>
            <b>Valor SPU:</b> R$ {valor_spu_m:,.1f} Mi<br>
            <b>Alertas CGU/Prontidão:</b> {om.get('total_alertas', 0)}
        </div>
        """

        if papel_a2ad:
            # Halo de cobertura A2/AD para unidades de negação de área
            folium.Circle(
                location=[lat, lon],
                radius=140_000,
                color="#38bdf8",
                weight=1.5,
                fill=True,
                fill_color="#38bdf8",
                fill_opacity=0.14,
                tooltip=f"Cobertura A2/AD: {om.get('sigla')}",
            ).add_to(camada_a2ad)

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=280),
                tooltip=f"[A2/AD] {om.get('sigla')} — IVE {om.get('nota_ive', 0):.1f}",
                icon=folium.Icon(color=cor, icon="shield", prefix="fa"),
            ).add_to(camada_a2ad)
        else:
            folium.CircleMarker(
                location=[lat, lon],
                radius=8,
                color=cor,
                fill=True,
                fill_color=cor,
                fill_opacity=0.85,
                popup=folium.Popup(popup_html, max_width=280),
                tooltip=f"{om.get('sigla')} ({om.get('classificacao_coeb')}) — IVE {om.get('nota_ive', 0):.1f}",
            ).add_to(camada_demais)

    camada_a2ad.add_to(mapa)
    camada_demais.add_to(mapa)
    folium.LayerControl(collapsed=False).add_to(mapa)

    return mapa
