"""Dashboard Executivo SIGA-F4 (Streamlit + Folium + Digital Twin)."""

import os
import re
import sys
import unicodedata
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
from backend.core.estrutura_eb import BRIGADAS_BLINDADAS, BRIGADAS_MECANIZADAS
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
                    "enquadramento_transformacao": d.dados_operacionais.get("enquadramento_transformacao", ""),
                    "comando_militar_area": d.dados_operacionais.get("comando_militar_area", ""),
                    "regiao_militar": d.dados_operacionais.get("regiao_militar", ""),
                    "uf": d.dados_operacionais.get("uf", ""),
                    "brigada": d.dados_operacionais.get("brigada", ""),
                    "latitude": d.dados_operacionais.get("latitude"),
                    "longitude": d.dados_operacionais.get("longitude"),
                    "indice_eficiencia_hospitalar": d.dados_operacionais.get("indice_eficiencia_hospitalar"),
                }
                for idx, d in enumerate(diags, start=1)
            ]
            return dados, "Local DB (Fallback)"
        finally:
            db.close()


def carregar_politica_transformacao() -> Dict[str, Any]:
    """Carrega os indicadores de aderência à EB10-P-01.031 via API ou MotorIVE local."""
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{API_URL}/api/politica-transformacao")
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError:
        db = SessionLocal()
        try:
            motor = MotorIVE()
            diags = motor.diagnosticar_todas(db, persistir_alertas=False)
            return motor.resumo_politica_transformacao(diags)
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
st.caption(
    "Motor JEV (Julgamento, Estratégia e Validação) • Política de Transformação EB10-P-01.031 (2026) "
    "& COEB • Auditoria CGU & SPU"
)

oms_brutas, fonte_dados = carregar_ranking_oms()
resumo_eb10 = carregar_politica_transformacao()

if not oms_brutas:
    st.warning(
        "Nenhuma OM encontrada no banco de dados. Execute `python scripts/gerador_mock.py` "
        "para gerar a massa de dados inicial."
    )
    st.stop()

df_all = pd.DataFrame(oms_brutas)

def _ordem_rm(rm: str) -> int:
    m = re.match(r"^(\d+)", rm or "")
    return int(m.group(1)) if m else 999


# ------------------------------------------------------------------
# 1. Filtros de Localização e Doutrina (Sidebar)
# ------------------------------------------------------------------
st.sidebar.header("📍 Localização e Enquadramento da OM")
cmas_disponiveis = sorted([c for c in df_all["comando_militar_area"].dropna().unique().tolist() if c])
cma_selecionado = st.sidebar.multiselect(
    "Comando Militar de Área (C Mil A)",
    options=cmas_disponiveis,
    default=[],
    placeholder="Todos (CMA, CMN, CMO, CMP, CML, CMSE, CMS, CMNE)",
)

df_loc_base = df_all[df_all["comando_militar_area"].isin(cma_selecionado)] if cma_selecionado else df_all
rms_disponiveis = sorted(
    [r for r in df_loc_base["regiao_militar"].dropna().unique().tolist() if r],
    key=_ordem_rm,
)
rm_selecionada = st.sidebar.multiselect(
    "Região Militar (RM)",
    options=rms_disponiveis,
    default=[],
    placeholder="Todas (1ª RM a 12ª RM)",
)

df_loc_base = df_loc_base[df_loc_base["regiao_militar"].isin(rm_selecionada)] if rm_selecionada else df_loc_base
ufs_disponiveis = sorted([u for u in df_loc_base["uf"].dropna().unique().tolist() if u])
uf_selecionada = st.sidebar.multiselect(
    "UF",
    options=ufs_disponiveis,
    default=[],
    placeholder="Todas as UFs",
)

df_loc_base = df_loc_base[df_loc_base["uf"].isin(uf_selecionada)] if uf_selecionada else df_loc_base
brigadas_disponiveis = sorted([b for b in df_loc_base["brigada"].dropna().unique().tolist() if b])
brigada_selecionada = st.sidebar.multiselect(
    "Brigada / Grande Comando",
    options=brigadas_disponiveis,
    default=[],
    placeholder="Todas as Brigadas / GUs",
)

