"""Digital Twin (Simulador de Evolução Doutrinária) para reestruturação SIGA-F4."""

from typing import Any, Dict

from sqlalchemy.orm import Session

from backend.core.estrutura_eb import eh_om_ensino, eh_om_saude
from backend.core.motor_jev import MotorIVE
from backend.models.schemas import OM


# Parâmetro de conversão de capital SPU/Custeio em capacidade C4ISR:
# Cada R$ 10 milhões direcionados para modernização C4ISR eleva o índice em ~1 ponto (teto 100).
BRL_POR_PONTO_C4ISR = 10_000_000.0
FRACAO_INVESTIMENTO_TECNOLOGIA = 0.65  # 65% do capital alienado reinvestido em Força 4.0 / C4ISR


def simular_reestruturacao(
    db: Session,
    id_om_zumbi: int,
    id_om_fei_destino: int,
) -> Dict[str, Any]:
    """Simula a desativação de uma OM Zumbi e conversão de seu capital/CPFs para uma OM destino.

    A simulação não altera os dados persistidos no banco; calcula o impacto líquido:
    - Alienação do patrimônio imobiliário (SPU) da OM Zumbi e fechamento de seu CNPJ UG;
    - Economia anual recorrente de custeio (CGU);
    - Transferência de fração de CPFs ativos aproveitáveis;
    - Elevação projetada do `indice_tecnologia_c4isr` e do `IVE` na OM destino.
    """
    if id_om_zumbi == id_om_fei_destino:
        raise ValueError("A OM Zumbi de origem e a OM destino devem ser distintas.")

    om_zumbi = db.query(OM).filter(OM.id_om == id_om_zumbi).first()
    om_destino = db.query(OM).filter(OM.id_om == id_om_fei_destino).first()

    if not om_zumbi:
        raise ValueError(f"OM origem (id={id_om_zumbi}) não encontrada.")
    if not om_destino:
        raise ValueError(f"OM destino (id={id_om_fei_destino}) não encontrada.")
    if eh_om_saude(om_zumbi.sigla) or eh_om_ensino(om_zumbi.sigla):
        raise ValueError(
            f"A {om_zumbi.sigla} integra categoria especial protegida (Sustentação Sanitária ou Capacidade Institucional) "
            "e não pode ser enquadrada ou alienada como OM Zumbi."
        )

    motor = MotorIVE()
    diag_zumbi = motor.diagnosticar_om(db, om_zumbi, persistir_alertas=False)
    diag_destino_antes = motor.diagnosticar_om(db, om_destino, persistir_alertas=False)

    valor_alienacao_spu = diag_zumbi.valor_imovel_brl
    economia_custeio_anual = diag_zumbi.dados_operacionais["total_empenhado_cgu"]
    cpfs_liberados = diag_zumbi.dados_operacionais["cpfs_ativos_cgu"]

    # Aproveita 40% dos CPFs ativos da OM desativada para reforço operacional/técnico
    cpfs_transferidos = int(cpfs_liberados * 0.40)

    # Capital disponível para modernização C4ISR da OM destino
    capital_para_c4isr = valor_alienacao_spu * FRACAO_INVESTIMENTO_TECNOLOGIA
    ganho_c4isr = capital_para_c4isr / BRL_POR_PONTO_C4ISR

    c4isr_antes = diag_destino_antes.indice_tecnologia_c4isr
    c4isr_depois = round(min(100.0, c4isr_antes + ganho_c4isr), 2)

    componentes_depois = dict(diag_destino_antes.componentes_ive)
    componentes_depois["nivel_tecnologico_c4isr"] = c4isr_depois

    ive_depois = motor.calcular_nota_ive(
        om_destino,
        componentes_depois,
        qtd_anomalias=len(diag_destino_antes.alertas_auditoria),
        c4isr_override=c4isr_depois,
    )
    classificacao_depois, foco_depois = motor.classificar_ive(
        ive_depois,
        is_saude=eh_om_saude(om_destino.sigla),
        is_ensino=eh_om_ensino(om_destino.sigla),
    )

    economia_total_5_anos = valor_alienacao_spu + (economia_custeio_anual * 5.0)
    reserva_liquida_tesouro = valor_alienacao_spu * (1.0 - FRACAO_INVESTIMENTO_TECNOLOGIA)

    op_dest = diag_destino_antes.dados_operacionais
    cat_bld = op_dest.get("categoria_forca_blindada")
    capex_req = op_dest.get("capex_aquisicao_brl", 0.0)
    obsol_anual = op_dest.get("custo_obsolescencia_anual_brl", 0.0)
    cobertura_capex_pct = round(min(100.0, (capital_para_c4isr / capex_req) * 100.0), 1) if capex_req else 0.0
    economia_obsol_anual = round(obsol_anual * (cobertura_capex_pct / 100.0) * 0.65, 2) if obsol_anual else 0.0

    resumo_base = (
        f"Alienação da {om_zumbi.sigla} (CNPJ UG {om_zumbi.cnpj_ug} encerrado) "
        f"libera R$ {valor_alienacao_spu:,.2f} em patrimônio SPU e R$ {economia_custeio_anual:,.2f}/ano "
        f"em custeio. Investindo R$ {capital_para_c4isr:,.2f} em Força 4.0, a {om_destino.sigla} "
        f"salta de C4ISR {c4isr_antes:.1f} para {c4isr_depois:.1f} e IVE {diag_destino_antes.nota_ive:.1f} "
        f"para {ive_depois:.1f} ({classificacao_depois})."
    )
    if cat_bld:
        resumo_base += (
            f" Na {cat_bld}, o aporte cobre {cobertura_capex_pct:.1f}% do CAPEX de renovação de frota/C4ISR "
            f"(demanda total R$ {capex_req / 1e6:,.1f} Mi), abatendo R$ {economia_obsol_anual / 1e6:,.2f} Mi/ano "
            "em custo de obsolescência."
        )

    return {
        "om_zumbi_desativada": {
            "id_om": om_zumbi.id_om,
            "sigla": om_zumbi.sigla,
            "cnpj_ug_encerrado": om_zumbi.cnpj_ug,
            "classificacao_coeb": diag_zumbi.classificacao_coeb,
            "ive_atual": diag_zumbi.nota_ive,
            "classificacao_ive": diag_zumbi.classificacao_ive,
            "valor_alienacao_spu_brl": round(valor_alienacao_spu, 2),
            "economia_custeio_anual_brl": round(economia_custeio_anual, 2),
            "cpfs_ativos_liberados": cpfs_liberados,
        },
        "om_destino_transformada": {
            "id_om": om_destino.id_om,
            "sigla": om_destino.sigla,
            "classificacao_coeb": diag_destino_antes.classificacao_coeb,
            "categoria_forca_blindada": cat_bld,
            "plataformas_requeridas": op_dest.get("plataformas_requeridas", []),
            "capex_aquisicao_brl": capex_req,
            "custo_obsolescencia_anual_brl": obsol_anual,
            "cobertura_capex_blindado_pct": cobertura_capex_pct,
            "economia_obsolescencia_anual_brl": economia_obsol_anual,
            "c4isr_antes": round(c4isr_antes, 2),
            "c4isr_depois": c4isr_depois,
            "delta_c4isr": round(c4isr_depois - c4isr_antes, 2),
            "ive_antes": diag_destino_antes.nota_ive,
            "ive_depois": ive_depois,
            "delta_ive": round(ive_depois - diag_destino_antes.nota_ive, 2),
            "classificacao_antes": diag_destino_antes.classificacao_ive,
            "classificacao_depois": classificacao_depois,
            "foco_estrategico_depois": foco_depois,
            "cpfs_incorporados": cpfs_transferidos,
        },
        "impacto_financeiro_e_c2": {
            "capital_investido_c4isr_brl": round(capital_para_c4isr, 2),
            "retorno_liquido_tesouro_spu_brl": round(reserva_liquida_tesouro, 2),
            "economia_custeio_anual_brl": round(economia_custeio_anual, 2),
            "economia_obsolescencia_anual_brl": economia_obsol_anual,
            "economia_acumulada_5_anos_brl": round(economia_total_5_anos + (economia_obsol_anual * 5.0), 2),
            "ganho_capacidade_c2_percentual": round(c4isr_depois - c4isr_antes, 2),
            "resumo_executivo": resumo_base,
        },
    }
