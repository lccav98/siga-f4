"""Motor JEV (Julgamento, Estratégia e Validação) para diagnóstico doutrinário SIGA-F4."""

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

from backend.core.estrutura_eb import (
    BRIGADAS_FEC_COMBATE_DE,
    eh_om_ensino,
    eh_om_saude,
    inferir_localizacao_militar,
)
from backend.models.schemas import ClassificacaoCOEB, OM, TransparenciaDados


MULTIPLICADOR_COEB: Dict[ClassificacaoCOEB, float] = {
    ClassificacaoCOEB.FEP: 1.5,   # Forças de Emprego de Prontidão (EB10-P-01.031 / COEB 5.3.4.4 b): 1ª prioridade
    ClassificacaoCOEB.FEI: 1.2,   # Forças de Emprego Imediato (COEB 5.3.4.4 a): faixa de fronteira / 2º plano vs FEP
    ClassificacaoCOEB.FEC: 0.95,  # Forças de Emprego Continuado (COEB 5.3.4.4 c): teto <75 (sem virar Ponta de Lança), sem rebaixar Bda FEC limpa a OM Zumbi
}
MULTIPLICADOR_SAUDE = 1.15  # Sustentação Sanitária (COEB 5.6.1.2.4 b,f / 5.3.4.4 e)
MULTIPLICADOR_INSTITUCIONAL = 1.10  # Capacidades Institucionais de Ensino/Formação (COEB 5.6.1.4)

META_EFETIVO_PRONTIDAO_PCT = 20.0  # EB10-P-01.031 itens 1.4 e 2.6: mínimo de 20% em elevada prontidão
TERMOS_MODULO_MULTIDOMINIO = (
    "BINT",
    "INTELIG",
    "CIBER",
    "BGE",
    "C COM",
    "BCOM",
    "AAA",
    "GMF",
    "AVEX",
    "PQDT",
    "FESP",
    "COMANDOS",
)
TERMOS_APOIO_AMPLIADO = (
    "BLOG",
    "CTA",
    "TECNOL",
    "ARSENAL",
    "BEC",
    "BE CMB",
    "ENG",
    "B FV",
    "BAPLOGEX",
)

PENALIDADE_ANOMALIA = 0.15
LIMIAR_DELTA_AUDITORIA = 0.05  # 5%
LIMIAR_PRONTIDAO_FEP = 85.0    # 85% exigido para prioridade máxima FEP
LIMIAR_PRONTIDAO_FEI = 78.0    # 78% mínimo operacional para tropas de fronteira (FEI)


@dataclass
class AlertaAuditoria:
    """Representa uma anomalia detectada no cruzamento CGU / SIGPES / SISLOG."""

    tipo: str
    severidade: str
    descricao: str
    delta_percentual: Optional[float] = None