st.sidebar.divider()
st.sidebar.header("🎯 Filtros Doutrinários (COEB / EB10-P-01.031)")
coeb_selecionado = st.sidebar.multiselect(
    "Grupos de Emprego COEB / Sistema",
    options=["FEP", "FEI", "FEC", "SAUDE", "ENSINO"],
    default=["FEP", "FEI", "FEC", "SAUDE", "ENSINO"],
    help=(
        "FEP — Forças de Emprego de Prontidão (5 Brigadas ForPron) — 1ª prioridade | "
        "FEI — Forças de Emprego Imediato: faixa de fronteira e módulos multidomínio | "
        "FEC — Forças de Emprego Continuado: reserva estratégica, litoral e presença territorial | "
        "SAUDE — Classificação em separado para OMs de Saúde (DSau / SAMMED-FUSEx) | "
        "ENSINO — Estabelecimentos de Ensino, Colégios Militares e Centros de Instrução/Adestramento (DECEx)"
    ),
)
status_jev_selecionado = st.sidebar.multiselect(
    "Diagnóstico JEV (IVE)",
    options=[
        "Ponta de Lança",
        "Zona de Fusão",
        "Sustentação Sanitária",
        "Capacidade Institucional",
        "OM Zumbi",
    ],
    default=[
        "Ponta de Lança",
        "Zona de Fusão",
        "Sustentação Sanitária",
        "Capacidade Institucional",
        "OM Zumbi",
    ],
)
modulos_disponiveis = sorted(
    [m for m in df_all["enquadramento_transformacao"].dropna().unique().tolist() if m]
)
modulos_selecionados = st.sidebar.multiselect(
    "Estrutura EB10-P-01.031 (FTC / Módulos)",
    options=modulos_disponiveis,
    default=[],
    placeholder="Todos os Grupos / Módulos",
)
busca_sigla = st.sidebar.text_input(
    "🔍 Buscar por UASG, UG/CNPJ ou Sigla",
    placeholder="Ex: 160069, 160501, BInt, BIS...",
)
apenas_a2ad = st.sidebar.checkbox("Apenas Eixo A2/AD (Negação de Área)", value=False)
apenas_alertas = st.sidebar.checkbox("Apenas OMs com Alertas CGU/Prontidão", value=False)
st.sidebar.divider()
st.sidebar.caption(
    "**Grupos de Emprego (EB10-P-01.031):**\n"
    f"- **FEP (Prontidão / 1ª Prio):** {int((df_all['classificacao_coeb'] == 'FEP').sum())} OMs\n"
    f"- **FEI (Imediato / Fronteira):** {int((df_all['classificacao_coeb'] == 'FEI').sum())} OMs\n"
    f"- **FEC (Continuado / Territorial):** {int((df_all['classificacao_coeb'] == 'FEC').sum())} OMs\n"
    f"- **SAUDE (DSau / Hospitais e Policlínicas):** {int((df_all['classificacao_coeb'] == 'SAUDE').sum())} OMs\n"
    f"- **ENSINO (DECEx / Escolas, CMs e CIs):** {int((df_all['classificacao_coeb'] == 'ENSINO').sum())} OMs"
)
st.sidebar.info(f"Fonte ativa: **{fonte_dados}** ({len(df_all)} OMs na base)")

df_filtrado = df_all[
    df_all["classificacao_coeb"].isin(coeb_selecionado)
    & df_all["classificacao_ive"].isin(status_jev_selecionado)
].copy()
if modulos_selecionados:
    df_filtrado = df_filtrado[df_filtrado["enquadramento_transformacao"].isin(modulos_selecionados)]
if cma_selecionado:
    df_filtrado = df_filtrado[df_filtrado["comando_militar_area"].isin(cma_selecionado)]
if rm_selecionada:
    df_filtrado = df_filtrado[df_filtrado["regiao_militar"].isin(rm_selecionada)]
if uf_selecionada:
    df_filtrado = df_filtrado[df_filtrado["uf"].isin(uf_selecionada)]
if brigada_selecionada:
    df_filtrado = df_filtrado[df_filtrado["brigada"].isin(brigada_selecionada)]
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
    "OMs Zumbi (Item 3.1.3.1)",
    int((df_filtrado["classificacao_ive"] == "OM Zumbi").sum()),
)

