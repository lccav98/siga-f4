"""Endpoints FastAPI do SIGA-F4 (Motor JEV e Digital Twin)."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.digital_twin import simular_reestruturacao
from backend.core.motor_jev import MotorIVE
from backend.models.database import get_db
from backend.models.schemas import ClassificacaoCOEB, OM

router = APIRouter(prefix="/api", tags=["SIGA-F4"])


class SimulacaoRequest(BaseModel):
    """Payload para simulação de reestruturação no Digital Twin."""

    id_om_zumbi: int = Field(..., gt=0, description="ID da OM Zumbi (FEC) a ser desativada")
    id_om_fei_destino: int = Field(..., gt=0, description="ID da OM destino a ser modernizada")


class OMRankingItem(BaseModel):
    """Resumo de OM para o ranking estratégico (GET /api/oms)."""

    ranking: int
    id_om: int
    sigla: str
    codigo_uasg: str
    classificacao_coeb: str
    indice_tecnologia_c4isr: float
    papel_a2ad: bool
    valor_imovel_brl: float
    nota_ive: float
    classificacao_ive: str
    foco_estrategico: str
    indicador_financeiro_estrategico: float
    total_alertas: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@router.get("/oms", response_model=List[OMRankingItem])
def listar_oms_ranking(
    coeb: Optional[ClassificacaoCOEB] = Query(
        default=None, description="Filtro opcional por classificação COEB (FEI, FEP, FEC)"
    ),
    db: Session = Depends(get_db),
) -> List[OMRankingItem]:
    """Retorna o ranking das OMs com IVE, Valor SPU e classificação COEB."""
    motor = MotorIVE()
    diagnosticos = motor.diagnosticar_todas(db, persistir_alertas=True)

    if coeb is not None:
        diagnosticos = [d for d in diagnosticos if d.classificacao_coeb == coeb.value]

    return [
        OMRankingItem(
            ranking=idx,
            id_om=d.id_om,
            sigla=d.sigla,
            codigo_uasg=d.codigo_uasg,
            classificacao_coeb=d.classificacao_coeb,
            indice_tecnologia_c4isr=d.indice_tecnologia_c4isr,
            papel_a2ad=d.papel_a2ad,
            valor_imovel_brl=d.valor_imovel_brl,
            nota_ive=d.nota_ive,
            classificacao_ive=d.classificacao_ive,
            foco_estrategico=d.foco_estrategico,
            indicador_financeiro_estrategico=d.indicador_financeiro_estrategico,
            total_alertas=len(d.alertas_auditoria),
            latitude=d.dados_operacionais.get("latitude"),
            longitude=d.dados_operacionais.get("longitude"),
        )
        for idx, d in enumerate(diagnosticos, start=1)
    ]


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
