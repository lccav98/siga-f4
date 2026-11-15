"""Serviço de integração com a Secretaria do Patrimônio da União (SPU) via RIP."""

import os
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.orm import Session

from backend.models.schemas import OM, PatrimonioUniao


class PatrimonioSyncService:
    """Sincroniza avaliação imobiliária (RIP SPU) para cálculo de Custo de Oportunidade."""

    BASE_URL = os.getenv("SPU_API_URL", "https://api.patrimonio.gov.br/v1")

    def __init__(self, api_key: Optional[str] = None, timeout: float = 15.0):
        self.api_key = api_key or os.getenv("SPU_API_KEY")
        self.timeout = timeout

    def consultar_imovel_rip(self, rip_spu: str) -> Dict[str, Any]:
        """Consulta valor atualizado de mercado do imóvel cadastrado no SPUNet."""
        if not self.api_key:
            return {
                "origem": "mock_fallback",
                "rip_spu": rip_spu,
                "valor_imovel_brl": None,
            }

        url = f"{self.BASE_URL}/imoveis/{rip_spu}"
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            return {
                "origem": "api_oficial",
                "rip_spu": rip_spu,
                "valor_imovel_brl": float(data.get("valor_avaliacao_brl", 0.0)),
            }
        except httpx.HTTPError as exc:
            return {
                "origem": "erro_api",
                "erro": str(exc),
                "rip_spu": rip_spu,
                "valor_imovel_brl": None,
            }

    def sincronizar_om(self, db: Session, id_om: int) -> Optional[PatrimonioUniao]:
        """Atualiza o valor patrimonial da OM no banco local a partir do RIP SPU."""
        om = db.query(OM).filter(OM.id_om == id_om).first()
        if not om:
            return None

        dados_spu = self.consultar_imovel_rip(om.rip_spu)
        patrimonio = db.query(PatrimonioUniao).filter(PatrimonioUniao.id_om == id_om).first()

        if dados_spu.get("valor_imovel_brl") is not None:
            if patrimonio is None:
                patrimonio = PatrimonioUniao(
                    id_om=id_om,
                    rip_spu=om.rip_spu,
                    valor_imovel_brl=dados_spu["valor_imovel_brl"],
                )
                db.add(patrimonio)
            else:
                patrimonio.valor_imovel_brl = dados_spu["valor_imovel_brl"]
            db.commit()
            db.refresh(patrimonio)

        return patrimonio