# Painel de Conformidade — Política de Transformação do Exército Brasileiro (EB10-P-01.031 / 2026)
with st.expander(
    f"📜 Conformidade Política de Transformação ({resumo_eb10['norma']}) — Meta ≥ 20% Prontidão & FTC Multidomínio",
    expanded=True,
):
    eb1, eb2, eb3, eb4 = st.columns(4)
    pct_pront = resumo_eb10["percentual_prontidao_forca"]
    delta_meta = round(pct_pront - resumo_eb10["meta_prontidao_minima_pct"], 1)
    eb1.metric(
        "Efetivo em Elevada Prontidão (Meta ≥ 20%)",
        f"{pct_pront:.1f}%",
        delta=f"{delta_meta:+.1f} p.p. vs. meta (itens 1.4/2.6)",
    )
    eb2.metric(
        "Módulos Multidomínio (Item 3.1.1.2 d)",
        f"{resumo_eb10['modulos_multidominio_ftc']} OMs",
        help="Forças aptas ao Multidomínio na Força Terrestre Componente (FTC) ou Comando Conjunto.",
    )
    eb3.metric(
        "Apoio Ampliado à FTC (Item 3.1.1.2 e)",
        f"{resumo_eb10['modulos_apoio_ampliado_ftc']} OMs",
        delta=(
            f"+ {resumo_eb10.get('oms_saude_sustentacao', 0)} Saúde (DSau) • "
            f"{resumo_eb10.get('oms_capacidade_institucional', 0)} Ensino/Adestr. (DECEx)"
        ),
        delta_color="off",
        help="Estruturas modulares de sustentação logística, engenharia, telemática, saúde e ensino/adestramento (DECEx).",
    )
    eb4.metric(
        "Alvos Otimização PEECFA (Item 3.1.3.1)",
        f"{resumo_eb10['oms_otimizacao_item_3_1_3_1']} OMs",
        delta=f"R$ {resumo_eb10['patrimonio_otimizacao_brl'] / 1e9:,.2f} Bi SPU",
        delta_color="off",
    )
    st.caption("**🛡️ Requisito de Modernização & Obsolescência — Prg EE Forças Blindadas / Mecanizadas & C4ISR:**")
    bm1, bm2, bm3, bm4 = st.columns(4)
    bm1.metric(
        f"Bda Blindadas ({resumo_eb10.get('oms_brigadas_blindadas', 0)} OMs)",
        f"R$ {resumo_eb10.get('capex_blindadas_brl', 0) / 1e9:,.2f} Bi CAPEX",
        help="Nova família: VBC CC, VBC Fuz, Obuseiros Blindados, VBC Eng, Socorro, Pranchas de Transporte Pesado e C4ISR.",
    )
    bm2.metric(
        "Obsolescência Blindadas/ano",
        f"R$ {resumo_eb10.get('obsolescencia_anual_blindadas_brl', 0) / 1e6:,.1f} Mi",
        help="Custo anual de sustentação e perda de disponibilidade do material blindado sobre lagartas legado.",
    )
    bm3.metric(
        f"Bda Mecanizadas ({resumo_eb10.get('oms_brigadas_mecanizadas', 0)} OMs)",
        f"R$ {resumo_eb10.get('capex_mecanizadas_brl', 0) / 1e9:,.2f} Bi CAPEX",
        help="Família sobre rodas: VBMT Guaicurus (4x4), VBTP Guarani (6x6), VBC Cav Centauro II (8x8), Apoio de Fogo/Log Mecanizado e C4ISR.",
    )
    bm4.metric(
        "Obsolescência Mecanizadas/ano",
        f"R$ {resumo_eb10.get('obsolescencia_anual_mecanizadas_brl', 0) / 1e6:,.1f} Mi",
        help="Custo anual de obsolescência da frota mecanizada legada e meios de apoio de fogo/logístico.",
    )
    st.caption(
        f"**Governança:** {resumo_eb10['governanca']} | "
        "**4 Eixos (Item 2.10):** Desenho Institucional, Capacidades, Doutrina e Pessoal | "
        "**5 Fatores de Efetividade (Item 1.7):** Superioridade de Informações, Letalidade, Sustentação, Proteção e Mobilidade | "
        "**Escalões Multidomínio (Item 3.1.3.2):** Corpo de Exército (ideal) e Divisão de Exército."
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
            "Enquadramento COEB / Sistema",
            options=["Automático (COEB)", "FEI", "FEP", "FEC", "SAUDE", "ENSINO"],
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
            "comando_militar_area",
            "regiao_militar",
            "uf",
            "brigada",
            "classificacao_coeb",
            "enquadramento_transformacao",
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
        "C Mil A",
        "RM",
        "UF",
        "Brigada / GU",
        "COEB",
        "Grupo / Módulo (EB10)",
        "IVE",
        "Status JEV",
        "C4ISR",
        "SPU (R$ Mi)",
        "Alertas",
    ]
    st.dataframe(df_tabela, use_container_width=True, height=440, hide_index=True)

st.divider()

# ------------------------------------------------------------------
# 2B. Guia Doutrinário: Significado do IVE, Faixas e Alternativas Viáveis
# ------------------------------------------------------------------
st.subheader("📘 Significado do IVE, Classificações JEV e Alternativas Viáveis")

