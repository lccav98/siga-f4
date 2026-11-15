"""Serviço de integração com o Portal da Transparência (CGU) via UASG/CNPJ."""

import os
from datetime import datetime
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.orm import Session

from backend.models.schemas import OM, TransparenciaDados


class TransparenciaSyncService:
    """Sincroniza execução orçamentária e folha (ativos vs. reserva) via API da CGU."""

    BASE_URL = "https://api.portaldatransparencia.gov.br/api-de-dados"

    def __init__(self, api_key: Optional[str] = None, timeout: float = 15.0):
        self.api_key = api_key or os.getenv("CGU_API_KEY")
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["chave-api-dados"] = self.api_key
        return headers

    def consultar_despesas_uasg(self, codigo_uasg: str, ano_mes: str) -> Dict[str, Any]:
        """Consulta despesas empenhadas e dados de pessoal para uma UASG na CGU.

        Caso não haja `CGU_API_KEY` configurada ou ocorra falha de rede no MVP,
        retorna estrutura compatível sinalizando fallback local.
        """
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

            total_empenhado = sum(float(item.get("empenhado", 0.0)) for item in payload) if isinstance(payload, list) else 0.0
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
