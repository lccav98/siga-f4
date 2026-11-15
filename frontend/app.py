"""Dashboard Executivo SIGA-F4 (Streamlit + Folium + Digital Twin)."""

import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# Garante importação local quando executado via `streamlit run frontend/app.py`
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.core.digital_twin import simular_reestruturacao
from backend.core.motor_jev import MotorIVE
from backend.models.database import Base, SessionLocal, engine
from backend.models.schemas import ClassificacaoCOEB, OM
from backend.services.cgu_sync import TransparenciaSyncService
from frontend.components.charts import (
    renderizar_dispersao_ive_spu,
    renderizar_dispersao_tecnologia_spu,
)
from frontend.components.maps import criar_mapa_a2ad

API_URL = os.getenv("SIGA_API_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="SIGA-F4 | Governança Algorítmica de Força",
    page_icon="🛡️",
    layout="wide",
)


def carregar_ranking_oms() -> tuple[List[Dict[str, Any]], str]:
    """Busca ranking via API FastAPI; faz fallback para MotorIVE local se API estiver offline."""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{API_URL}/api/oms")
            resp.raise_for_status()
            return resp.json(), "FastAPI"
    except httpx.HTTPError:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            diags = MotorIVE().diagnosticar_todas(db, persistir_alertas=True)
            dados = [
                {
                    "ranking": idx,
                    "id_om": d.id_om,
                    "sigla": d.sigla,
                    "codigo_uasg": d.codigo_uasg,
                    "cnpj_ug": d.cnpj_ug,
                    "classificacao_coeb": d.classificacao_coeb,
                    "indice_tecnologia_c4isr": d.indice_tecnologia_c4isr,
                    "papel_a2ad": d.papel_a2ad,
                    "valor_imovel_brl": d.valor_imovel_brl,
                    "nota_ive": d.nota_ive,
                    "classificacao_ive": d.classificacao_ive,
                    "foco_estrategico": d.foco_estrategico,
                    "indicador_financeiro_estrategico": d.indicador_financeiro_estrategico,
                    "total_alertas": len(d.alertas_auditoria),
                    "latitude": d.dados_operacionais.get("latitude"),
                    "longitude": d.dados_operacionais.get("longitude"),
                }
                for idx, d in enumerate(diags, start=1)
            ]
            return dados, "Local DB (Fallback)"
        finally:
            db.close()


def carregar_diagnostico_om(id_om: int) -> Optional[Dict[str, Any]]:
    """Carrega diagnóstico completo de uma OM via API ou fallback local."""
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{API_URL}/api/oms/{id_om}/diagnostico")
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError:
        db = SessionLocal()
        try:
            om = db.query(OM).filter(OM.id_om == id_om).first()
            if not om:
                return None
            return MotorIVE().diagnosticar_om(db, om, persistir_alertas=True).to_dict()
        finally:
            db.close()


def executar_simulacao(id_zumbi: int, id_destino: int) -> Dict[str, Any]:
    """Executa simulação Digital Twin via FastAPI ou fallback local."""
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(
                f"{API_URL}/api/simulador/reestruturar",
                json={"id_om_zumbi": id_zumbi, "id_om_fei_destino": id_destino},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError:
        db = SessionLocal()
        try:
            return simular_reestruturacao(db, id_zumbi, id_destino)
        finally:
            db.close()


def capturar_om_uasg(codigo: str, coeb_opcao: str) -> Dict[str, Any]:
    """Capta ou atualiza uma OM pelo código UASG/UG via API ou serviço local."""
    coeb_val = None if coeb_opcao == "Automático (COEB)" else coeb_opcao
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{API_URL}/api/oms/capturar-uasg",
                json={"codigo_uasg_ou_ug": codigo, "classificacao_coeb": coeb_val},
            )
            if resp.status_code >= 400:
                detalhe = resp.json().get("detail", resp.text)
                raise ValueError(detalhe)
            return resp.json()
    except httpx.HTTPError:
        db = SessionLocal()
        try:
            coeb_enum = ClassificacaoCOEB(coeb_val) if coeb_val else None
            res = TransparenciaSyncService().capturar_om_por_uasg(
                db=db,
                codigo_uasg_ou_ug=codigo,
                coeb_override=coeb_enum,
            )
            om = db.query(OM).filter(OM.id_om == res["id_om"]).first()
            diag = MotorIVE().diagnosticar_om(db, om, persistir_alertas=True).to_dict()
            return {"acao": res["acao"], "origem_dados": res["origem_dados"], "diagnostico": diag}
        finally:
            db.close()