with st.expander("🧮 Como o IVE (0–100) é calculado pelo Motor JEV", expanded=False):
    st.markdown(
        """
        O **Índice de Valor Estratégico (IVE)** mede a efetividade em combate e a aderência de cada OM à
        **Política de Transformação do Exército Brasileiro (EB10-P-01.031 / 2026)** e aos **PEECFA**,
        refletindo os 5 vetores do item 1.7 (*Superioridade de Informações, Letalidade, Sustentação, Proteção e Mobilidade*):

        - **Teeth-to-Tail (15%):** razão `efetivo_fim / cpfs_ativos` (peso do poder de combate e letalidade sobre a estrutura administrativa — item 3.1.3.1).
        - **Eficiência de Custeio (15%):** `total_empenhado / cpfs_ativos` auditado via CGU sob restrição orçamentária (item 2.2).
        - **Nível Tecnológico Força 4.0 (25%):** `indice_tecnologia_c4isr` — sensores, sistemas não tripulados, fogos de precisão, Ciber, Guerra Eletrônica e apoio à decisão (itens 1.3 e 3.2).
        - **Prontidão e Emprego (25%):** disponibilidade e acionamentos reais (SISLOG), sustentando a meta mínima de **20% do efetivo em elevado grau de prontidão** (itens 1.4 e 2.6).
        - **Geoestratégia e A2/AD (20%):** resposta inicial na faixa de fronteira, Amazônia/rotas críticas e proteção multidomínio.
        - **Multiplicador COEB (Item 3.1.1.2 / COEB 5.3.4.4):** `FEP — Prontidão (× 1,5)` *(5 Brigadas ForPron — 1ª prioridade)* | `FEI — Imediato (× 1,2)` *(12 Brigadas da Faixa de Fronteira e módulos multidomínio)* | `Sustentação Sanitária (× 1,15)` *(DSau/FUSEx)* | `Capacidade Institucional (× 1,10)` *(Ensino/DOAMEPI)* | `FEC — Continuado (× 0,95)` *(Reserva Estratégica, Defesa Territorial/Litoral — teto 65,5 pts sem virar Ponta de Lança)*.
        - **Penalidade de Auditoria (`-15%` por anomalia):** divergência `> 5%` entre custeio declarado e CGU, divergência `> 5%` entre efetivo SIGPES e CPFs ativos CGU, ou quebra de prontidão (`FEP < 85%` ou `FEI < 78%`).
        """
    )

col_p, col_z_fusao, col_zumbi = st.columns(3)

with col_p:
    st.success("### 🟢 Ponta de Lança (`IVE > 75`)")
    st.markdown(
        """
        **O que torna a OM Ponta de Lança:**
        - Enquadramento de 1ª prioridade (**FEP**) com pleno recompletamento de pessoal/material ou **FEI** estratégica na fronteira com alto A2/AD.
        - Elevada maturidade tecnológica **C4ISR**, alta taxa de **efetivo-fim** e disponibilidade **SISLOG ≥ 85%**.
        - Sem anomalias graves de auditoria CGU/SIGPES.

        **Alternativas Viáveis:**
        1. **Prioridade Máxima Força 4.0 (FEP):** concentrar injeção de IA, Guerra Eletrônica, Ciber e sistemas C4ISR.
        2. **Sanar Gargalo Doutrinário (se FEP com C4ISR < 50):** redirecionar verbas de alienação SPU para recompletamento imediato de sistemas/material.
        3. **Integração Fronteira–Núcleo:** conectar sensores de fronteira (**FEI**) à rede de C2 das grandes unidades **FEP**.
        """
    )

with col_z_fusao:
    st.warning("### 🟡 Zona de Fusão (`IVE 40 a 75`)")
    st.markdown(
        """
        **O que torna a OM Zona de Fusão:**
        - Tropas **FEI** debruçadas na fronteira (que operam em 2º plano de pessoal/material em relação às **FEP** no COEB) ou unidades **FEP** com C4ISR intermediário / penalizadas por queda de prontidão (`-15%`).
        - Maturidade tecnológica **C4ISR mediana (45–70)** ou lacunas pontuais de recompletamento material.

        **Alternativas Viáveis:**
        1. **Recompletamento Escalonado (Pós-FEP):** se **FEI** de fronteira, priorizar sensores ISR, comunicações táticas e logística de selva/fronteira após o atendimento do núcleo **FEP**.
        2. **Upgrade via Digital Twin:** captar capital de OMs Zumbi alienadas para elevar o índice C4ISR e migrar unidades **FEP** medianas para *Ponta de Lança*.
        3. **Unificação Modular / Recuperação SISLOG:** fundir encargos administrativos redundantes na guarnição e eliminar quebras de disponibilidade (`-15%`).
        """
    )

with col_zumbi:
    st.error("### 🔴 OM Zumbi (`IVE < 40`)")
    st.markdown(
        """
        **O que torna a OM Zumbi (Item 3.1.3.1):**
        - Estrutura de **Emprego Continuado (FEC)** (multiplicador `0,8`) ou administrativa que não agrega poder de combate/letalidade nem alinhamento pleno aos **PEECFA**.
        - Baixo índice **C4ISR (< 35)**, baixa proporção de tropa na atividade-fim e **alto Custo de Oportunidade Imobiliária** (SPU).
        - Penalidades acumuladas (`-15%` a `-30%`) por divergências **CGU × SIGPES** (> 5% em folha/inativos ou custeio).

        **Alternativas Viáveis:**
        1. **Otimização e Alienação via SPU (Item 3.1.3.1):** encerrar o CNPJ/UG, alienar ou permutar o imóvel urbano e capitalizar **FEP (Prontidão)**, **FEI (Fronteira)** e **Módulos Multidomínio** (simule no *Digital Twin* abaixo).
        2. **Rearticulação / Absorção Modular:** extinguir a autonomia de UG e consolidar encargos territoriais/de mobilização em outra OM da guarnição.
        3. **Saneamento Imediato de Folha/Custeio:** caso mantida para defesa territorial/mobilização, auditar CPFs inativos e corrigir o *burn rate* na CGU.
        """
    )

    st.info(
        "🏥 **Classificações Especiais JEV (COEB `EB20-MF-07.101` / `EB10-P-01.031`):** "
        "**`Sustentação Sanitária`** (`SAUDE` — `HCE`, `HMA`, `HGe`, `HGu`, `Policlínicas`) e "
        "**`Capacidade Institucional`** (`ENSINO` / **DECEx** — Escolas como `AMAN`, `ESA`/`EsSA`, `EsLog`/`EsSLog`, `EsAO`, `EsPCEx`, `ECEME`, `IME`, `CPORs`, "
        "os 15 Colégios Militares `SCMB`, órgãos culturais `DPHCEx`/`CEP` e Centros de Instrução/Adestramento como `CIGS`, `CI Bld`, `CA-Leste`) "
        "não são rotuladas como **OM Zumbi**, pois cumprem vocação assistencial (**FUSEx**) e de formação/adestramento (**DOAMEPI 5.6.1.4**). "
        "Igualmente, **não acrescem efetivo combatente (`FEP`)**, permanecendo auditáveis no eixo administrativo (`CGU/SIGPES`)."
    )

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
def _normalizar_busca(texto: Any) -> str:
    """Normaliza texto para filtro rápido sem distinção de maiúsculas ou acentos."""
    s = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower().strip()


