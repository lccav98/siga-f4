"""Mapeamento territorial e organizacional do Exército Brasileiro (C Mil A, RM, UF e Brigada)."""

import re
from typing import Dict, List, Tuple

# UF -> (Região Militar, Comando Militar de Área)
_UF_PARA_RM_CMA: Dict[str, Tuple[str, str]] = {
    "RJ": ("1ª RM", "CML"),
    "ES": ("1ª RM", "CML"),
    "SP": ("2ª RM", "CMSE"),
    "RS": ("3ª RM", "CMS"),
    "MG": ("4ª RM", "CML"),
    "PR": ("5ª RM", "CMS"),
    "SC": ("5ª RM", "CMS"),
    "BA": ("6ª RM", "CMNE"),
    "SE": ("6ª RM", "CMNE"),
    "PE": ("7ª RM", "CMNE"),
    "AL": ("7ª RM", "CMNE"),
    "PB": ("7ª RM", "CMNE"),
    "RN": ("7ª RM", "CMNE"),
    "PA": ("8ª RM", "CMN"),
    "AP": ("8ª RM", "CMN"),
    "MA": ("8ª RM", "CMN"),
    "MS": ("9ª RM", "CMO"),
    "MT": ("9ª RM", "CMO"),
    "CE": ("10ª RM", "CMNE"),
    "PI": ("10ª RM", "CMNE"),
    "DF": ("11ª RM", "CMP"),
    "GO": ("11ª RM", "CMP"),
    "TO": ("11ª RM", "CMP"),
    "AM": ("12ª RM", "CMA"),
    "RR": ("12ª RM", "CMA"),
    "RO": ("12ª RM", "CMA"),
    "AC": ("12ª RM", "CMA"),
}

# Municípios do Triângulo Mineiro subordinados operacionalmente à 11ª RM / CMP
_CIDADES_CMP_MG = ("UBERLÂNDIA", "UBERABA", "ARAGUARI")

# Brigadas classificadas como FEI (Forças de Emprego Imediato) na Faixa de Fronteira
BRIGADAS_FEI_FRONTEIRA = frozenset({
    "1ª Bda Inf Sl",
    "2ª Bda Inf Sl",
    "16ª Bda Inf Sl",
    "17ª Bda Inf Sl",
    "22ª Bda Inf Sl",
    "13ª Bda Inf Mtz",
    "18ª Bda Inf Pan",
    "4ª Bda C Mec",
    "15ª Bda Inf Mec",
    "1ª Bda C Mec",
    "2ª Bda C Mec",
    "3ª Bda C Mec",
})

