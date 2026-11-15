"""Gerador de massa de dados sintética (Faker) para as 20 OMs do MVP SIGA-F4.

Inclui obrigatoriamente exemplos contrastantes:
- Batalhão de Inteligência Militar (FEI, Alta Tecnologia C4ISR, Baixo Efetivo)
- Batalhão de Infantaria Convencional de Guarda (FEC, Baixa Tecnologia, Alto Valor Imobiliário SPU)
"""

import os
import sys
import random
from pathlib import Path

from faker import Faker

# Garante importação do pacote backend quando executado diretamente
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.models.database import Base, SessionLocal, engine
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

fake = Faker("pt_BR")
Faker.seed(42)
random.seed(42)

# Perfis geográficos e doutrinários realistas para as 20 OMs
PERFIS_OMS = [
    # 1. Caso contrastante 1: Inteligência Militar (FEI, Alta Tecnologia, Baixo Efetivo)
    {
        "sigla": "1º BInt (Btl Intlg Mil)",
        "cidade": "Manaus - AM",
        "lat": -3.119028,
        "lon": -60.021731,
        "coeb": ClassificacaoCOEB.FEI,
        "c4isr": 94.5,
        "a2ad": True,
        "valor_spu": 42_000_000.0,
        "efetivo_decl": 185,
        "efetivo_fim": 165,
        "cpfs_ativos": 184,
        "cpfs_reserva": 12,
        "custeio_decl": 18_500_000.0,
        "empenhado_cgu": 18_620_000.0,
        "acionamentos": 48,
        "disponibilidade": 96.5,
        "dist_fronteira": 180.0,
        "area_urbana": True,
    },
    # 2. Caso contrastante 2: Infantaria de Guarda (FEC, Baixa Tecnologia, Alto Valor Imobiliário)
    {
        "sigla": "2º BIG (Btl Inf Gda)",
        "cidade": "Rio de Janeiro - RJ",
        "lat": -22.906847,
        "lon": -43.172896,
        "coeb": ClassificacaoCOEB.FEC,
        "c4isr": 16.0,
        "a2ad": False,
        "valor_spu": 485_000_000.0,
        "efetivo_decl": 780,
        "efetivo_fim": 320,
        "cpfs_ativos": 650,  # Anomalia proposital (>5% delta: efetivo fantasma/inativos)
        "cpfs_reserva": 210,
        "custeio_decl": 34_000_000.0,
        "empenhado_cgu": 38_900_000.0,  # Anomalia financeira (>5% delta)
        "acionamentos": 1,
        "disponibilidade": 58.0,
        "dist_fronteira": 1150.0,
        "area_urbana": True,
    },
    # 3. Comando de Defesa Cibernética (FEI, C4ISR máximo, baixo efetivo)
    {
        "sigla": "ComDCiber",
        "cidade": "Brasília - DF",
        "lat": -15.780148,
        "lon": -47.929170,
        "coeb": ClassificacaoCOEB.FEI,
        "c4isr": 98.0,
        "a2ad": True,
        "valor_spu": 65_000_000.0,
        "efetivo_decl": 210,
        "efetivo_fim": 190,
        "cpfs_ativos": 208,
        "cpfs_reserva": 8,
        "custeio_decl": 29_000_000.0,
        "empenhado_cgu": 29_400_000.0,
        "acionamentos": 62,
        "disponibilidade": 98.0,
        "dist_fronteira": 980.0,
        "area_urbana": True,
    },
    # 4. Pelotão/Batalhão de Fronteira Amazônico (FEI, A2/AD em rota estratégica)
    {
        "sigla": "5º BIS (Btl Inf Sl)",
        "cidade": "São Gabriel da Cachoeira - AM",
        "lat": -0.130320,
        "lon": -67.089160,
        "coeb": ClassificacaoCOEB.FEI,
        "c4isr": 72.0,
        "a2ad": True,
        "valor_spu": 18_500_000.0,
        "efetivo_decl": 620,
        "efetivo_fim": 540,
        "cpfs_ativos": 615,
        "cpfs_reserva": 18,
        "custeio_decl": 31_000_000.0,
        "empenhado_cgu": 31_500_000.0,
        "acionamentos": 37,
        "disponibilidade": 91.0,
        "dist_fronteira": 25.0,
        "area_urbana": False,
    },
    # 5. Brigada de Operações Especiais (FEI, mas com gargalo tecnológico simulado)
    {
        "sigla": "1º BFEsp",
        "cidade": "Goiânia - GO",
        "lat": -16.686891,
        "lon": -49.264794,
        "coeb": ClassificacaoCOEB.FEI,
        "c4isr": 44.0,  # Gargalo Doutrinário (<50 em FEI)
        "a2ad": True,
        "valor_spu": 95_000_000.0,
        "efetivo_decl": 410,
        "efetivo_fim": 375,
        "cpfs_ativos": 408,
        "cpfs_reserva": 15,
        "custeio_decl": 26_000_000.0,
        "empenhado_cgu": 26_300_000.0,
        "acionamentos": 41,
        "disponibilidade": 94.0,
        "dist_fronteira": 820.0,
        "area_urbana": True,
    },
    # 6. Btl Com GE (Guerra Eletrônica - FEI)
    {
        "sigla": "1º BGE",
        "cidade": "Brasília - DF",
        "lat": -15.794229,
        "lon": -47.882166,
        "coeb": ClassificacaoCOEB.FEI,
        "c4isr": 91.0,
        "a2ad": True,
        "valor_spu": 54_000_000.0,
        "efetivo_decl": 240,
        "efetivo_fim": 210,
        "cpfs_ativos": 238,
        "cpfs_reserva": 10,
        "custeio_decl": 22_000_000.0,
        "empenhado_cgu": 22_100_000.0,
        "acionamentos": 35,
        "disponibilidade": 93.5,
        "dist_fronteira": 960.0,
        "area_urbana": True,
    },
    # 7. FEI com quebra de prontidão (<85%)
    {
        "sigla": "2º RCC (Reg C Bld)",
        "cidade": "Pirassununga - SP",
        "lat": -21.996944,
        "lon": -47.425833,
        "coeb": ClassificacaoCOEB.FEI,
        "c4isr": 62.0,
        "a2ad": False,
        "valor_spu": 140_000_000.0,
        "efetivo_decl": 590,
        "efetivo_fim": 480,
        "cpfs_ativos": 585,
        "cpfs_reserva": 45,
        "custeio_decl": 41_000_000.0,
        "empenhado_cgu": 41_800_000.0,
        "acionamentos": 19,
        "disponibilidade": 76.0,  # Quebra de Prontidão FEI (<85%)
        "dist_fronteira": 750.0,
        "area_urbana": True,
    },
]