def _filtrar_dataframe_om(df_base: pd.DataFrame, termo: str) -> pd.DataFrame:
    """Filtra DataFrame de OMs por termo textual normalizado nos campos principais."""
    termo_norm = _normalizar_busca(termo)
    if not termo_norm or df_base.empty:
        return df_base
    campos_busca = (
        df_base["sigla"].astype(str)
        + " " + df_base["codigo_uasg"].astype(str)
        + " " + df_base["cnpj_ug"].astype(str)
        + " " + df_base["brigada"].astype(str)
        + " " + df_base["uf"].astype(str)
        + " " + df_base["comando_militar_area"].astype(str)
        + " " + df_base["regiao_militar"].astype(str)
        + " " + df_base["enquadramento_transformacao"].astype(str)
    ).map(_normalizar_busca)
    return df_base[campos_busca.str.contains(termo_norm, regex=False, na=False)]


st.subheader("🔍 Diagnóstico Individual e Prescrição Doutrinária")
df_opcoes_diag = (df_filtrado if not df_filtrado.empty else df_all).copy()

f_col1, f_col2, f_col3, f_col4 = st.columns([2.0, 1.0, 1.2, 1.0])
with f_col1:
    diag_busca = st.text_input(
        "Filtrar OM (Sigla, UASG, Brigada, UF ou Sistema)",
        placeholder="Ex: 16º Esqd, CIGS, CMB, TG 02, HCE, PR, DECEx...",
        key="diag_filtro_texto",
    )
with f_col2:
    diag_coeb_local = st.selectbox(
        "Grupo COEB / Sistema",
        options=["Todos", "FEP", "FEI", "FEC", "SAUDE", "ENSINO"],
        key="diag_filtro_coeb",
    )
with f_col3:
    diag_jev_local = st.selectbox(
        "Diagnóstico JEV",
        options=[
            "Todos",
            "Ponta de Lança",
            "Zona de Fusão",
            "Sustentação Sanitária",
            "Capacidade Institucional",
            "OM Zumbi",
        ],
        key="diag_filtro_jev",
    )
with f_col4:
    diag_ordem = st.selectbox(
        "Ordenar por",
        options=["Maior IVE", "Sigla (A–Z)", "Maior Valor SPU", "Mais Alertas"],
        key="diag_ordem",
    )

if diag_coeb_local != "Todos":
    df_opcoes_diag = df_opcoes_diag[df_opcoes_diag["classificacao_coeb"] == diag_coeb_local]
if diag_jev_local != "Todos":
    df_opcoes_diag = df_opcoes_diag[df_opcoes_diag["classificacao_ive"] == diag_jev_local]
df_opcoes_diag = _filtrar_dataframe_om(df_opcoes_diag, diag_busca)

if diag_ordem == "Sigla (A–Z)":
    df_opcoes_diag = df_opcoes_diag.sort_values("sigla", ascending=True)
elif diag_ordem == "Maior Valor SPU":
    df_opcoes_diag = df_opcoes_diag.sort_values("valor_imovel_brl", ascending=False)
elif diag_ordem == "Mais Alertas":
    df_opcoes_diag = df_opcoes_diag.sort_values(["total_alertas", "nota_ive"], ascending=[False, True])
else:
    df_opcoes_diag = df_opcoes_diag.sort_values("nota_ive", ascending=False)

opcoes_om = {
    f"{r['sigla']} [{r['comando_militar_area']}/{r['uf']} • {r['brigada']}] ({r['classificacao_coeb']} — IVE {r['nota_ive']:.1f})": r["id_om"]
    for _, r in df_opcoes_diag.iterrows()
}

