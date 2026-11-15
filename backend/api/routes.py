"""Endpoints FastAPI do SIGA-F4 (Motor JEV, Captação UASG/UG e Digital Twin)."""

import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.digital_twin import simular_reestruturacao
from backend.core.motor_jev import MotorIVE
from backend.models.database import get_db
from backend.models.schemas import ClassificacaoCOEB, OM
from backend.services.cgu_sync import TransparenciaSyncService

router = APIRouter(prefix="/api", tags=["SIGA-F4"])


class SimulacaoRequest(BaseModel):
    """Payload para simulação de reestruturação no Digital Twin."""

    id_om_zumbi: int = Field(..., gt=0, description="ID da OM Zumbi (FEC) a ser desativada")
    id_om_fei_destino: int = Field(..., gt=0, description="ID da OM destino a ser modernizada")


class CapturaUasgRequest(BaseModel):
    """Payload para captação/sincronização de OM via código UASG ou UG."""

    codigo_uasg_ou_ug: str = Field(..., min_length=4, description="Código UASG (ex: 160069) ou UG/CNPJ")
    classificacao_coeb: Optional[ClassificacaoCOEB] = Field(
        default=None, description="Enquadramento COEB opcional (inferido automaticamente se omitido)"
    )
    indice_tecnologia_c4isr: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    papel_a2ad: Optional[bool] = Field(default=None)


class OMRankingItem(BaseModel):
    """Resumo de OM para o ranking estratégico (GET /api/oms)."""

    ranking: int
    id_om: int
    sigla: str
    codigo_uasg: str
    cnpj_ug: str
    classificacao_coeb: str
    indice_tecnologia_c4isr: float
    papel_a2ad: bool
    valor_imovel_brl: float
    nota_ive: float
    classificacao_ive: str
    foco_estrategico: str
    indicador_financeiro_estrategico: float
    total_alertas: int
    enquadramento_transformacao: str = ""
    comando_militar_area: str = ""
    regiao_militar: str = ""
    uf: str = ""
    brigada: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@router.get("/oms", response_model=List[OMRankingItem])
def listar_oms_ranking(
    coeb: Optional[ClassificacaoCOEB] = Query(
        default=None, description="Filtro opcional por classificação COEB (FEI, FEP, FEC)"
    ),
    uasg: Optional[str] = Query(
        default=None, description="Filtro opcional por código UASG ou dígitos da UG/CNPJ"
    ),
    cma: Optional[str] = Query(
        default=None, description="Filtro opcional por Comando Militar de Área (ex: CMA, CMS)"
    ),
    rm: Optional[str] = Query(
        default=None, description="Filtro opcional por Região Militar (ex: 3ª RM, 12ª RM)"
    ),
    uf: Optional[str] = Query(
        default=None, description="Filtro opcional por UF (ex: AM, RJ, RS, SP)"
    ),
    brigada: Optional[str] = Query(
        default=None, description="Filtro opcional por Brigada / Grande Comando"
    ),
    db: Session = Depends(get_db),
) -> List[OMRankingItem]:
    """Retorna o ranking das OMs com IVE, Valor SPU, UASG/UG e localização territorial."""
    motor = MotorIVE()
    diagnosticos = motor.diagnosticar_todas(db, persistir_alertas=True)

    if coeb is not None:
        diagnosticos = [d for d in diagnosticos if d.classificacao_coeb == coeb.value]

    if uasg:
        termo = re.sub(r"\D", "", uasg) or uasg.strip()
        diagnosticos = [
            d
            for d in diagnosticos
            if termo in d.codigo_uasg or termo in re.sub(r"\D", "", d.cnpj_ug)
        ]

    for campo, valor_filtro in (
        ("comando_militar_area", cma),
        ("regiao_militar", rm),
        ("uf", uf),
        ("brigada", brigada),
    ):
        if valor_filtro:
            termo_loc = valor_filtro.strip().lower()
            diagnosticos = [
                d
                for d in diagnosticos
                if termo_loc in str(d.dados_operacionais.get(campo, "")).lower()
            ]

    return [
        OMRankingItem(
            ranking=idx,
            id_om=d.id_om,
            sigla=d.sigla,
            codigo_uasg=d.codigo_uasg,
            cnpj_ug=d.cnpj_ug,
            classificacao_coeb=d.classificacao_coeb,
            indice_tecnologia_c4isr=d.indice_tecnologia_c4isr,
            papel_a2ad=d.papel_a2ad,
            valor_imovel_brl=d.valor_imovel_brl,
            nota_ive=d.nota_ive,
            classificacao_ive=d.classificacao_ive,
            foco_estrategico=d.foco_estrategico,
            indicador_financeiro_estrategico=d.indicador_financeiro_estrategico,
            total_alertas=len(d.alertas_auditoria),
            enquadramento_transformacao=d.dados_operacionais.get("enquadramento_transformacao", ""),
            comando_militar_area=d.dados_operacionais.get("comando_militar_area", ""),
            regiao_militar=d.dados_operacionais.get("regiao_militar", ""),
            uf=d.dados_operacionais.get("uf", ""),
            brigada=d.dados_operacionais.get("brigada", ""),
            latitude=d.dados_operacionais.get("latitude"),
            longitude=d.dados_operacionais.get("longitude"),
        )
        for idx, d in enumerate(diagnosticos, start=1)
    ]