CIDADES_RESTANTES = [
    ("4º BIL", "Osasco - SP", -23.532486, -46.791680, ClassificacaoCOEB.FEP, 55.0, False, 210_000_000.0, 620.0, True),
    ("12º GAC", "Jundiaí - SP", -23.185708, -46.897806, ClassificacaoCOEB.FEP, 68.0, True, 165_000_000.0, 610.0, True),
    ("6º RCB", "Alegrete - RS", -29.783056, -55.791944, ClassificacaoCOEB.FEP, 64.0, True, 48_000_000.0, 95.0, False),
    ("17º BLog", "Juiz de Fora - MG", -21.762423, -43.343399, ClassificacaoCOEB.FEP, 58.0, False, 110_000_000.0, 910.0, True),
    ("3º BAvEx", "Campo Grande - MS", -20.469710, -54.620121, ClassificacaoCOEB.FEI, 84.0, True, 88_000_000.0, 290.0, False),
    ("10º BLog", "Alegrete - RS", -29.791000, -55.775000, ClassificacaoCOEB.FEP, 51.0, False, 39_000_000.0, 98.0, False),
    ("23º BI", "Blumenau - SC", -26.919444, -49.066111, ClassificacaoCOEB.FEP, 49.0, False, 175_000_000.0, 380.0, True),
    ("34º BIMec", "Foz do Iguaçu - PR", -25.516336, -54.585376, ClassificacaoCOEB.FEI, 76.0, True, 92_000_000.0, 12.0, True),
    ("14º BIMtz", "Jaboatão dos Guararapes - PE", -8.112867, -35.014964, ClassificacaoCOEB.FEP, 45.0, False, 195_000_000.0, 1850.0, True),
    ("52º BIS", "Marabá - PA", -5.368579, -49.117891, ClassificacaoCOEB.FEP, 61.0, True, 44_000_000.0, 420.0, False),
    ("19º BC", "Salvador - BA", -12.971400, -38.501400, ClassificacaoCOEB.FEC, 22.0, False, 340_000_000.0, 1650.0, True),
    ("28º BC", "Aracaju - SE", -10.947247, -37.073082, ClassificacaoCOEB.FEC, 28.0, False, 230_000_000.0, 1720.0, True),
    ("1º BG (Btl Guarda)", "Porto Alegre - RS", -30.034647, -51.217658, ClassificacaoCOEB.FEC, 19.0, False, 410_000_000.0, 310.0, True),
]