if not opcoes_om:
    st.warning("Nenhuma OM encontrada com os filtros informados nesta seção.")
    diag = None
else:
    st.caption(f"Exibindo **{len(opcoes_om)}** OM(s) correspondente(s) para seleção rápida:")
    label_om_sel = st.selectbox(
        "Selecione uma OM para inspeção detalhada:",
        list(opcoes_om.keys()),
        key="diag_select_om",
    )
    diag = carregar_diagnostico_om(opcoes_om[label_om_sel])

if diag:
    dados_op = diag.get("dados_operacionais", {})
    enq_eb10 = dados_op.get("enquadramento_transformacao", diag["classificacao_coeb"])
    cma_om = dados_op.get("comando_militar_area", "-")
    rm_om = dados_op.get("regiao_militar", "-")
    uf_om = dados_op.get("uf", "-")
    brig_om = dados_op.get("brigada", "-")
    st.caption(
        f"**Localização:** `{cma_om}` • `{rm_om}` • `{uf_om}` • **Brigada:** `{brig_om}` | "
        f"**EB10-P-01.031:** `{enq_eb10}` • UASG `{diag['codigo_uasg']}` • UG `{diag['cnpj_ug']}`"
    )
    c_a, c_b, c_c, c_d = st.columns(4)
    c_a.metric("Classificação JEV", diag["classificacao_ive"])
    c_b.metric("Nota IVE", f"{diag['nota_ive']:.1f}")
    c_c.metric("Índice C4ISR", f"{diag['indice_tecnologia_c4isr']:.1f}/100")
    c_d.metric("Custo / IVE", f"R$ {diag['indicador_financeiro_estrategico'] / 1e6:,.2f} Mi")

    comp = diag.get("componentes_ive", {})
    if comp:
        st.caption("**Decomposição dos 5 Pilares do IVE (notas 0–100 antes do multiplicador COEB e penalidades):**")
        p1, p2, p3, p4, p5 = st.columns(5)
        p1.metric("Teeth-to-Tail (15%)", f"{comp.get('teeth_to_tail', 0):.1f}")
        p2.metric("Efic. Custeio (15%)", f"{comp.get('eficiencia_custeio', 0):.1f}")
        p3.metric("C4ISR 4.0 (25%)", f"{comp.get('nivel_tecnologico_c4isr', 0):.1f}")
        p4.metric("Prontidão (25%)", f"{comp.get('prontidao_emprego', 0):.1f}")
        p5.metric("Geo/A2AD (20%)", f"{comp.get('geoestrategia_a2ad', 0):.1f}")

    if diag.get("classificacao_coeb") == "SAUDE" or dados_op.get("indice_eficiencia_hospitalar") is not None:
        st.caption("**🏥 Indicadores de Eficiência Hospitalar & Assistencial (SAMMED / FUSEx — DSau):**")
        h1, h2, h3, h4, h5, h6 = st.columns(6)
        h1.metric("Índice Eficiência Hosp.", f"{dados_op.get('indice_eficiencia_hospitalar', 0):.1f}/100")
        h2.metric("Atendimentos/Ano", f"{dados_op.get('atendimentos_ano', 0):,}")
        h3.metric("Beneficiários FUSEx", f"{dados_op.get('beneficiarios_fusex', 0):,}")
        leitos_op = dados_op.get("leitos_operacionais", 0)
        h4.metric("Leitos Operacionais", f"{leitos_op}" if leitos_op > 0 else "Ambulatorial")
        h5.metric("Ocupação / Giro", f"{dados_op.get('taxa_ocupacao_leitos_pct', 0):.1f}%")
        h6.metric(
            "Resolutividade Própria",
            f"{dados_op.get('resolutividade_propria_pct', 0):.1f}%",
            delta=f"R$ {dados_op.get('custo_medio_atendimento_brl', 0):,.0f}/atend.",
            delta_color="off",
        )

    if dados_op.get("categoria_forca_blindada"):
        st.caption(f"**🛡️ Dotação Prg EE Forças Blindadas / Mecanizadas & Custo de Obsolescência — {dados_op['categoria_forca_blindada']}:**")
        b1, b2, b3 = st.columns(3)
        b1.metric("CAPEX Aquisição / Modernização", f"R$ {dados_op.get('capex_aquisicao_brl', 0) / 1e6:,.1f} Mi")
        b2.metric("Custo Obsolescência Material/ano", f"R$ {dados_op.get('custo_obsolescencia_anual_brl', 0) / 1e6:,.1f} Mi")
        b3.metric("Exposição Obsolescência Frota", f"{dados_op.get('obsolescencia_material_pct', 0):.1f}%")
        st.caption("**Meios e Capacidades Requeridas:** " + " • ".join(dados_op.get("plataformas_requeridas", [])))

    st.info(f"**Prescrição Doutrinária:** {diag['prescricao_doutrinaria']}")

    if diag["classificacao_ive"] == "Ponta de Lança":
        alternativas_om = (
            "1) Manter prioridade máxima de recompletamento (pessoal, material, sistemas) e dotação SISLOG; "
            "2) Se C4ISR < 50 (Gargalo FEP), redirecionar capital de alienações SPU para modernização C2/C4ISR; "
            "3) Consolidar integração em rede multidomínio Força 4.0."
        )
    elif diag["classificacao_ive"] == "Zona de Fusão":
        alternativas_om = (
            "1) Se FEI de fronteira (2º plano relativo às FEP), priorizar sensores ISR e logística de fronteira após cobertura FEP; "
            "2) Se FEP mediana, receber aporte via Digital Twin (alienação de OMs Zumbi) para upgrade C4ISR; "
            "3) Avaliar unificação modular na guarnição e sanar eventuais quebras de prontidão no SISLOG."
        )
    elif diag["classificacao_ive"] == "Sustentação Sanitária":
        alternativas_om = (
            "1) Preservar integralmente a vocação assistencial (FUSEx / Eixo Pessoal 3.4.7) — vedada alienação como OM Zumbi; "
            "2) Manter núcleo de Saúde Operacional pronto para desdobramento como Módulo de Apoio Ampliado à FTC (COEB 5.3.4.4 e), sem inflar cômputo combatente (FEP); "
            "3) Se houver alerta CGU/SIGPES, racionalizar exclusivamente contratos e área-meio administrativa (item 3.1.3.1)."
        )
    elif diag["classificacao_ive"] == "Capacidade Institucional":
        alternativas_om = (
            "1) Preservar infraestrutura de Ensino/Formação (COEB 5.6.1.4 e DOAMEPI Educação 5.6.1.3.2 e) — vedada alienação como OM Zumbi; "
            "2) Atualizar currículos de liderança e emprego multidomínio (item 3.4.8 / COEB 5.6.2); "
            "3) Auditar área-meio administrativa e divergências CGU/SIGPES."
        )
    else:
        alternativas_om = (
            "1) Desativação com encerramento de CNPJ/UG e alienação/permuta do imóvel SPU para capitalizar forças FEP (1ª prioridade) e FEI de fronteira; "
            "2) Absorção das atividades de guarnição/guarda por outra OM próxima; "
            "3) Se mantida, auditar divergências >5% de folha (inativos) e custeio na CGU."
        )
    st.markdown(f"**Alternativas Viáveis para esta OM:** {alternativas_om}")

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
    "conversão em capacidade **C4ISR** e modernização de frota para uma unidade prioritária ou blindada/mecanizada."
)