# Regras ordenadas para identificar Brigada / Grande Comando pela sigla da OM.
# O uso de `(?<!\d)` evita colisões como "3º RCC" dentro de "13º RCC".
_REGRAS_BRIGADA: List[Tuple[Tuple[str, ...], str]] = [
    # --- 5 BRIGADAS FEP (FORPRON) ---
    (("PQDT", "DOMPSA"), "Bda Inf Pqdt (FEP)"),
    (("12ª BDA", "4º BIL", "5º BIL", "6º BIL", "20º GAC L", "12º BLOG L", "5ª BIA AAAE L"), "12ª Bda Inf L (Amv) (FEP)"),
    (("23ª BDA", "50º BIS", "51º BIS", "52º BIS", "53º BIS", "1º GAC SL", "23º BLOG SL", "23ª CIA COM SL"), "23ª Bda Inf Sl (FEP)"),
    (("11ª BDA", "2º BIL", "4º BIMTZ", "28º BI MEC", "37º BI MEC", "13º RC MEC", "2º GAC L", "12º GAC", "2º BLOG L", "11º CIA COM MEC"), "11ª Bda Inf Mec (FEP)"),
    (("5ª BDA", "3º RCC", "5º RCC", "13º BIB", "20º BIB", "5º GAC AP", "15º GAC AP", "5º BE CMB BLD", "5º BLOG", "5º CIA COM BLD"), "5ª Bda C Bld (FEP)"),

    # --- GRANDES COMANDOS / BRIGADAS DE EMPREGO ESPECIALIZADO ---
    (("COPESP", "1º BFESP", "1º BAC", "1º BOPPSC", "3ª CIA FE"), "COpEsp (Cmdo Op Esp)"),
    (("BAVEX",), "CAvEx (Aviação do Exército)"),
    (("COMDCIBER", "BINT", "1º BGE", "CIGE", "CDS", "CTEX", "CAEX", "CITEX", "CTA", "CIA INTLG"), "DCT / Def Ciber / Intlg"),
    (("GMF", "GAAAE", "9ª BIA AAAE", "1ª BDA AAAE", "ART EX"), "Cmdo Art Ex / 1ª Bda AAAe"),

    # --- BRIGADAS DE SELVA E PANTANAL (CMA / CMN / CMO) ---
    (("1ª BDA INF SL", "7º BIS", "1º ESQD C SL", "12º ESQD C MEC", "10º GAC SL", "1º BTL LOG SL", "PEF PACARAIMA", "PEF BONFIM"), "1ª Bda Inf Sl"),
    (("2ª BDA INF SL", "3º BIS", "5º BIS", "2º CIA COM SL"), "2ª Bda Inf Sl"),
    (("16ª BDA INF SL", "8º BIS", "17º BIS", "16ª CIA COM SL"), "16ª Bda Inf Sl"),
    (("17ª BDA INF SL", "4º BIS", "6º BIS", "54º BIS", "61º BIS", "17ª CIA COM SL", "PEF EPITACIOLÂNDIA"), "17ª Bda Inf Sl"),
    (("22ª BDA INF SL", "2º BIS", "24º BIS", "34º BIS", "CIA ESP FRON OIAPOQUE"), "22ª Bda Inf Sl"),
    (("1º BIS", "1º CIA COM SL"), "CMA / Tropas Diretas (Selva)"),
    (("18ª BDA INF PAN", "17º BTL FRON", "47º BI"), "18ª Bda Inf Pan"),
    (("13ª BDA INF MTZ", "2º BTL FRON", "44º BI MTZ", "58º BI MTZ", "18º GAC"), "13ª Bda Inf Mtz"),

    # --- BRIGADAS MECANIZADAS, BLINDADAS E INFANTARIA ---
    (("6ª BDA C BLD", "6ª BDA INF BLD", "1º RCC", "4º RCC", "7º BIB", "29º BIB", "3º GAC AP", "4º BLOG"), "6ª Bda Inf Bld"),
    (("1ª BDA C MEC", "1º RCB", "4º RCB", "1º RC MEC", "2º RC MEC", "19º RC MEC", "19º GAC", "1º BCOM", "1º BLOG", "1ª CIA ENG"), "1ª Bda C Mec"),
    (("2ª BDA C MEC", "6º RCB", "5º RC MEC", "8º RC MEC", "22º GAC AP", "2ª CIA ENG", "10º BLOG"), "2ª Bda C Mec"),
    (("3ª BDA C MEC", "9º RCB", "3º RC MEC", "7º RC MEC", "12º RC MEC", "25º GAC", "3º BLOG", "3ª CIA ENG"), "3ª Bda C Mec"),
    (("8ª BDA INF MTZ", "9º BI MTZ", "18º BI MTZ", "19º BI MTZ", "6º GAC", "13º GAC"), "8ª Bda Inf Mtz"),
    (("14ª BDA INF MTZ", "23º BI", "62º BI", "63º BI", "14º RC MEC", "16º ESQD C MEC", "28º GAC", "14º PEL PE", "14ª CIA ENG"), "14ª Bda Inf Mtz"),
    (("15ª BDA INF MEC", "30º BI MEC", "33º BI MEC", "34º BI MEC", "15ª CIA INF MTZ", "26º GAC", "15º BLOG", "15º CIA COM"), "15ª Bda Inf Mec"),
    (("4ª BDA C MEC", "10º RC MEC", "11º RC MEC", "17º RC MEC", "20º RCB", "9º GAC", "28º BLOG", "4ª CIA ENG", "9º BCOM GE"), "4ª Bda C Mec"),
    (("3ª BDA INF MEC", "36º BI MEC", "41º BI MTZ", "22º BI", "32º GAC", "16º BLOG", "6º BCOM", "6º CIA COM"), "3ª Bda Inf Mec"),
    (("4ª BDA INF L MTH", "10º BI L MTH", "11º BI MTH", "32º BI L MTH", "4º GAC L MTH", "17º BLOG L MTH"), "4ª Bda Inf L Mth"),
    (("GUES", "9ª BDA", "1º BI MTZ (ES)", "2º BI MTZ (ES)", "57º BI MTZ (ES)", "31º GAC (ES)"), "GUEs / 9ª Bda Inf Mtz"),
    (("7ª BDA INF MTZ", "14º BI MTZ", "15º BI MTZ", "16º BI MTZ", "16º RC MEC", "7º GAC", "17º GAC"), "7ª Bda Inf Mtz"),
    (("10ª BDA INF MTZ", "71º BI MTZ", "72º BI CAAT", "31º BI MTZ", "59º BI MTZ", "10ª CIA ENG"), "10ª Bda Inf Mtz"),
    (("2º RCC", "22º BLOG L"), "2ª DE / Apoio Mecanizado"),

    # --- GRUPAMENTOS DE ENGENHARIA (1º ao 5º Gpt E) E SUAS UNIDADES ---
    (("1º GPT E", "1º BEC", "2º BEC", "3º BEC", "4º BEC", "7º BE CMB", "CRO/7"), "1º Gpt E (CMNE)"),
    (("2º GPT E", "5º BEC", "6º BEC", "7º BEC", "8º BEC", "21ª CIA ENG CNST", "CRO/12"), "2º Gpt E (CMA)"),
    (("3º GPT E", "9º BEC", "9º BE CMB", "CO/3º GPT E"), "3º Gpt E (CMO)"),
    (("4º GPT E", "3º BE CMB", "6º BE CMB", "12º BE CMB BLD", "1º B FV", "CRO/3", "CRO/5"), "4º Gpt E (CMS)"),
    (("5º GPT E", "1º BE CMB", "4º BE CMB", "CRO/1"), "5º Gpt E (CML)"),
    (("2º B FV", "2º BFERR"), "DEC / Engenharia de Construção"),
    (("BEC", "GPT E", "B FV", "CRO/"), "Engenharia (Gpt E / DEC)"),
    (("BE CMB", "GAC", "BCOM", "BLOG"), "Tropa Direta DE / AD"),
    (("HCE", "HMA", "HGE", "HGU", "HMIL", "POLICL", "PMRJ", "PMPV", "PMN", "PMPA", "PMCG", "PMCAMP", "OCEX", "IBEX", "LQFEX"), "Saúde Militar (DSau / FUSEx)"),
    (("DSUP", "ARSENAL", "AGR", "AGSP", "AGRS", "PQRMNT", "BAPLOGEX", "BTL SUP", "BTL MNT", "BTL TRNS"), "Apoio Logístico (RM)"),
    (("BG", "BGP", "RCG", "GUARDAS", "BPE", "PEL PE"), "Guarda / Polícia do Exército"),
    (("AMAN", "ESSA", "BTL INSTR"), "Estab. de Ensino / Instrução"),
    (("CIA CMDO", "CMDO "), "Comando de Área / DE / RM"),
]