# ------------------------------------------------------------------
# Cabeçalho e Carregamento
# ------------------------------------------------------------------
st.title("🛡️ SIGA-F4 — Sistema de Governança Algorítmica de Força")
st.caption("Motor JEV (Julgamento, Estratégia e Validação) • COEB / Força 4.0 • Auditoria CGU & SPU")

oms_brutas, fonte_dados = carregar_ranking_oms()

if not oms_brutas:
    st.warning(
        "Nenhuma OM encontrada no banco de dados. Execute `python scripts/gerador_mock.py` "
        "para gerar a massa de dados inicial."
    )
    st.stop()

df_all = pd.DataFrame(oms_brutas)

# ------------------------------------------------------------------
# 1. Filtros Doutrinários (Sidebar)
# ------------------------------------------------------------------
st.sidebar.header("🎯 Filtros Doutrinários (COEB)")
coeb_selecionado = st.sidebar.multiselect(
    "Classificação COEB",
    options=["FEI", "FEP", "FEC"],
    default=["FEI", "FEP", "FEC"],
    help=(
        "FEI: Emprego Imediato (Fronteira, Selva, OpEsp, Pqdt, Amv, Ciber, Intlg, AvEx, AAAe) | "
        "FEP: Prontidão / FORPRON (Bld, Mec, Art, Eng, Com, Log) | "
        "FEC: Emprego Condicionado (Guarda, PE, Territorial, Depósitos, Arsenais, RM)"
    ),
)
status_jev_selecionado = st.sidebar.multiselect(
    "Diagnóstico JEV (IVE)",
    options=["Ponta de Lança", "Zona de Fusão", "OM Zumbi"],
    default=["Ponta de Lança", "Zona de Fusão", "OM Zumbi"],
)
busca_sigla = st.sidebar.text_input(
    "🔍 Buscar por UASG, UG/CNPJ ou Sigla",
    placeholder="Ex: 160069, 160501, BInt, BIS...",
)
apenas_a2ad = st.sidebar.checkbox("Apenas Eixo A2/AD (Negação de Área)", value=False)
apenas_alertas = st.sidebar.checkbox("Apenas OMs com Alertas CGU/Prontidão", value=False)
st.sidebar.divider()
st.sidebar.caption(
    "**Enquadramento COEB:**\n"
    f"- **FEI:** {int((df_all['classificacao_coeb'] == 'FEI').sum())} OMs\n"
    f"- **FEP:** {int((df_all['classificacao_coeb'] == 'FEP').sum())} OMs\n"
    f"- **FEC:** {int((df_all['classificacao_coeb'] == 'FEC').sum())} OMs"
)
st.sidebar.info(f"Fonte ativa: **{fonte_dados}** ({len(df_all)} OMs na base)")

df_filtrado = df_all[
    df_all["classificacao_coeb"].isin(coeb_selecionado)
    & df_all["classificacao_ive"].isin(status_jev_selecionado)
].copy()
if busca_sigla.strip():
    termo = busca_sigla.strip().lower()
    digitos_busca = re.sub(r"\D", "", termo)
    mask_sigla = df_filtrado["sigla"].str.lower().str.contains(termo, na=False)
    mask_uasg = df_filtrado["codigo_uasg"].astype(str).str.contains(termo, na=False)
    mask_ug = (
        df_filtrado["cnpj_ug"].astype(str).str.replace(r"\D", "", regex=True).str.contains(digitos_busca, na=False)
        if digitos_busca
        else pd.Series(False, index=df_filtrado.index)
    )
    df_filtrado = df_filtrado[mask_sigla | mask_uasg | mask_ug]
if apenas_a2ad:
    df_filtrado = df_filtrado[df_filtrado["papel_a2ad"] == True]  # noqa: E712
if apenas_alertas:
    df_filtrado = df_filtrado[df_filtrado["total_alertas"] > 0]

# KPIs Executivos
col1, col2, col3, col4 = st.columns(4)
col1.metric("OMs Filtradas", len(df_filtrado))
col2.metric(
    "IVE Médio da Força",
    f"{df_filtrado['nota_ive'].mean():.1f}" if not df_filtrado.empty else "0.0",
)
col3.metric(
    "Patrimônio SPU Total",
    f"R$ {df_filtrado['valor_imovel_brl'].sum() / 1e9:,.2f} Bi",
)
col4.metric(
    "OMs Zumbi (Alienação)",
    int((df_filtrado["classificacao_ive"] == "OM Zumbi").sum()),
)