df_zumbis_base = df_all[
    (df_all["classificacao_coeb"] == "FEC")
    & (df_all["classificacao_ive"] == "OM Zumbi")
].copy()
if df_zumbis_base.empty:
    df_zumbis_base = df_all[
        ~df_all["classificacao_ive"].isin(["Sustentação Sanitária", "Capacidade Institucional"])
    ].nsmallest(10, "nota_ive").copy()

df_destinos_base = df_all[
    ~df_all["classificacao_ive"].isin(["Sustentação Sanitária", "Capacidade Institucional"])
].copy()

cmas_dt = ["Todos"] + sorted([c for c in df_all["comando_militar_area"].dropna().unique().tolist() if c])

col_s1, col_s2 = st.columns(2)
with col_s1:
    st.markdown("**1. Origem — OM Zumbi (FEC) a Desativar / Alienar**")
    z_f1, z_f2 = st.columns([1.4, 1.0])
    with z_f1:
        busca_zumbi = st.text_input(
            "Pesquisar OM Origem",
            placeholder="Ex: 2º BG, AGR, CML, RJ, DSup...",
            key="dt_busca_zumbi",
        )
    with z_f2:
        cma_zumbi = st.selectbox("C Mil A (Origem)", options=cmas_dt, key="dt_cma_zumbi")
    ordem_zumbi = st.selectbox(
        "Ordenar Origens por",
        options=["Maior Valor SPU", "Menor IVE", "Sigla (A–Z)"],
        key="dt_ordem_zumbi",
    )

    df_zumbis = df_zumbis_base
    if cma_zumbi != "Todos":
        df_zumbis = df_zumbis[df_zumbis["comando_militar_area"] == cma_zumbi]
    df_zumbis = _filtrar_dataframe_om(df_zumbis, busca_zumbi)
    if ordem_zumbi == "Menor IVE":
        df_zumbis = df_zumbis.sort_values("nota_ive", ascending=True)
    elif ordem_zumbi == "Sigla (A–Z)":
        df_zumbis = df_zumbis.sort_values("sigla", ascending=True)
    else:
        df_zumbis = df_zumbis.sort_values("valor_imovel_brl", ascending=False)

    mapa_zumbis = {
        f"{r['sigla']} [{r['comando_militar_area']}/{r['uf']}] ({r['classificacao_coeb']} | IVE {r['nota_ive']:.1f} | SPU R$ {r['valor_imovel_brl']/1e6:.0f} Mi)": r["id_om"]
        for _, r in df_zumbis.iterrows()
    }
    st.caption(f"Exibindo **{len(mapa_zumbis)}** OM(s) Zumbi(s) para alienação:")
    sel_zumbi = (
        st.selectbox(
            "Selecione a OM Zumbi (FEC):",
            list(mapa_zumbis.keys()),
            key="dt_select_zumbi",
        )
        if mapa_zumbis
        else None
    )