@dataclass
class DiagnosticoOM:
    """Resultado consolidado do Motor JEV para uma Organização Militar."""

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
    prescricao_doutrinaria: str
    alertas_auditoria: List[Dict[str, Any]]
    componentes_ive: Dict[str, float]
    dados_operacionais: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MotorIVE:
    """Implementa os pilares Validação, Estratégia e Julgamento do framework JEV."""

    def _obter_transparencia_recente(self, om: OM) -> Optional[TransparenciaDados]:
        if not om.transparencia_dados:
            return None
        return max(om.transparencia_dados, key=lambda r: r.ano_mes)

    # ------------------------------------------------------------------
    # 1. VALIDAÇÃO (Auditorias via Dados Abertos CGU / SIGPES / SISLOG)
    # ------------------------------------------------------------------
    def validar_anomalias(self, om: OM) -> List[AlertaAuditoria]:
        """Executa gatilhos de auditoria cruzando SIGPES, CGU e SISLOG."""
        alertas: List[AlertaAuditoria] = []
        sigpes = om.sigpes
        cgu = self._obter_transparencia_recente(om)
        doutrina = om.doutrina_tecnologia
        sislog = om.sislog

        if sigpes and cgu:
            # Gatilho Financeiro: Delta(Custeio Declarado, CGU) > 5%
            base_custeio = max(sigpes.custeio_declarado_brl, cgu.total_empenhado, 1.0)
            delta_fin = abs(cgu.total_empenhado - sigpes.custeio_declarado_brl) / base_custeio
            if delta_fin > LIMIAR_DELTA_AUDITORIA:
                alertas.append(
                    AlertaAuditoria(
                        tipo="FINANCEIRO",
                        severidade="ALTA",
                        delta_percentual=round(delta_fin * 100, 2),
                        descricao=(
                            f"Divergência orçamentária de {delta_fin * 100:.1f}% entre custeio "
                            f"declarado (R$ {sigpes.custeio_declarado_brl:,.2f}) e empenhado CGU "
                            f"(R$ {cgu.total_empenhado:,.2f})."
                        ),
                    )
                )

            # Gatilho Folha/Inativos: Delta(Efetivo Declarado, CPFs Ativos CGU) > 5%
            base_efetivo = max(sigpes.efetivo_total_declarado, cgu.cpfs_ativos, 1)
            delta_folha = abs(sigpes.efetivo_total_declarado - cgu.cpfs_ativos) / base_efetivo
            if delta_folha > LIMIAR_DELTA_AUDITORIA:
                alertas.append(
                    AlertaAuditoria(
                        tipo="FOLHA_INATIVOS",
                        severidade="ALTA",
                        delta_percentual=round(delta_folha * 100, 2),
                        descricao=(
                            f"Divergência de efetivo de {delta_folha * 100:.1f}%: SIGPES declara "
                            f"{sigpes.efetivo_total_declarado} militares vs. {cgu.cpfs_ativos} CPFs "
                            f"ativos na CGU ({cgu.cpfs_reserva} inativos/pensionistas isolados)."
                        ),
                    )
                )

        # Gatilho Prontidão Falsa: FEP (<85%) ou FEI de fronteira (<78%)
        if doutrina and sislog:
            if (
                doutrina.classificacao_coeb == ClassificacaoCOEB.FEP
                and sislog.taxa_disponibilidade < LIMIAR_PRONTIDAO_FEP
            ):
                alertas.append(
                    AlertaAuditoria(
                        tipo="QUEBRA_PRONTIDAO_FEP",
                        severidade="CRITICA",
                        delta_percentual=round(LIMIAR_PRONTIDAO_FEP - sislog.taxa_disponibilidade, 2),
                        descricao=(
                            f"Quebra de Prontidão FEP: disponibilidade de {sislog.taxa_disponibilidade:.1f}% "
                            f"abaixo do mínimo de {LIMIAR_PRONTIDAO_FEP:.0f}% exigido para força de 1ª prioridade."
                        ),
                    )
                )
            elif (
                doutrina.classificacao_coeb == ClassificacaoCOEB.FEI
                and sislog.taxa_disponibilidade < LIMIAR_PRONTIDAO_FEI
            ):
                alertas.append(
                    AlertaAuditoria(
                        tipo="QUEBRA_PRONTIDAO_FEI",
                        severidade="ALTA",
                        delta_percentual=round(LIMIAR_PRONTIDAO_FEI - sislog.taxa_disponibilidade, 2),
                        descricao=(
                            f"Alerta de Prontidão na Fronteira (FEI): disponibilidade de {sislog.taxa_disponibilidade:.1f}% "
                            f"abaixo do mínimo operacional de {LIMIAR_PRONTIDAO_FEI:.0f}%."
                        ),
                    )
                )

        return alertas

    # ------------------------------------------------------------------
    # 2. ESTRATÉGIA (Cálculo do IVE Dinâmico com Pesos COEB & Força 4.0)
    # ------------------------------------------------------------------
    @staticmethod
    def _em_rota_estrategica(om: OM) -> bool:
        """Identifica OMs posicionadas em rotas de aproximação estratégica (ex: Calha Amazônica)."""
        if om.latitude is None or om.longitude is None:
            return False
        calha_amazonica = om.latitude >= -10.5 and om.longitude <= -48.0
        faixa_fronteira_critica = bool(om.estrategia and om.estrategia.dist_fronteira_km <= 150.0)
        return calha_amazonica or faixa_fronteira_critica

    def calcular_componentes_ive(self, om: OM) -> Dict[str, float]:
        """Calcula os 5 subíndices (0-100) do IVE antes do multiplicador COEB e penalidades."""
        sigpes = om.sigpes
        cgu = self._obter_transparencia_recente(om)
        doutrina = om.doutrina_tecnologia
        sislog = om.sislog
        estrategia = om.estrategia

        cpfs_ativos = max(cgu.cpfs_ativos if cgu else (sigpes.efetivo_total_declarado if sigpes else 1), 1)
        efetivo_fim = sigpes.efetivo_fim if sigpes else 0
        total_empenhado = cgu.total_empenhado if cgu else (sigpes.custeio_declarado_brl if sigpes else 0.0)

        # 1. Teeth-to-Tail (15%): efetivo_fim / cpfs_ativos
        nota_teeth_to_tail = min(100.0, max(0.0, (efetivo_fim / cpfs_ativos) * 100.0))

        # 2. Eficiência de Custeio (15%): total_empenhado / cpfs_ativos
        # Faixa de referência: <= R$ 45k/CPF (100 pts) até R$ 220k/CPF (20 pts)
        custo_por_cpf = total_empenhado / cpfs_ativos
        if custo_por_cpf <= 45_000.0:
            nota_eficiencia = 100.0
        else:
            nota_eficiencia = max(20.0, min(100.0, 100.0 - ((custo_por_cpf - 45_000.0) / 175_000.0) * 80.0))

        # 3. Nível Tecnológico e Força 4.0 (25%)
        c4isr = doutrina.indice_tecnologia_c4isr if doutrina else 0.0
        nota_tecnologia = min(100.0, max(0.0, c4isr))

        # 4. Prontidão e Emprego (25%): SISLOG cruzado com exigência COEB
        disponibilidade = sislog.taxa_disponibilidade if sislog else 0.0
        acionamentos = sislog.acionamentos_reais_36m if sislog else 0
        coeb = doutrina.classificacao_coeb if doutrina else ClassificacaoCOEB.FEC
        is_saude = eh_om_saude(om.sigla)
        is_ensino = eh_om_ensino(om.sigla)
        local_eb = inferir_localizacao_militar(om.sigla, om.endereco)

        if is_saude:
            # OMS: disponibilidade assistencial/leitos e prontidão para módulo de saúde FTC
            nota_mobilizacao_saude = min(100.0, (acionamentos / 4.0) * 100.0)
            nota_prontidao = 0.85 * disponibilidade + 0.15 * nota_mobilizacao_saude
        elif is_ensino:
            nota_prontidao = disponibilidade
        elif coeb == ClassificacaoCOEB.FEP:
            nota_acionamento = min(100.0, (acionamentos / 32.0) * 100.0)
            nota_prontidao = 0.50 * disponibilidade + 0.50 * nota_acionamento
        elif coeb == ClassificacaoCOEB.FEI:
            nota_acionamento = min(100.0, (acionamentos / 24.0) * 100.0)
            nota_prontidao = 0.65 * disponibilidade + 0.35 * nota_acionamento
        else:  # FEC: foco na capacidade de mobilização em D+
            nota_mobilizacao = min(100.0, (acionamentos / 6.0) * 100.0)
            nota_prontidao = 0.85 * disponibilidade + 0.15 * nota_mobilizacao

        # 5. Geoestratégia e A2/AD (20%) — com COEB 2026 (Litoral, DE Multidomínio, Saúde e Capacidades Institucionais)
        papel_a2ad = bool(doutrina and doutrina.papel_a2ad)
        dist_fronteira = estrategia.dist_fronteira_km if estrategia else 1000.0
        sigla_up = om.sigla.upper()
        if is_saude:
            nota_geo = 85.0 if ("HCE" in sigla_up or "HMA" in sigla_up) else 75.0
        elif is_ensino:
            nota_geo = 80.0
        elif papel_a2ad and self._em_rota_estrategica(om):
            nota_geo = 100.0
        else:
            base_fronteira = max(10.0, min(100.0, 100.0 - (dist_fronteira / 20.0)))
            bonus_a2ad = 25.0 if papel_a2ad else 0.0
            is_de_c2 = "CIA CMDO" in sigla_up and "DE" in sigla_up
            if is_de_c2 or local_eb["brigada"] in BRIGADAS_FEC_COMBATE_DE:
                # COEB 1.3.2.7 / 5.3.2 / 5.3.4.4 c: defesa da costa/litoral, C2 Divisionário e reserva mobilizável
                base_fronteira = max(48.0, base_fronteira)
            nota_geo = min(100.0, base_fronteira + bonus_a2ad)

        return {
            "teeth_to_tail": round(nota_teeth_to_tail, 2),
            "eficiencia_custeio": round(nota_eficiencia, 2),
            "nivel_tecnologico_c4isr": round(nota_tecnologia, 2),
            "prontidao_emprego": round(nota_prontidao, 2),
            "geoestrategia_a2ad": round(nota_geo, 2),
        }

    def calcular_nota_ive(
        self,
        om: OM,
        componentes: Dict[str, float],
        qtd_anomalias: int,
        c4isr_override: Optional[float] = None,
    ) -> float:
        """Aplica pesos dinâmicos, multiplicador COEB e penalidade de -15% por anomalia."""
        c4isr = c4isr_override if c4isr_override is not None else componentes["nivel_tecnologico_c4isr"]

        score_ponderado = (
            0.15 * componentes["teeth_to_tail"]
            + 0.15 * componentes["eficiencia_custeio"]
            + 0.25 * c4isr
            + 0.25 * componentes["prontidao_emprego"]
            + 0.20 * componentes["geoestrategia_a2ad"]
        )

        coeb = om.doutrina_tecnologia.classificacao_coeb if om.doutrina_tecnologia else ClassificacaoCOEB.FEC
        if eh_om_saude(om.sigla):
            multiplicador = MULTIPLICADOR_SAUDE
        elif eh_om_ensino(om.sigla):
            multiplicador = MULTIPLICADOR_INSTITUCIONAL
        else:
            multiplicador = MULTIPLICADOR_COEB[coeb]

        fator_penalidade = max(0.10, 1.0 - (PENALIDADE_ANOMALIA * qtd_anomalias))
        # Normaliza pelo teto próximo ao multiplicador FEP (1.45) preservando a prioridade FEP > FEI > Saúde/Inst > FEC
        ive_bruto = score_ponderado * (multiplicador / 1.45) * fator_penalidade
        return round(min(100.0, max(0.0, ive_bruto)), 2)

    # ------------------------------------------------------------------
    # 3. JULGAMENTO (Classificação e Prescrição Doutrinária)
    # ------------------------------------------------------------------
    @staticmethod
    def classificar_ive(
        nota_ive: float, is_saude: bool = False, is_ensino: bool = False
    ) -> tuple[str, str]:
        if is_saude:
            return ("Sustentação Sanitária", "Saúde Operacional & FUSEx (DSau)")
        if is_ensino:
            return ("Capacidade Institucional", "Ensino, Liderança & DOAMEPI (COEB 5.6.1.4)")
        if nota_ive > 75.0:
            return ("Ponta de Lança", "Força 4.0, Injeção C4ISTAR")
        if nota_ive >= 40.0:
            return ("Zona de Fusão", "COEB, Unificação Modular")
        return ("OM Zumbi", "Política de Transformação, Alienação")

    @staticmethod
    def classificar_enquadramento_transformacao(
        sigla: str, coeb: ClassificacaoCOEB, c4isr: float, papel_a2ad: bool
    ) -> str:
        """Enquadra a OM nos grupos de emprego e módulos (EB10-P-01.031 & COEB EB20-MF-07.101, 5.3.4.4)."""
        if eh_om_saude(sigla):
            return "Sustentação Sanitária (FUSEx / Apoio Ampliado FTC)"
        if eh_om_ensino(sigla):
            return "Capacidade Institucional (Ensino / DOAMEPI)"
        sigla_up = sigla.upper()
        if any(t in sigla_up for t in TERMOS_MODULO_MULTIDOMINIO) or (
            coeb == ClassificacaoCOEB.FEP and c4isr >= 78.0 and papel_a2ad
        ):
            return "Módulo Multidomínio (FTC / C Conj)"
        if any(t in sigla_up for t in TERMOS_APOIO_AMPLIADO):
            return "Módulo de Apoio Ampliado (FTC)"
        if coeb == ClassificacaoCOEB.FEP:
            return "Força de Emprego de Prontidão (FEP)"
        if coeb == ClassificacaoCOEB.FEI:
            return "Força de Emprego Imediato (FEI)"
        return "Força de Emprego Continuado (FEC)"

    @staticmethod
    def gerar_prescricao(
        classificacao_ive: str,
        coeb: ClassificacaoCOEB,
        c4isr: float,
        alertas: List[AlertaAuditoria],
    ) -> str:
        """Gera Linha de Ação Dinâmica conforme EB10-P-01.031 e COEB EB20-MF-07.101."""
        if classificacao_ive == "Sustentação Sanitária":
            if any(a.tipo in ("FINANCEIRO", "FOLHA_INATIVOS") for a in alertas):
                return (
                    "Auditoria e Racionalização de Área-Meio (EB10-P-01.031, item 3.1.3.1): sanear "
                    "divergências CGU/SIGPES e custos administrativos preservando integralmente a "
                    "vocação assistencial (FUSEx) e o núcleo de Apoio Ampliado à FTC (COEB 5.3.4.4 e) "
                    "— vedada alienação patrimonial como OM Zumbi."
                )
            return (
                "Preservar Vocação Assistencial (FUSEx / Eixo Pessoal 3.4.7) e Sustentação Sanitária "
                "(COEB 5.6.1.2.4 b,f e 5.3.4.4 e): não computar como poder de combate ofensivo (FEP); "
                "manter pronto o núcleo de Apoio Ampliado de Saúde para desdobramento na FTC."
            )

        if classificacao_ive == "Capacidade Institucional":
            return (
                "Preservar Capacidade Institucional de Ensino e Formação (COEB 5.6.1.4 e DOAMEPI 5.6.1.3.2 e): "
                "sustentar formação de quadros e liderança para operações no multidomínio, "
                "mantendo auditoria contínua de área-meio via CGU/SIGPES."
            )

        if classificacao_ive == "OM Zumbi" and coeb == ClassificacaoCOEB.FEC:
            return (
                "Desativação/Otimização imediata (EB10-P-01.031, item 3.1.3.1): estrutura de Emprego Continuado "
                "que não agrega poder de combate/letalidade ou alinhamento PEECFA. Alienar patrimônio via SPU "
                "para capitalizar forças FEP (Prontidão), FEI (Fronteira) e Módulos Multidomínio."
            )

        if classificacao_ive == "Ponta de Lança" and coeb == ClassificacaoCOEB.FEP and c4isr < 50.0:
            return (
                "Gargalo Doutrinário FEP (Prontidão). Tropa de maior prioridade no COEB carente de tecnologia C4ISR "
                "(Eixo Capacidades 3.2). Redirecionar recursos imediatamente para sistemas de apoio à decisão e material."
            )

        if any(a.tipo == "QUEBRA_PRONTIDAO_FEP" for a in alertas):
            return (
                "Intervenção de Prontidão Imediata (FEP). Unidade de Emprego de Prontidão abaixo de 85% de "
                "disponibilidade (compromete meta ≥20% EB10-P-01.031); recompletar pessoal, material e SISLOG."
            )

        if any(a.tipo == "QUEBRA_PRONTIDAO_FEI" for a in alertas):
            return (
                "Reforço na Faixa de Fronteira (FEI). Unidade de Emprego Imediato abaixo de 78% de "
                "disponibilidade; ajustar logística SISLOG para resposta inicial após cobertura das prioridades FEP."
            )

        if classificacao_ive == "Ponta de Lança" and coeb == ClassificacaoCOEB.FEP:
            return (
                "Manter prioridade máxima de recompletamento (pessoal, material, sistemas e C4ISR) como núcleo "
                "ofensivo e módulo Multidomínio da FTC/Comando Conjunto (EB10-P-01.031, PEEx 2024–2031)."
            )

        if classificacao_ive == "Ponta de Lança":
            return (
                "Preservar prontidão de resposta inicial e vigilância na faixa de fronteira (FEI), "
                "integrando sensores ISR à arquitetura de comando e controle das grandes unidades FEP."
            )

        if classificacao_ive == "Zona de Fusão":
            return (
                "Rearticular conforme o COEB e PEECFA (item 3.1.2.1/3.1.3.2) via unificação modular na FTC; "
                "se FEI de fronteira, modernizar sensores pós-FEP; se FEP, elevar C4ISR via Digital Twin."
            )

        return (
            "Revisão estrutural severa pela Política de Transformação (item 3.1.3.1): auditar folha/custeio "
            "e avaliar fusão ou alienação patrimonial de estrutura sem agregação direta de letalidade."
        )

    def diagnosticar_om(self, db: Session, om: OM, persistir_alertas: bool = True) -> DiagnosticoOM:
        """Executa o ciclo completo JEV (Validação -> Estratégia -> Julgamento) para uma OM."""
        alertas = self.validar_anomalias(om)
        alertas_dict = [asdict(a) for a in alertas]

        if persistir_alertas and om.alertas_auditoria != alertas_dict:
            om.alertas_auditoria = alertas_dict
            db.add(om)
            db.commit()
            db.refresh(om)

        componentes = self.calcular_componentes_ive(om)
        nota_ive = self.calcular_nota_ive(om, componentes, len(alertas))
        classificacao_ive, foco = self.classificar_ive(
            nota_ive, is_saude=eh_om_saude(om.sigla), is_ensino=eh_om_ensino(om.sigla)
        )

        doutrina = om.doutrina_tecnologia
        coeb = doutrina.classificacao_coeb if doutrina else ClassificacaoCOEB.FEC
        c4isr = doutrina.indice_tecnologia_c4isr if doutrina else 0.0
        papel_a2ad = bool(doutrina and doutrina.papel_a2ad)
        valor_imovel = om.patrimonio_uniao.valor_imovel_brl if om.patrimonio_uniao else 0.0

        indicador_fin = round(valor_imovel / max(nota_ive, 1.0), 2)
        prescricao = self.gerar_prescricao(classificacao_ive, coeb, c4isr, alertas)
        enquadramento_eb10 = self.classificar_enquadramento_transformacao(
            om.sigla, coeb, c4isr, papel_a2ad
        )
        local_eb = inferir_localizacao_militar(om.sigla, om.endereco)

        cgu = self._obter_transparencia_recente(om)
        sigpes = om.sigpes
        sislog = om.sislog
        estrategia = om.estrategia

        return DiagnosticoOM(
            id_om=om.id_om,
            sigla=om.sigla,
            codigo_uasg=om.codigo_uasg,
            cnpj_ug=om.cnpj_ug,
            classificacao_coeb=coeb.value,
            indice_tecnologia_c4isr=c4isr,
            papel_a2ad=papel_a2ad,
            valor_imovel_brl=valor_imovel,
            nota_ive=nota_ive,
            classificacao_ive=classificacao_ive,
            foco_estrategico=foco,
            indicador_financeiro_estrategico=indicador_fin,
            prescricao_doutrinaria=prescricao,
            alertas_auditoria=alertas_dict,
            componentes_ive=componentes,
            dados_operacionais={
                "latitude": om.latitude,
                "longitude": om.longitude,
                "endereco": om.endereco,
                "municipio": local_eb["municipio"],
                "uf": local_eb["uf"],
                "regiao_militar": local_eb["regiao_militar"],
                "comando_militar_area": local_eb["comando_militar_area"],
                "brigada": local_eb["brigada"],
                "enquadramento_transformacao": enquadramento_eb10,
                "efetivo_declarado": sigpes.efetivo_total_declarado if sigpes else 0,
                "efetivo_fim": sigpes.efetivo_fim if sigpes else 0,
                "cpfs_ativos_cgu": cgu.cpfs_ativos if cgu else 0,
                "cpfs_reserva_cgu": cgu.cpfs_reserva if cgu else 0,
                "custeio_declarado_brl": sigpes.custeio_declarado_brl if sigpes else 0.0,
                "total_empenhado_cgu": cgu.total_empenhado if cgu else 0.0,
                "acionamentos_36m": sislog.acionamentos_reais_36m if sislog else 0,
                "taxa_disponibilidade": sislog.taxa_disponibilidade if sislog else 0.0,
                "dist_fronteira_km": estrategia.dist_fronteira_km if estrategia else 0.0,
                "area_urbana": estrategia.area_urbana if estrategia else True,
            },
        )

    def diagnosticar_todas(self, db: Session, persistir_alertas: bool = True) -> List[DiagnosticoOM]:
        """Executa o Motor JEV em todas as OMs (com eager loading) ordenado pelo IVE decrescente."""
        oms = (
            db.query(OM)
            .options(
                joinedload(OM.doutrina_tecnologia),
                joinedload(OM.patrimonio_uniao),
                joinedload(OM.sigpes),
                joinedload(OM.transparencia_dados),
                joinedload(OM.sislog),
                joinedload(OM.estrategia),
            )
            .all()
        )
        diagnosticos: List[DiagnosticoOM] = []
        houve_alteracao = False

        for om in oms:
            diag = self.diagnosticar_om(db, om, persistir_alertas=False)
            if persistir_alertas and om.alertas_auditoria != diag.alertas_auditoria:
                om.alertas_auditoria = diag.alertas_auditoria
                db.add(om)
                houve_alteracao = True
            diagnosticos.append(diag)

        if houve_alteracao:
            db.commit()

        diagnosticos.sort(key=lambda d: d.nota_ive, reverse=True)
        return diagnosticos

    @staticmethod
    def resumo_politica_transformacao(diagnosticos: List[DiagnosticoOM]) -> Dict[str, Any]:
        """Calcula indicadores da Política de Transformação (EB10-P-01.031, itens 1.4, 2.6 e 3.1)."""
        efetivo_total = sum(d.dados_operacionais.get("cpfs_ativos_cgu", 0) for d in diagnosticos)
        efetivo_prontidao = sum(
            d.dados_operacionais.get("cpfs_ativos_cgu", 0)
            for d in diagnosticos
            if d.classificacao_coeb in ("FEP", "FEI")
            and d.dados_operacionais.get("taxa_disponibilidade", 0.0) >= LIMIAR_PRONTIDAO_FEP
        )
        percentual_prontidao = round((efetivo_prontidao / max(efetivo_total, 1)) * 100.0, 1)

        modulos_multidominio = sum(
            1
            for d in diagnosticos
            if d.dados_operacionais.get("enquadramento_transformacao") == "Módulo Multidomínio (FTC / C Conj)"
        )
        modulos_apoio_ampliado = sum(
            1
            for d in diagnosticos
            if d.dados_operacionais.get("enquadramento_transformacao") == "Módulo de Apoio Ampliado (FTC)"
        )
        estruturas_otimizacao = [d for d in diagnosticos if d.classificacao_ive == "OM Zumbi"]
        oms_saude_sustentacao = sum(1 for d in diagnosticos if d.classificacao_ive == "Sustentação Sanitária")
        oms_capacidade_institucional = sum(
            1 for d in diagnosticos if d.classificacao_ive == "Capacidade Institucional"
        )

        return {
            "norma": "EB10-P-01.031 • COEB EB20-MF-07.101 (2ª Ed. 2026)",
            "governanca": "EME / 7ª Subchefia • Ciclo PEEx 2024–2027 → 2028–2031",
            "meta_prontidao_minima_pct": META_EFETIVO_PRONTIDAO_PCT,
            "efetivo_total_ativos": efetivo_total,
            "efetivo_elevada_prontidao": efetivo_prontidao,
            "percentual_prontidao_forca": percentual_prontidao,
            "atende_meta_prontidao": percentual_prontidao >= META_EFETIVO_PRONTIDAO_PCT,
            "modulos_multidominio_ftc": modulos_multidominio,
            "modulos_apoio_ampliado_ftc": modulos_apoio_ampliado,
            "oms_saude_sustentacao": oms_saude_sustentacao,
            "oms_capacidade_institucional": oms_capacidade_institucional,
            "oms_otimizacao_item_3_1_3_1": len(estruturas_otimizacao),
            "patrimonio_otimizacao_brl": round(sum(d.valor_imovel_brl for d in estruturas_otimizacao), 2),
        }