st.divider()

# ------------------------------------------------------------------
# Captação em Tempo Real por UASG ou UG (Compras.gov.br / CGU)
# ------------------------------------------------------------------
with st.expander("📡 Capturar / Sincronizar OM pelo Código UASG ou UG (Compras.gov.br / CGU)", expanded=False):
    col_u1, col_u2, col_u3 = st.columns([2, 1.5, 1])
    with col_u1:
        input_uasg = st.text_input(
            "Código UASG ou UG/CNPJ",
            placeholder="Ex: 160069 (COEx), 160054, 160224...",
            key="input_captura_uasg",
        )
    with col_u2:
        coeb_captura = st.selectbox(
            "Enquadramento COEB",
            options=["Automático (COEB)", "FEI", "FEP", "FEC"],
            key="select_coeb_captura",
        )
    with col_u3:
        st.write("")
        st.write("")
        btn_capturar = st.button("📥 Capturar UASG/UG", use_container_width=True)

    if btn_capturar:
        if not input_uasg.strip():
            st.warning("Informe um código UASG ou UG para capturar.")
        else:
            try:
                res_cap = capturar_om_uasg(input_uasg.strip(), coeb_captura)
                d_cap = res_cap["diagnostico"]
                st.success(
                    f"OM **{d_cap['sigla']}** (UASG `{d_cap['codigo_uasg']}` | UG `{d_cap['cnpj_ug']}`) "
                    f"{res_cap['acao']} via `{res_cap['origem_dados']}` — "
                    f"COEB **{d_cap['classificacao_coeb']}**, IVE **{d_cap['nota_ive']:.1f}** ({d_cap['classificacao_ive']}). "
                    "Recarregue ou aplique filtros para vê-la destacada."
                )
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

# ------------------------------------------------------------------
# 2. Mapa Interativo A2/AD (Folium) + Ranking Doutrinário
# ------------------------------------------------------------------
col_mapa, col_rank = st.columns([1.25, 1])

with col_mapa:
    st.subheader("🗺️ Dispositivo Geoestratégico e Eixo A2/AD")
    mapa_folium = criar_mapa_a2ad(df_filtrado.to_dict(orient="records"))
    st_folium(mapa_folium, width=None, height=440, returned_objects=[])

with col_rank:
    st.subheader("📊 Ranking JEV (IVE & Custo SPU)")
    df_tabela = df_filtrado[
        [
            "ranking",
            "codigo_uasg",
            "sigla",
            "classificacao_coeb",
            "nota_ive",
            "classificacao_ive",
            "indice_tecnologia_c4isr",
            "valor_imovel_brl",
            "total_alertas",
        ]
    ].copy()
    df_tabela["valor_imovel_brl"] = (df_tabela["valor_imovel_brl"] / 1_000_000.0).round(1)
    df_tabela.columns = [
        "#",
        "UASG",
        "OM",
        "COEB",
        "IVE",
        "Status JEV",
        "C4ISR",
        "SPU (R$ Mi)",
        "Alertas",
    ]
    st.dataframe(df_tabela, use_container_width=True, height=440, hide_index=True)

st.divider()

# ------------------------------------------------------------------
# 3. Gráficos de Dispersão (Tecnologia vs. Valor SPU e IVE vs. Valor SPU)
# ------------------------------------------------------------------
st.subheader("📈 Análise de Custo de Oportunidade & Força 4.0")
tab_tec, tab_ive = st.tabs(
    [
        "Nível Tecnológico (C4ISR) vs. Custo de Oportunidade (SPU)",
        "Nota IVE vs. Valor Imobiliário (SPU)",
    ]
)

with tab_tec:
    renderizar_dispersao_tecnologia_spu(df_filtrado)

with tab_ive:
    renderizar_dispersao_ive_spu(df_filtrado)

st.divider()