with col_s2:
    st.markdown("**2. Destino — OM a Recompletar / Modernizar**")
    d_f1, d_f2 = st.columns([1.4, 1.0])
    with d_f1:
        busca_destino = st.text_input(
            "Pesquisar OM Destino",
            placeholder="Ex: 3º RCC, 20º BIB, 1º RC Mec, BInt, FEP...",
            key="dt_busca_destino",
        )
    with d_f2:
        filtro_cat_dest = st.selectbox(
            "Perfil de Emprego",
            options=[
                "FEP e FEI (Prioritárias)",
                "Somente FEP (ForPron)",
                "Somente FEI (Fronteira/Multidomínio)",
                "Brigadas Blindadas (Lagartas)",
                "Brigadas Mecanizadas (Rodas)",
                "Todas Operativas (FEP/FEI/FEC)",
            ],
            key="dt_perfil_destino",
        )
    ordem_dest = st.selectbox(
        "Ordenar Destinos por",
        options=["Menor C4ISR (Priorizar Gargalos)", "Maior IVE", "Sigla (A–Z)"],
        key="dt_ordem_destino",
    )

    df_destinos = df_destinos_base
    if filtro_cat_dest == "FEP e FEI (Prioritárias)":
        df_destinos = df_destinos[df_destinos["classificacao_coeb"].isin(["FEP", "FEI"])]
    elif filtro_cat_dest == "Somente FEP (ForPron)":
        df_destinos = df_destinos[df_destinos["classificacao_coeb"] == "FEP"]
    elif filtro_cat_dest == "Somente FEI (Fronteira/Multidomínio)":
        df_destinos = df_destinos[df_destinos["classificacao_coeb"] == "FEI"]
    elif filtro_cat_dest == "Brigadas Blindadas (Lagartas)":
        df_destinos = df_destinos[
            df_destinos["brigada"].isin(BRIGADAS_BLINDADAS)
            | df_destinos["sigla"].str.contains("2º RCC", na=False)
        ]
    elif filtro_cat_dest == "Brigadas Mecanizadas (Rodas)":
        df_destinos = df_destinos[df_destinos["brigada"].isin(BRIGADAS_MECANIZADAS)]

    df_destinos = _filtrar_dataframe_om(df_destinos, busca_destino)
    if ordem_dest == "Maior IVE":
        df_destinos = df_destinos.sort_values("nota_ive", ascending=False)
    elif ordem_dest == "Sigla (A–Z)":
        df_destinos = df_destinos.sort_values("sigla", ascending=True)
    else:
        df_destinos = df_destinos.sort_values(["indice_tecnologia_c4isr", "nota_ive"], ascending=[True, False])

    mapa_destinos = {
        f"{r['sigla']} [{r['comando_militar_area']}/{r['uf']} • {r['brigada']}] ({r['classificacao_coeb']} | C4ISR {r['indice_tecnologia_c4isr']:.1f} | IVE {r['nota_ive']:.1f})": r["id_om"]
        for _, r in df_destinos.iterrows()
    }
    id_zumbi_sel = mapa_zumbis[sel_zumbi] if sel_zumbi else None
    chaves_dest = [k for k in mapa_destinos.keys() if mapa_destinos[k] != id_zumbi_sel]
    st.caption(f"Exibindo **{len(chaves_dest)}** OM(s) destino elegível(eis):")
    sel_destino = (
        st.selectbox(
            "Selecione a OM Destino:",
            chaves_dest,
            key="dt_select_destino",
        )
        if chaves_dest
        else None
    )

if not sel_zumbi or not sel_destino:
    st.warning("Ajuste os filtros de Origem ou Destino do Digital Twin para selecionar duas OMs distintas.")
elif st.button("🚀 Simular Transformação Doutrinária", type="primary"):
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
    if d.get("categoria_forca_blindada"):
        dt1, dt2, dt3 = st.columns(3)
        dt1.metric("Enquadramento Frota", d["categoria_forca_blindada"].split("(")[0].strip())
        dt2.metric("Cobertura CAPEX Frota/C4ISR", f"{d.get('cobertura_capex_blindado_pct', 0):.1f}%")
        dt3.metric("Abatimento Obsolescência/ano", f"R$ {d.get('economia_obsolescencia_anual_brl', 0) / 1e6:,.2f} Mi")
        st.caption("**Prioridade de Aquisição:** " + " • ".join(d.get("plataformas_requeridas", [])))
    with st.expander("Detalhes Técnicos da Simulação (CNPJ UG, CPFs e Tesouro)"):
        st.json(resultado)