@router.get("/politica-transformacao")
def obter_resumo_politica_transformacao(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retorna indicadores de aderência à Política de Transformação do Exército (EB10-P-01.031)."""
    motor = MotorIVE()
    diagnosticos = motor.diagnosticar_todas(db, persistir_alertas=False)
    return motor.resumo_politica_transformacao(diagnosticos)


@router.get("/oms/uasg/{codigo}")
def buscar_om_por_uasg_ou_ug(codigo: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Localiza e diagnostica uma OM diretamente pelo código UASG ou UG/CNPJ."""
    digitos = re.sub(r"\D", "", codigo)
    if not digitos:
        raise HTTPException(status_code=400, detail="Código UASG/UG inválido.")

    om = db.query(OM).filter(OM.codigo_uasg == digitos.zfill(6)).first()
    if not om:
        oms = db.query(OM).all()
        om = next((item for item in oms if digitos in re.sub(r"\D", "", item.cnpj_ug)), None)

    if not om:
        raise HTTPException(
            status_code=404,
            detail=f"OM com UASG/UG '{codigo}' não encontrada na base. Use POST /api/oms/capturar-uasg.",
        )

    return MotorIVE().diagnosticar_om(db, om, persistir_alertas=True).to_dict()


@router.post("/oms/capturar-uasg")
def capturar_om_por_uasg_ou_ug(
    payload: CapturaUasgRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Capta ou atualiza uma OM a partir do código UASG/UG na API Compras.gov.br e CGU."""
    service = TransparenciaSyncService()
    try:
        resultado = service.capturar_om_por_uasg(
            db=db,
            codigo_uasg_ou_ug=payload.codigo_uasg_ou_ug,
            coeb_override=payload.classificacao_coeb,
            c4isr_override=payload.indice_tecnologia_c4isr,
            papel_a2ad_override=payload.papel_a2ad,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    om = db.query(OM).filter(OM.id_om == resultado["id_om"]).first()
    diag = MotorIVE().diagnosticar_om(db, om, persistir_alertas=True).to_dict()
    return {
        "acao": resultado["acao"],
        "origem_dados": resultado["origem_dados"],
        "diagnostico": diag,
    }


@router.get("/oms/{id_om}/diagnostico")
def obter_diagnostico_om(id_om: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retorna diagnóstico JEV completo: alertas CGU, L.A. doutrinária e índice C4ISR."""
    om = db.query(OM).filter(OM.id_om == id_om).first()
    if not om:
        raise HTTPException(status_code=404, detail=f"OM com id={id_om} não encontrada.")

    motor = MotorIVE()
    return motor.diagnosticar_om(db, om, persistir_alertas=True).to_dict()


@router.post("/simulador/reestruturar")
def executar_simulacao_reestruturacao(
    payload: SimulacaoRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Simula alienação de OM Zumbi e conversão de capital/CPFs para OM FEI destino."""
    try:
        return simular_reestruturacao(
            db=db,
            id_om_zumbi=payload.id_om_zumbi,
            id_om_fei_destino=payload.id_om_fei_destino,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "não encontrada" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
