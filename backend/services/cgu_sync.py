"""Serviço de integração com Compras.gov.br (UASG/UG) e Portal da Transparência (CGU)."""

import os
import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from backend.models.schemas import (
    ClassificacaoCOEB,
    DoutrinaTecnologia,
    Estrategia,
    OM,
    PatrimonioUniao,
    Sigpes,
    Sislog,
    TransparenciaDados,
)
from backend.services.geo_locator import GeoLocatorService

# Coordenadas de fallback por UF para garantir plotagem imediata caso o Nominatim oscile
CAPITAIS_UF: Dict[str, Tuple[float, float]] = {
    "AC": (-9.9747, -67.8100),
    "AL": (-9.6658, -35.7353),
    "AM": (-3.1190, -60.0217),
    "AP": (0.0344, -51.0664),
    "BA": (-12.9714, -38.5014),
    "CE": (-3.7172, -38.5431),
    "DF": (-15.7939, -47.8828),
    "ES": (-20.3155, -40.3128),
    "GO": (-16.6869, -49.2648),
    "MA": (-2.5297, -44.3028),
    "MG": (-19.9167, -43.9344),
    "MS": (-20.4697, -54.6201),
    "MT": (-15.6011, -56.0972),
    "PA": (-1.4558, -48.5039),
    "PB": (-7.1150, -34.8631),
    "PE": (-8.0476, -34.8770),
    "PI": (-5.0892, -42.8019),
    "PR": (-25.4284, -49.2733),
    "RJ": (-22.9068, -43.1729),
    "RN": (-5.7944, -35.2111),
    "RO": (-8.7619, -63.9039),
    "RR": (2.8200, -60.6733),
    "RS": (-30.0346, -51.2177),
    "SC": (-27.5954, -48.5480),
    "SE": (-10.9472, -37.0731),
    "SP": (-23.5505, -46.6333),
    "TO": (-10.1844, -48.3336),
}


def formatar_cnpj(valor: Optional[str], fallback_uasg: str) -> str:
    """Normaliza dígitos de CNPJ para o formato XX.XXX.XXX/XXXX-XX."""
    digitos = re.sub(r"\D", "", valor or "")
    if not digitos:
        # Gera identificador UG determinístico compatível quando a API omitir CNPJ específico
        digitos = f"00394452{fallback_uasg.zfill(6)}"
    digitos = digitos.zfill(14)[:14]
    return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:14]}"


def inferir_enquadramento_coeb(nome_uasg: str) -> Tuple[ClassificacaoCOEB, float, bool]:
    """Classifica automaticamente uma OM (FEI, FEP ou FEC) a partir da denominação oficial."""
    nome = nome_uasg.upper()

    termos_fei = (
        "SELVA",
        "FRONTEIRA",
        "PQDT",
        "PARAQUED",
        "AEROMOVEL",
        "OPERAÇÕES ESPECIAIS",
        "OPERACOES ESPECIAIS",
        "COMANDOS",
        "CIBER",
        "GUERRA ELETRÔNICA",
        "GUERRA ELETRONICA",
        "INTELIGÊNCIA",
        "INTELIGENCIA",
        "AVIAÇÃO",
        "AVIACAO",
        "ANTIAÉRE",
        "ANTIAERE",
        "MÍSSEIS",
        "MISSEIS",
        "FOGUETES",
        "TELEMÁTICA",
        "TELEMATICA",
        "SISTEMAS",
        "TECNOL",
    )
    if any(t in nome for t in termos_fei):
        c4isr = 88.0 if any(t in nome for t in ("CIBER", "INTELIG", "GUERRA ELETR", "SISTEMAS", "TELEM")) else 74.0
        return (ClassificacaoCOEB.FEI, c4isr, True)

    termos_fep = (
        "BLINDAD",
        "MECANIZAD",
        "ARTILHARIA",
        "CAVALARIA",
        "ENGENHARIA",
        "COMUNICAÇÕES",
        "COMUNICACOES",
        "LOGÍSTIC",
        "LOGISTIC",
        "MONTANHA",
        "CAATINGA",
        "PANTANAL",
    )
    if any(t in nome for t in termos_fep):
        return (ClassificacaoCOEB.FEP, 62.0, "BLINDAD" in nome or "MECANIZAD" in nome)

    return (ClassificacaoCOEB.FEC, 26.0, False)