# ------------------------------------------------------------------
# 4. Diagnóstico Individual (Auditoria CGU & Prescrição Doutrinária)
# ------------------------------------------------------------------
st.subheader("🔍 Diagnóstico Individual e Prescrição Doutrinária")
opcoes_om = {f"{r['sigla']} ({r['classificacao_coeb']} — IVE {r['nota_ive']:.1f})": r["id_om"] for _, r in df_all.iterrows()}
label_om_sel = st.selectbox("Selecione uma OM para inspeção detalhada:", list(opcoes_om.keys()))
diag = carregar_diagnostico_om(opcoes_om[label_om_sel])

if diag:
    c_a, c_b, c_c, c_d = st.columns(4)
    c_a.metric("Classificação JEV", diag["classificacao_ive"])
    c_b.metric("Nota IVE", f"{diag['nota_ive']:.1f}")
    c_c.metric("Índice C4ISR", f"{diag['indice_tecnologia_c4isr']:.1f}/100")
    c_d.metric("Custo / IVE", f"R$ {diag['indicador_financeiro_estrategico'] / 1e6:,.2f} Mi")

    st.info(f"**Prescrição Doutrinária:** {diag['prescricao_doutrinaria']}")

    if diag["alertas_auditoria"]:
        for alerta in diag["alertas_auditoria"]:
            st.error(f"**[{alerta['tipo']} | {alerta['severidade']}]** {alerta['descricao']}")
    else:
        st.success("Nenhuma anomalia detectada no cruzamento SIGPES × CGU × SISLOG.")

st.divider()

# ------------------------------------------------------------------
# 5. Módulo Simulador de Evolução (Digital Twin)
# ------------------------------------------------------------------
st.subheader("🧬 Digital Twin — Simulador de Reestruturação e Evolução Força 4.0")
st.markdown(
    "Selecione uma **OM Zumbi (FEC)** para simular sua alienação patrimonial (SPU) e "
    "conversão em capacidade **C4ISR** para uma unidade mediana ou prioritária."
)

df_zumbis = df_all[df_all["classificacao_coeb"] == "FEC"]
if df_zumbis.empty:
    df_zumbis = df_all.nsmallest(5, "nota_ive")

df_destinos = df_all[df_all["classificacao_coeb"].isin(["FEP", "FEI"])]
if df_destinos.empty:
    df_destinos = df_all

mapa_zumbis = {
    f"{r['sigla']} ({r['classificacao_coeb']} | IVE {r['nota_ive']:.1f} | SPU R$ {r['valor_imovel_brl']/1e6:.0f} Mi)": r["id_om"]
    for _, r in df_zumbis.iterrows()
}
mapa_destinos = {
    f"{r['sigla']} ({r['classificacao_coeb']} | C4ISR {r['indice_tecnologia_c4isr']:.1f} | IVE {r['nota_ive']:.1f})": r["id_om"]
    for _, r in df_destinos.iterrows()
}

col_s1, col_s2 = st.columns(2)
with col_s1:
    sel_zumbi = st.selectbox("1. OM Zumbi (FEC) a Desativar / Alienar:", list(mapa_zumbis.keys()))
with col_s2:
    # Evita selecionar a mesma OM por padrão
    chaves_dest = [k for k in mapa_destinos.keys() if mapa_destinos[k] != mapa_zumbis[sel_zumbi]]
    sel_destino = st.selectbox("2. OM Destino a Transformar (FEI / Força 4.0):", chaves_dest)

if st.button("🚀 Simular Transformação Doutrinária", type="primary"):
    resultado = executar_simulacao(mapa_zumbis[sel_zumbi], mapa_destinos[sel_destino])
    z = resultado["om_zumbi_desativada"]
    d = resultado["om_destino_transformada"]
    imp = resultado["impacto_financeiro_e_c2"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        f"C4ISR ({d['sigla']})",
        f"{d['c4isr_depois']:.1f}",
        delta=f"+{d['delta_c4isr']:.1f} pts",
    )
    m2.metric(
        f"IVE ({d['sigla']})",
        f"{d['ive_depois']:.1f}",
        delta=f"+{d['delta_ive']:.1f} pts",
    )
    m3.metric(
        "Capital Investido C4ISR",
        f"R$ {imp['capital_investido_c4isr_brl'] / 1e6:,.1f} Mi",
    )
    m4.metric(
        "Economia Acumulada (5 anos)",
        f"R$ {imp['economia_acumulada_5_anos_brl'] / 1e6:,.1f} Mi",
    )

    st.success(imp["resumo_executivo"])
    with st.expander("Detalhes Técnicos da Simulação (CNPJ UG, CPFs e Tesouro)"):
        st.json(resultado)