def gerar_oms(reset: bool = True) -> int:
    """Popula o banco de dados com as 20 OMs de teste."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        if reset:
            db.query(TransparenciaDados).delete()
            db.query(Sislog).delete()
            db.query(Estrategia).delete()
            db.query(Sigpes).delete()
            db.query(PatrimonioUniao).delete()
            db.query(DoutrinaTecnologia).delete()
            db.query(OM).delete()
            db.commit()

        todos_perfis = list(PERFIS_OMS)
        for sigla, cidade, lat, lon, coeb, c4isr, a2ad, val_spu, dist_f, urbana in CIDADES_RESTANTES:
            ef_decl = random.randint(350, 750)
            ef_fim = int(ef_decl * (0.78 if coeb == ClassificacaoCOEB.FEI else 0.55 if coeb == ClassificacaoCOEB.FEP else 0.42))
            # Introduz anomalia de folha em parte das OMs FEC
            cpfs_at = int(ef_decl * (0.86 if coeb == ClassificacaoCOEB.FEC and random.random() < 0.5 else 0.99))
            custeio_decl = round(random.uniform(18_000_000, 38_000_000), 2)
            empenhado = round(custeio_decl * (1.08 if coeb == ClassificacaoCOEB.FEC else 1.01), 2)

            todos_perfis.append(
                {
                    "sigla": sigla,
                    "cidade": cidade,
                    "lat": lat,
                    "lon": lon,
                    "coeb": coeb,
                    "c4isr": c4isr,
                    "a2ad": a2ad,
                    "valor_spu": val_spu,
                    "efetivo_decl": ef_decl,
                    "efetivo_fim": ef_fim,
                    "cpfs_ativos": cpfs_at,
                    "cpfs_reserva": random.randint(20, 160),
                    "custeio_decl": custeio_decl,
                    "empenhado_cgu": empenhado,
                    "acionamentos": random.randint(15, 40) if coeb == ClassificacaoCOEB.FEI else random.randint(4, 15) if coeb == ClassificacaoCOEB.FEP else random.randint(0, 3),
                    "disponibilidade": round(random.uniform(86, 97), 1) if coeb != ClassificacaoCOEB.FEC else round(random.uniform(52, 74), 1),
                    "dist_fronteira": dist_f,
                    "area_urbana": urbana,
                }
            )

        for idx, p in enumerate(todos_perfis, start=1):
            uasg = f"160{idx:03d}"
            rip = f"RIP-{7000 + idx:04d}-SPU"
            cnpj = fake.cnpj()
            cep = fake.postcode()
            endereco = f"{fake.street_address()}, {p['cidade']}"

            om = OM(
                codigo_uasg=uasg,
                rip_spu=rip,
                cnpj_ug=cnpj,
                sigla=p["sigla"],
                cep=cep,
                endereco=endereco,
                latitude=p["lat"],
                longitude=p["lon"],
                alertas_auditoria=[],
            )
            db.add(om)
            db.flush()

            db.add(
                DoutrinaTecnologia(
                    id_om=om.id_om,
                    classificacao_coeb=p["coeb"],
                    indice_tecnologia_c4isr=p["c4isr"],
                    papel_a2ad=p["a2ad"],
                )
            )
            db.add(
                PatrimonioUniao(
                    id_om=om.id_om,
                    rip_spu=rip,
                    valor_imovel_brl=p["valor_spu"],
                )
            )
            db.add(
                Sigpes(
                    id_om=om.id_om,
                    efetivo_total_declarado=p["efetivo_decl"],
                    efetivo_fim=p["efetivo_fim"],
                    custeio_declarado_brl=p["custeio_decl"],
                )
            )
            db.add(
                TransparenciaDados(
                    id_om=om.id_om,
                    ano_mes="2026-10",
                    total_empenhado=p["empenhado_cgu"],
                    cpfs_ativos=p["cpfs_ativos"],
                    cpfs_reserva=p["cpfs_reserva"],
                )
            )
            db.add(
                Sislog(
                    id_om=om.id_om,
                    acionamentos_reais_36m=p["acionamentos"],
                    taxa_disponibilidade=p["disponibilidade"],
                )
            )
            db.add(
                Estrategia(
                    id_om=om.id_om,
                    dist_fronteira_km=p["dist_fronteira"],
                    area_urbana=p["area_urbana"],
                )
            )

        db.commit()
        return len(todos_perfis)
    finally:
        db.close()


if __name__ == "__main__":
    total = gerar_oms(reset=True)
    print(f"[SIGA-F4] {total} OMs geradas e persistidas com sucesso no banco de dados.")