class TransparenciaSyncService:
    """Capta OMs por UASG/UG (Compras.gov.br) e sincroniza execução orçamentária via CGU."""

    BASE_URL = "https://api.portaldatransparencia.gov.br/api-de-dados"
    COMPRAS_UASG_URL = "https://dadosabertos.compras.gov.br/modulo-uasg/1_consultarUasg"

    def __init__(self, api_key: Optional[str] = None, timeout: float = 15.0):
        self.api_key = api_key or os.getenv("CGU_API_KEY")
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["chave-api-dados"] = self.api_key
        return headers

    def consultar_uasg_comprasnet(self, codigo_uasg_ou_ug: str) -> Optional[Dict[str, Any]]:
        """Consulta dados oficiais de uma UASG/UG na API aberta do Compras.gov.br."""
        digitos = re.sub(r"\D", "", codigo_uasg_ou_ug)
        if not digitos:
            return None
        codigo_uasg = digitos[:6].zfill(6)

        with httpx.Client(timeout=self.timeout) as client:
            for status in ("true", "false"):
                try:
                    resp = client.get(
                        self.COMPRAS_UASG_URL,
                        params={"codigoUasg": codigo_uasg, "statusUasg": status, "pagina": 1},
                        headers={"Accept": "application/json"},
                    )
                    if resp.status_code == 404:
                        continue
                    resp.raise_for_status()
                    payload = resp.json()
                    resultados = payload.get("resultado") or []
                    if resultados:
                        item = resultados[0]
                        cnpj_bruto = item.get("cnpjCpfUasg") or item.get("cnpjCpfOrgao")
                        return {
                            "origem": "compras_gov_br",
                            "codigo_uasg": str(item.get("codigoUasg", codigo_uasg)).zfill(6),
                            "nome_uasg": item.get("nomeUasg") or f"UG {codigo_uasg}",
                            "cnpj_ug": formatar_cnpj(cnpj_bruto, codigo_uasg),
                            "municipio": item.get("nomeMunicipioIbge") or "Brasília",
                            "uf": (item.get("siglaUf") or "DF").upper(),
                            "codigo_orgao": item.get("codigoOrgao"),
                            "status_ativo": bool(item.get("statusUasg", True)),
                        }
                except httpx.HTTPError:
                    continue
        return None

    def consultar_despesas_uasg(self, codigo_uasg: str, ano_mes: str) -> Dict[str, Any]:
        """Consulta despesas empenhadas para uma UASG na API do Portal da Transparência."""
        if not self.api_key:
            return {
                "origem": "mock_fallback",
                "codigo_uasg": codigo_uasg,
                "ano_mes": ano_mes,
                "total_empenhado": None,
                "cpfs_ativos": None,
                "cpfs_reserva": None,
            }

        ano = ano_mes.split("-")[0]
        url = f"{self.BASE_URL}/despesas/por-orgao"
        params = {"ano": ano, "codigoOrgao": codigo_uasg, "pagina": 1}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self._headers(), params=params)
                resp.raise_for_status()
                payload = resp.json()

            total_empenhado = (
                sum(float(item.get("empenhado", 0.0)) for item in payload)
                if isinstance(payload, list)
                else 0.0
            )
            return {
                "origem": "api_oficial",
                "codigo_uasg": codigo_uasg,
                "ano_mes": ano_mes,
                "total_empenhado": total_empenhado,
                "cpfs_ativos": None,
                "cpfs_reserva": None,
            }
        except httpx.HTTPError as exc:
            return {
                "origem": "erro_api",
                "erro": str(exc),
                "codigo_uasg": codigo_uasg,
                "ano_mes": ano_mes,
                "total_empenhado": None,
                "cpfs_ativos": None,
                "cpfs_reserva": None,
            }

    def sincronizar_om(self, db: Session, id_om: int, ano_mes: Optional[str] = None) -> Optional[TransparenciaDados]:
        """Atualiza ou insere registro de transparência para uma OM específica."""
        om = db.query(OM).filter(OM.id_om == id_om).first()
        if not om:
            return None

        competencia = ano_mes or datetime.now().strftime("%Y-%m")
        dados_api = self.consultar_despesas_uasg(om.codigo_uasg, competencia)

        registro = (
            db.query(TransparenciaDados)
            .filter(TransparenciaDados.id_om == id_om, TransparenciaDados.ano_mes == competencia)
            .first()
        )

        if dados_api.get("total_empenhado") is not None:
            if registro is None:
                registro = TransparenciaDados(
                    id_om=id_om,
                    ano_mes=competencia,
                    total_empenhado=dados_api["total_empenhado"],
                    cpfs_ativos=dados_api.get("cpfs_ativos") or 0,
                    cpfs_reserva=dados_api.get("cpfs_reserva") or 0,
                )
                db.add(registro)
            else:
                registro.total_empenhado = dados_api["total_empenhado"]
            db.commit()
            db.refresh(registro)

        return registro

    def capturar_om_por_uasg(
        self,
        db: Session,
        codigo_uasg_ou_ug: str,
        coeb_override: Optional[ClassificacaoCOEB] = None,
        c4isr_override: Optional[float] = None,
        papel_a2ad_override: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Capta (ou atualiza) uma OM pelo código de UASG ou UG consultando Compras.gov.br e CGU."""
        digitos = re.sub(r"\D", "", codigo_uasg_ou_ug)
        if len(digitos) < 4:
            raise ValueError("Informe um código UASG/UG válido (mínimo 4 dígitos, padrão 6 dígitos ex: 160069).")

        codigo_6 = digitos[:6].zfill(6)

        # Verifica se já existe por UASG ou por dígitos de UG/CNPJ
        om_existente = db.query(OM).filter(OM.codigo_uasg == codigo_6).first()
        if not om_existente and len(digitos) >= 8:
            om_existente = (
                db.query(OM)
                .filter(OM.cnpj_ug == formatar_cnpj(digitos, codigo_6))
                .first()
            )

        dados_oficiais = self.consultar_uasg_comprasnet(codigo_6)

        if not dados_oficiais and not om_existente:
            raise ValueError(
                f"UASG/UG '{codigo_uasg_ou_ug}' não localizada na API Compras.gov.br nem na base local."
            )

        if om_existente:
            if dados_oficiais:
                om_existente.sigla = dados_oficiais["nome_uasg"][:40]
                om_existente.endereco = f"{dados_oficiais['municipio']} - {dados_oficiais['uf']}"
                if coeb_override and om_existente.doutrina_tecnologia:
                    om_existente.doutrina_tecnologia.classificacao_coeb = coeb_override
                if c4isr_override is not None and om_existente.doutrina_tecnologia:
                    om_existente.doutrina_tecnologia.indice_tecnologia_c4isr = c4isr_override
                if papel_a2ad_override is not None and om_existente.doutrina_tecnologia:
                    om_existente.doutrina_tecnologia.papel_a2ad = papel_a2ad_override
                db.commit()
                db.refresh(om_existente)

            self.sincronizar_om(db, om_existente.id_om)
            return {
                "acao": "atualizada",
                "origem_dados": dados_oficiais["origem"] if dados_oficiais else "base_local",
                "dados_oficiais": dados_oficiais,
                "id_om": om_existente.id_om,
            }

        # Criação de nova OM a partir dos dados capturados na API oficial
        assert dados_oficiais is not None
        coeb_inf, c4isr_inf, a2ad_inf = inferir_enquadramento_coeb(dados_oficiais["nome_uasg"])
        coeb = coeb_override or coeb_inf
        c4isr = c4isr_override if c4isr_override is not None else c4isr_inf
        papel_a2ad = papel_a2ad_override if papel_a2ad_override is not None else a2ad_inf

        municipio = dados_oficiais["municipio"]
        uf = dados_oficiais["uf"]
        coords = GeoLocatorService().geocodificar_endereco(f"{municipio}, {uf}")
        if not coords:
            coords = CAPITAIS_UF.get(uf, (-15.7939, -47.8828))

        # Evita colisão caso o mesmo CNPJ apareça em unidade espelho
        cnpj_ug = dados_oficiais["cnpj_ug"]
        if db.query(OM).filter(OM.cnpj_ug == cnpj_ug).first():
            cnpj_ug = formatar_cnpj(f"00394452{codigo_6}", codigo_6)

        rip_spu = f"RIP-UG-{codigo_6}"
        om = OM(
            codigo_uasg=dados_oficiais["codigo_uasg"],
            rip_spu=rip_spu,
            cnpj_ug=cnpj_ug,
            sigla=dados_oficiais["nome_uasg"][:40],
            cep="70000-000",
            endereco=f"{municipio} - {uf}",
            latitude=coords[0],
            longitude=coords[1],
            alertas_auditoria=[],
        )
        db.add(om)
        db.flush()

        efetivo_base = 220 if coeb == ClassificacaoCOEB.FEI else 480 if coeb == ClassificacaoCOEB.FEP else 310
        custeio_base = float(efetivo_base * 65_000)
        valor_spu_base = 45_000_000.0 if coeb == ClassificacaoCOEB.FEI else 95_000_000.0 if coeb == ClassificacaoCOEB.FEP else 180_000_000.0

        db.add(
            DoutrinaTecnologia(
                id_om=om.id_om,
                classificacao_coeb=coeb,
                indice_tecnologia_c4isr=c4isr,
                papel_a2ad=papel_a2ad,
            )
        )
        db.add(PatrimonioUniao(id_om=om.id_om, rip_spu=rip_spu, valor_imovel_brl=valor_spu_base))
        db.add(
            Sigpes(
                id_om=om.id_om,
                efetivo_total_declarado=efetivo_base,
                efetivo_fim=int(efetivo_base * (0.85 if coeb == ClassificacaoCOEB.FEI else 0.62 if coeb == ClassificacaoCOEB.FEP else 0.40)),
                custeio_declarado_brl=custeio_base,
            )
        )
        db.add(
            TransparenciaDados(
                id_om=om.id_om,
                ano_mes=datetime.now().strftime("%Y-%m"),
                total_empenhado=custeio_base,
                cpfs_ativos=efetivo_base,
                cpfs_reserva=18,
            )
        )
        db.add(
            Sislog(
                id_om=om.id_om,
                acionamentos_reais_36m=28 if coeb == ClassificacaoCOEB.FEI else 12 if coeb == ClassificacaoCOEB.FEP else 2,
                taxa_disponibilidade=92.0 if coeb == ClassificacaoCOEB.FEI else 86.0 if coeb == ClassificacaoCOEB.FEP else 64.0,
            )
        )
        db.add(
            Estrategia(
                id_om=om.id_om,
                dist_fronteira_km=120.0 if uf in ("AM", "RR", "AC", "RO", "AP", "MS", "MT", "RS", "PR", "SC") else 950.0,
                area_urbana=True,
            )
        )
        db.commit()
        db.refresh(om)

        self.sincronizar_om(db, om.id_om)
        return {
            "acao": "criada",
            "origem_dados": dados_oficiais["origem"],
            "dados_oficiais": dados_oficiais,
            "id_om": om.id_om,
        }