_PADRAO_OM_SAUDE = re.compile(
    r"\b(HCE|HMA[A-Z]*|HGE[A-Z]*|HGU[A-Z]*|HMIL|H\s*MIL|H\s*GER|HOSPITAL|POLICL[IÍ]NICA|PMRJ|PMPV|PMN|PMPA|PMCG|PMCAMP|OCEX|IBEX|LQFEX|DSAU|HCMP|B\s*SAU)\b",
    re.IGNORECASE,
)


_PADRAO_OM_ENSINO = re.compile(
    r"\b(AMAN|ESSA|BTL\s+INSTR|ECEME|ESAO|ESFCEX|IME)\b",
    re.IGNORECASE,
)

# Grandes Unidades de Combate / Apoio Divisionário FEC (Reserva Estratégica, Defesa do Litoral e C2 DE - COEB 2026)
BRIGADAS_FEC_COMBATE_DE = frozenset({
    "6ª Bda Inf Bld",
    "3ª Bda Inf Mec",
    "4ª Bda Inf L Mth",
    "GUEs / 9ª Bda Inf Mtz",
    "7ª Bda Inf Mtz",
    "8ª Bda Inf Mtz",
    "10ª Bda Inf Mtz",
    "14ª Bda Inf Mtz",
    "2ª DE / Apoio Mecanizado",
    "Tropa Direta DE / AD",
})


def eh_om_saude(sigla: str) -> bool:
    """Identifica Organizações Militares de Saúde (Hospitais, Policlínicas, Institutos DSau)."""
    return bool(sigla and _PADRAO_OM_SAUDE.search(sigla))


def eh_om_ensino(sigla: str) -> bool:
    """Identifica OMs de Ensino/Formação (Capacidades Institucionais — COEB EB20-MF-07.101, 5.6.1.4)."""
    return bool(sigla and _PADRAO_OM_ENSINO.search(sigla))


def extrair_uf_e_municipio(endereco: str) -> Tuple[str, str]:
    """Extrai município e UF de strings como 'Rua X, Cidade - UF' ou 'Cidade - UF'."""
    if not endereco:
        return ("Não informado", "ND")

    partes = endereco.rsplit(",", 1)
    trecho_cidade = partes[-1].strip()
    match = re.match(r"^(.*?)\s*-\s*([A-Za-z]{2})$", trecho_cidade)
    if match:
        return (match.group(1).strip(), match.group(2).strip().upper())
    return (trecho_cidade, "ND")


def inferir_localizacao_militar(sigla: str, endereco: str) -> Dict[str, str]:
    """Resolve UF, Região Militar, Comando Militar de Área e Brigada de uma OM."""
    municipio, uf = extrair_uf_e_municipio(endereco)
    rm, cma = _UF_PARA_RM_CMA.get(uf, ("Sem RM", "Sem C Mil A"))

    if uf == "MG" and municipio.upper() in _CIDADES_CMP_MG:
        rm, cma = ("11ª RM", "CMP")

    sigla_up = (sigla or "").upper()
    brigada = "Guarnição / Apoio Territorial"

    for padroes, nome_brigada in _REGRAS_BRIGADA:
        if any(re.search(rf"(?<!\d){re.escape(p)}", sigla_up) for p in padroes):
            brigada = nome_brigada
            break

    return {
        "municipio": municipio,
        "uf": uf,
        "regiao_militar": rm,
        "comando_militar_area": cma,
        "brigada": brigada,
    }
