"""Gerador de massa de dados realista do Exército Brasileiro para o SIGA-F4.

Cobre os 8 Comandos Militares de Área (CMA, CMN, CMO, CMP, CML, CMSE, CMS, CMNE)
com mais de 220 Organizações Militares reais classificadas conforme o COEB:
- FEI (Força de Emprego Imediato): Selva/Fronteira A2/AD, OpEsp, Pqdt, Amv, Ciber, GE, Intlg, AvEx, AAAe/GMF.
- FEP (Força de Emprego Pronto / FORPRON): Brigadas Blindadas, Mecanizadas, Artilharia, Eng, Com e Log operativa.
- FEC (Força de Emprego Condicionado): Guarda, PE, Caçadores/Infantaria territorial, Depósitos, Arsenais e Apoio RM.
"""

import random
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from faker import Faker

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.core.estrutura_eb import (
    BRIGADAS_FEC_COMBATE_DE,
    eh_om_ensino,
    eh_om_saude,
    inferir_localizacao_militar,
)
from backend.models.database import Base, SessionLocal, engine
from backend.models.schemas import (
    ClassificacaoCOEB,
    DoutrinaTecnologia,
    Estrategia,
    OM,
    PatrimonioUniao,
    SaudeIndicadores,
    Sigpes,
    Sislog,
    TransparenciaDados,
)

fake = Faker("pt_BR")
Faker.seed(42)
random.seed(42)

# Coordenadas reais (lat, lon, dist_fronteira_km, area_urbana, multiplicador_valor_spu)
GUARNICOES: Dict[str, Tuple[float, float, float, bool, float]] = {
    "Brasília - DF": (-15.793889, -47.882778, 980.0, True, 2.2),
    "Rio de Janeiro - RJ": (-22.906847, -43.172896, 1150.0, True, 2.8),
    "Vila Militar - RJ": (-22.862500, -43.401944, 1130.0, True, 1.9),
    "Niterói - RJ": (-22.883333, -43.103611, 1160.0, True, 2.1),
    "Petrópolis - RJ": (-22.505000, -43.178611, 1120.0, True, 1.4),
    "Resende - RJ": (-22.468889, -44.446667, 1020.0, False, 1.1),
    "Valença - RJ": (-22.245556, -43.700278, 1080.0, False, 0.8),
    "Três Rios - RJ": (-22.116667, -43.208889, 1100.0, True, 0.9),
    "Campos dos Goytacazes - RJ": (-21.754444, -41.324444, 1280.0, True, 1.1),
    "São Paulo - SP": (-23.550520, -46.633308, 790.0, True, 3.0),
    "Osasco - SP": (-23.532486, -46.791680, 775.0, True, 2.0),
    "Barueri - SP": (-23.511111, -46.876111, 770.0, True, 2.1),
    "Campinas - SP": (-22.905556, -47.060833, 730.0, True, 1.8),
    "Caçapava - SP": (-23.100833, -45.706944, 880.0, True, 1.2),
    "Taubaté - SP": (-23.026389, -45.555278, 895.0, True, 1.3),
    "Lorena - SP": (-22.730833, -45.124722, 940.0, True, 0.9),
    "Pindamonhangaba - SP": (-22.923889, -45.461667, 905.0, True, 1.0),
    "Jundiaí - SP": (-23.185708, -46.897806, 745.0, True, 1.6),
    "Itu - SP": (-23.264167, -47.299167, 710.0, True, 1.2),
    "Pirassununga - SP": (-21.996944, -47.425833, 695.0, False, 1.0),
    "Lins - SP": (-21.678611, -49.742500, 480.0, True, 0.8),
    "Santos - SP": (-23.960833, -46.333611, 835.0, True, 2.0),
    "Guarujá - SP": (-23.993056, -46.256389, 845.0, True, 1.9),
    "Praia Grande - SP": (-24.005833, -46.402778, 840.0, True, 1.8),
    "Belo Horizonte - MG": (-19.916667, -43.934444, 1140.0, True, 2.2),
    "Juiz de Fora - MG": (-21.762423, -43.343399, 1090.0, True, 1.4),
    "São João del-Rei - MG": (-21.135556, -44.261667, 1020.0, False, 0.9),
    "Montes Claros - MG": (-16.735000, -43.861667, 1340.0, True, 1.0),
    "Uberlândia - MG": (-18.918611, -48.277222, 780.0, True, 1.5),
    "Uberaba - MG": (-19.748333, -47.931944, 790.0, True, 1.2),
    "Araguari - MG": (-18.647222, -48.186944, 800.0, True, 0.9),
    "Três Corações - MG": (-21.694722, -45.255278, 950.0, False, 0.9),
    "Itajubá - MG": (-22.425556, -45.452778, 930.0, False, 0.9),
    "Pouso Alegre - MG": (-22.230000, -45.936389, 885.0, True, 1.0),
    "Vila Velha - ES": (-20.329722, -40.292500, 1420.0, True, 1.7),
    "Manaus - AM": (-3.119028, -60.021731, 180.0, True, 1.4),
    "São Gabriel da Cachoeira - AM": (-0.130320, -67.089160, 25.0, False, 0.5),
    "Tabatinga - AM": (-4.252500, -69.938056, 4.0, True, 0.5),
    "Tefé - AM": (-3.353611, -64.711389, 280.0, False, 0.5),
    "Humaitá - AM": (-7.506111, -63.020833, 210.0, False, 0.5),
    "Barcelos - AM": (-0.975000, -62.923889, 195.0, False, 0.4),
    "Boa Vista - RR": (2.820000, -60.673333, 65.0, True, 0.9),
    "Pacaraima - RR": (4.477778, -61.147778, 2.0, False, 0.3),
    "Bonfim - RR": (3.360000, -59.833056, 3.0, False, 0.3),
    "Porto Velho - RO": (-8.761944, -63.903889, 95.0, True, 1.0),
    "Guajará-Mirim - RO": (-10.782778, -65.339444, 3.0, False, 0.4),
    "Rio Branco - AC": (-9.974722, -67.810000, 75.0, True, 0.8),
    "Cruzeiro do Sul - AC": (-7.627778, -72.675556, 45.0, False, 0.4),
    "Epitaciolândia - AC": (-11.028889, -68.741111, 2.0, False, 0.3),
    "Belém - PA": (-1.455833, -48.503889, 520.0, True, 1.5),
    "Marabá - PA": (-5.368579, -49.117891, 680.0, False, 0.7),
    "Altamira - PA": (-3.203333, -52.206389, 640.0, False, 0.5),
    "Itaituba - PA": (-4.276111, -55.983611, 590.0, False, 0.5),
    "Santarém - PA": (-2.443056, -54.708333, 490.0, True, 0.7),
    "Tucuruí - PA": (-3.766111, -49.672500, 710.0, False, 0.5),
    "Macapá - AP": (0.034444, -51.066389, 145.0, True, 0.8),
    "Oiapoque - AP": (3.843056, -51.835000, 3.0, False, 0.3),
    "Imperatriz - MA": (-5.526389, -47.491667, 940.0, True, 0.8),
    "São Luís - MA": (-2.529722, -44.302778, 1020.0, True, 1.4),
    "Campo Grande - MS": (-20.469710, -54.620121, 240.0, True, 1.3),
    "Dourados - MS": (-22.220833, -54.805833, 95.0, True, 0.9),
    "Corumbá - MS": (-19.008889, -57.651389, 8.0, False, 0.6),
    "Ponta Porã - MS": (-22.536111, -55.725556, 2.0, False, 0.5),
    "Amambai - MS": (-23.104167, -55.225556, 35.0, False, 0.5),
    "Bela Vista - MS": (-22.108889, -56.521111, 3.0, False, 0.4),
    "Jardim - MS": (-21.480278, -56.138056, 85.0, False, 0.5),
    "Aquidauana - MS": (-20.471111, -55.787222, 160.0, False, 0.5),
    "Coxim - MS": (-18.506667, -54.760000, 260.0, False, 0.5),
    "Três Lagoas - MS": (-20.751111, -51.678333, 470.0, True, 0.8),
    "Cuiabá - MT": (-15.601111, -56.097222, 220.0, True, 1.2),
    "Cáceres - MT": (-16.070556, -57.678889, 65.0, False, 0.5),
    "Rondonópolis - MT": (-16.470833, -54.635556, 360.0, True, 0.8),
    "Barra do Garças - MT": (-15.890000, -52.256667, 560.0, False, 0.6),
    "Goiânia - GO": (-16.686891, -49.264794, 820.0, True, 1.7),
    "Anápolis - GO": (-16.326667, -48.952778, 860.0, True, 1.1),
    "Cristalina - GO": (-16.768611, -47.613611, 950.0, False, 0.7),
    "Formosa - GO": (-15.537222, -47.334167, 1020.0, False, 0.7),
    "Jataí - GO": (-17.881389, -51.714444, 590.0, False, 0.7),
    "Ipameri - GO": (-17.721944, -48.159722, 910.0, False, 0.6),
    "Palmas - TO": (-10.184444, -48.333611, 890.0, True, 1.0),
    "Porto Alegre - RS": (-30.034647, -51.217658, 310.0, True, 2.3),
    "Santa Maria - RS": (-29.684167, -53.806944, 195.0, True, 1.1),
    "Uruguaiana - RS": (-29.754722, -57.088333, 5.0, True, 0.7),
    "Alegrete - RS": (-29.783056, -55.791944, 95.0, False, 0.6),
    "Santiago - RS": (-29.191667, -54.866944, 115.0, False, 0.6),
    "Bagé - RS": (-31.331389, -54.106944, 48.0, True, 0.7),
    "São Borja - RS": (-28.660556, -56.004444, 6.0, False, 0.5),
    "Itaqui - RS": (-29.125278, -56.553056, 2.0, False, 0.5),
    "Quaraí - RS": (-30.387500, -56.451389, 2.0, False, 0.5),
    "Santana do Livramento - RS": (-30.890833, -55.532778, 2.0, True, 0.6),
    "Jaguarão - RS": (-32.566111, -53.375833, 3.0, False, 0.5),
    "Dom Pedrito - RS": (-30.982778, -54.673056, 42.0, False, 0.5),
    "Rosário do Sul - RS": (-30.258333, -54.914444, 120.0, False, 0.5),
    "São Gabriel - RS": (-30.336389, -54.320000, 145.0, False, 0.6),
    "Cruz Alta - RS": (-28.638611, -53.606389, 175.0, True, 0.7),
    "Santo Ângelo - RS": (-28.299167, -54.263056, 75.0, False, 0.6),
    "Santa Rosa - RS": (-27.870833, -54.481389, 32.0, False, 0.6),
    "Ijuí - RS": (-28.387778, -53.914722, 130.0, False, 0.6),
    "Passo Fundo - RS": (-28.262778, -52.406667, 220.0, True, 0.9),
    "Pelotas - RS": (-31.765278, -52.337500, 110.0, True, 1.2),
    "Rio Grande - RS": (-32.035000, -52.098611, 135.0, True, 1.1),
    "São Leopoldo - RS": (-29.760278, -51.147222, 325.0, True, 1.3),
    "Sapucaia do Sul - RS": (-29.839167, -51.144167, 320.0, True, 1.3),
    "Cachoeira do Sul - RS": (-30.039167, -52.893889, 210.0, False, 0.6),
    "Bento Gonçalves - RS": (-29.171389, -51.519167, 310.0, True, 0.9),
    "Caxias do Sul - RS": (-29.167778, -51.179444, 340.0, True, 1.4),
    "Curitiba - PR": (-25.428356, -49.273252, 420.0, True, 2.1),
    "Ponta Grossa - PR": (-25.094444, -50.161944, 345.0, True, 1.1),
    "Cascavel - PR": (-24.955556, -53.455278, 115.0, True, 1.1),
    "Foz do Iguaçu - PR": (-25.516336, -54.585376, 8.0, True, 1.0),
    "Guaíra - PR": (-24.080000, -54.255833, 6.0, False, 0.5),
    "Guarapuava - PR": (-25.390833, -51.462222, 265.0, False, 0.8),
    "Apucarana - PR": (-23.550833, -51.460833, 270.0, True, 0.8),
    "Francisco Beltrão - PR": (-26.081111, -53.055000, 58.0, False, 0.6),
    "Palmas - PR": (-26.484167, -51.990556, 125.0, False, 0.5),
    "Rio Negro - PR": (-26.105833, -49.797500, 310.0, False, 0.6),
    "Lapa - PR": (-25.769722, -49.715833, 355.0, False, 0.6),
    "Florianópolis - SC": (-27.595378, -48.548050, 390.0, True, 2.2),
    "Blumenau - SC": (-26.919444, -49.066111, 360.0, True, 1.3),
    "Joinville - SC": (-26.304444, -48.846389, 410.0, True, 1.4),
    "Criciúma - SC": (-28.677500, -49.369722, 330.0, True, 1.0),
    "Tubarão - SC": (-28.466667, -49.006944, 365.0, True, 0.9),
    "São Miguel do Oeste - SC": (-26.725556, -53.518056, 28.0, False, 0.5),
    "Porto União - SC": (-26.238056, -51.078333, 220.0, False, 0.5),
    "Lages - SC": (-27.816111, -50.326111, 270.0, False, 0.7),
    "Recife - PE": (-8.047562, -34.876964, 1890.0, True, 2.0),
    "Jaboatão dos Guararapes - PE": (-8.112867, -35.014964, 1875.0, True, 1.5),
    "Olinda - PE": (-8.008889, -34.855278, 1895.0, True, 1.5),
    "Petrolina - PE": (-9.389167, -40.502778, 1340.0, True, 0.9),
    "São Bento do Una - PE": (-8.522500, -36.444444, 1730.0, False, 0.5),
    "Garanhuns - PE": (-8.890278, -36.492778, 1720.0, False, 0.7),
    "Salvador - BA": (-12.971400, -38.501400, 1650.0, True, 2.3),
    "Feira de Santana - BA": (-12.266667, -38.966667, 1590.0, True, 1.1),
    "Barreiras - BA": (-12.152778, -44.990000, 1120.0, False, 0.7),
    "Paulo Afonso - BA": (-9.406111, -38.221667, 1520.0, False, 0.6),
    "Ilhéus - BA": (-14.788889, -39.049444, 1580.0, True, 1.1),
    "Aracaju - SE": (-10.947247, -37.073082, 1720.0, True, 1.6),
    "Maceió - AL": (-9.665833, -35.735278, 1810.0, True, 1.6),
    "João Pessoa - PB": (-7.115000, -34.863056, 1920.0, True, 1.5),
    "Campina Grande - PB": (-7.230556, -35.881111, 1820.0, True, 1.0),
    "Natal - RN": (-5.794444, -35.211111, 1950.0, True, 1.6),
    "Caicó - RN": (-6.458333, -37.097778, 1790.0, False, 0.5),
    "Fortaleza - CE": (-3.717222, -38.543056, 1780.0, True, 2.0),
    "Crateús - CE": (-5.178333, -40.677500, 1560.0, False, 0.5),
    "Teresina - PI": (-5.089167, -42.801944, 1390.0, True, 1.2),
    "Picos - PI": (-7.076944, -41.466944, 1460.0, False, 0.5),
}

# Catálogo doutrinário (sigla, guarnicao, coeb, c4isr, a2ad, perfil_anomalia)
# Regra COEB (Política de Transformação EB10-P-01.031):
# - FEP (Forças de Emprego de Prontidão): EXCLUSIVAMENTE as OMs das 5 Brigadas ForPron:
#     1) Brigada de Infantaria Paraquedista (Bda Inf Pqdt)
#     2) 12ª Brigada de Infantaria Leve (Aeromóvel) (12ª Bda Inf Amv)
#     3) 23ª Brigada de Infantaria de Selva (23ª Bda Inf Sl)
#     4) 11ª Brigada de Infantaria Mecanizada (11ª Bda Inf Mec)
#     5) 5ª Brigada de Cavalaria Blindada (5ª Bda C Bld)
# - FEI (Forças de Emprego Imediato): exclusivamente as Brigadas da Faixa de Fronteira, módulos multidomínio e resposta inicial imediata (2º plano relativo às FEP).
# - FEC (Forças de Emprego Continuado): Brigadas fora da faixa de fronteira, defesa territorial, guarda, presença, mobilização, depósitos, arsenais e hospitais.
CATALOGO_OMS: List[Tuple[str, str, ClassificacaoCOEB, float, bool, str]] = [
    # --- CASOS DE REFERÊNCIA E CONTRASTE DOUTRINÁRIO ---
    ("1º BInt (Btl Intlg Mil)", "Manaus - AM", ClassificacaoCOEB.FEI, 94.5, True, "limpo"),
    ("2º BG (Btl Guarda)", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEC, 16.0, False, "ambos"),
    ("ComDCiber (Cmdo Def Ciber)", "Brasília - DF", ClassificacaoCOEB.FEI, 98.0, True, "limpo"),
    ("1º BFEsp (Btl Forças Esp)", "Goiânia - GO", ClassificacaoCOEB.FEI, 44.0, True, "limpo"),
    ("1º BGE (Btl Guerra Elet)", "Brasília - DF", ClassificacaoCOEB.FEI, 91.0, True, "limpo"),

    # --- FEP: AS 5 BRIGADAS FORPRON DE EMPREGO DE PRONTIDÃO ---
    # 1) Brigada de Infantaria Paraquedista (Bda Inf Pqdt)
    ("Cia Cmdo Bda Inf Pqdt", "Vila Militar - RJ", ClassificacaoCOEB.FEP, 82.0, True, "limpo"),
    ("25º BI Pqdt", "Vila Militar - RJ", ClassificacaoCOEB.FEP, 78.0, True, "limpo"),
    ("26º BI Pqdt", "Vila Militar - RJ", ClassificacaoCOEB.FEP, 79.5, True, "limpo"),
    ("27º BI Pqdt", "Vila Militar - RJ", ClassificacaoCOEB.FEP, 77.0, True, "limpo"),
    ("8º GAC Pqdt", "Vila Militar - RJ", ClassificacaoCOEB.FEP, 80.0, True, "limpo"),
    ("20º BLog Pqdt", "Vila Militar - RJ", ClassificacaoCOEB.FEP, 73.0, False, "limpo"),
    ("1º Esqd C Pqdt", "Vila Militar - RJ", ClassificacaoCOEB.FEP, 76.0, True, "limpo"),
    ("Btl DOMPSA", "Vila Militar - RJ", ClassificacaoCOEB.FEP, 74.0, False, "limpo"),
    ("Cia Prec Pqdt", "Vila Militar - RJ", ClassificacaoCOEB.FEP, 88.0, True, "limpo"),
    ("21ª Bia AAAe Pqdt", "Vila Militar - RJ", ClassificacaoCOEB.FEP, 81.0, True, "limpo"),

    # 2) Brigada de Infantaria Aeromóvel (12ª Bda Inf L Amv)
    ("Cia Cmdo 12ª Bda Inf Amv", "Caçapava - SP", ClassificacaoCOEB.FEP, 79.0, True, "limpo"),
    ("4º BIL (12ª Bda Amv)", "Osasco - SP", ClassificacaoCOEB.FEP, 76.5, True, "limpo"),
    ("5º BIL (12ª Bda Amv)", "Lorena - SP", ClassificacaoCOEB.FEP, 75.5, True, "limpo"),
    ("6º BIL (12ª Bda Amv)", "Caçapava - SP", ClassificacaoCOEB.FEP, 78.0, True, "limpo"),
    ("20º GAC L (12ª Bda Amv)", "Barueri - SP", ClassificacaoCOEB.FEP, 76.0, True, "limpo"),
    ("12º BLog L (12ª Bda Amv)", "Taubaté - SP", ClassificacaoCOEB.FEP, 72.0, False, "limpo"),
    ("5ª Bia AAAe L (12ª Bda Amv)", "Osasco - SP", ClassificacaoCOEB.FEP, 79.0, True, "limpo"),

    # 3) 23ª Brigada de Infantaria de Selva (23ª Bda Inf Sl)
    ("Cia Cmdo 23ª Bda Inf Sl", "Marabá - PA", ClassificacaoCOEB.FEP, 77.0, True, "limpo"),
    ("50º BIS (23ª Bda Inf Sl)", "Imperatriz - MA", ClassificacaoCOEB.FEP, 72.0, True, "limpo"),
    ("51º BIS (23ª Bda Inf Sl)", "Altamira - PA", ClassificacaoCOEB.FEP, 74.0, True, "limpo"),
    ("52º BIS (23ª Bda Inf Sl)", "Marabá - PA", ClassificacaoCOEB.FEP, 76.0, True, "limpo"),
    ("53º BIS (23ª Bda Inf Sl)", "Itaituba - PA", ClassificacaoCOEB.FEP, 73.5, True, "limpo"),
    ("1º GAC Sl (23ª Bda Inf Sl)", "Marabá - PA", ClassificacaoCOEB.FEP, 74.5, True, "limpo"),
    ("23º BLog Sl (23ª Bda Inf Sl)", "Marabá - PA", ClassificacaoCOEB.FEP, 70.0, False, "limpo"),
    ("23ª Cia Com Sl (23ª Bda Inf Sl)", "Marabá - PA", ClassificacaoCOEB.FEP, 78.0, True, "limpo"),

    # 4) 11ª Brigada de Infantaria Mecanizada (11ª Bda Inf Mec)
    ("Cia Cmdo 11ª Bda Inf Mec", "Campinas - SP", ClassificacaoCOEB.FEP, 76.0, True, "limpo"),
    ("2º BIL (11ª Bda Inf Mec)", "Santos - SP", ClassificacaoCOEB.FEP, 71.0, False, "limpo"),
    ("4º BIMtz (11ª Bda Inf Mec)", "Osasco - SP", ClassificacaoCOEB.FEP, 70.5, False, "limpo"),
    ("28º BI Mec (11ª Bda Inf Mec)", "Campinas - SP", ClassificacaoCOEB.FEP, 77.5, True, "limpo"),
    ("37º BI Mec (11ª Bda Inf Mec)", "Lins - SP", ClassificacaoCOEB.FEP, 73.0, False, "limpo"),
    ("13º RC Mec (11ª Bda Inf Mec)", "Pirassununga - SP", ClassificacaoCOEB.FEP, 74.0, True, "limpo"),
    ("2º GAC L (11ª Bda Inf Mec)", "Itu - SP", ClassificacaoCOEB.FEP, 74.5, False, "limpo"),
    ("12º GAC (11ª Bda Inf Mec)", "Jundiaí - SP", ClassificacaoCOEB.FEP, 75.5, True, "limpo"),
    ("2º BLog L (11ª Bda Inf Mec)", "Campinas - SP", ClassificacaoCOEB.FEP, 71.0, False, "limpo"),
    ("11º Cia Com Mec (11ª Bda Inf Mec)", "Campinas - SP", ClassificacaoCOEB.FEP, 78.0, True, "limpo"),

    # 5) 5ª Brigada de Cavalaria Blindada (5ª Bda C Bld)
    ("Esqd Cmdo 5ª Bda C Bld", "Ponta Grossa - PR", ClassificacaoCOEB.FEP, 77.0, True, "limpo"),
    ("3º RCC (5ª Bda C Bld)", "Ponta Grossa - PR", ClassificacaoCOEB.FEP, 80.0, True, "limpo"),
    ("5º RCC (5ª Bda C Bld)", "Rio Negro - PR", ClassificacaoCOEB.FEP, 78.5, True, "limpo"),
    ("13º BIB (5ª Bda C Bld)", "Ponta Grossa - PR", ClassificacaoCOEB.FEP, 75.0, True, "limpo"),
    ("20º BIB (5ª Bda C Bld)", "Curitiba - PR", ClassificacaoCOEB.FEP, 76.5, True, "limpo"),
    ("5º GAC AP (5ª Bda C Bld)", "Curitiba - PR", ClassificacaoCOEB.FEP, 78.0, True, "limpo"),
    ("15º GAC AP (5ª Bda C Bld)", "Lapa - PR", ClassificacaoCOEB.FEP, 77.0, True, "limpo"),
    ("5º BE Cmb Bld (5ª Bda C Bld)", "Porto União - SC", ClassificacaoCOEB.FEP, 75.5, True, "limpo"),
    ("5º BLog (5ª Bda C Bld)", "Curitiba - PR", ClassificacaoCOEB.FEP, 71.5, False, "limpo"),
    ("5º Cia Com Bld (5ª Bda C Bld)", "Ponta Grossa - PR", ClassificacaoCOEB.FEP, 79.0, True, "limpo"),

    # --- FEI: MÓDULOS MULTIDOMÍNIO, OPESP, AVEX E TROPAS NA FRONTEIRA ---
    ("2º BInt (Btl Intlg Mil)", "Brasília - DF", ClassificacaoCOEB.FEI, 92.0, True, "limpo"),
    ("3º BInt (Btl Intlg Mil)", "Porto Alegre - RS", ClassificacaoCOEB.FEI, 89.0, True, "limpo"),
    ("4º BInt (Btl Intlg Mil)", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEI, 88.5, True, "limpo"),
    ("5º BInt (Btl Intlg Mil)", "Campo Grande - MS", ClassificacaoCOEB.FEI, 87.0, True, "limpo"),
    ("6º BInt (Btl Intlg Mil)", "Recife - PE", ClassificacaoCOEB.FEI, 84.0, False, "limpo"),
    ("COpEsp (Cmdo Op Esp)", "Goiânia - GO", ClassificacaoCOEB.FEI, 86.0, True, "limpo"),
    ("1º BAC (Btl Ações Comandos)", "Goiânia - GO", ClassificacaoCOEB.FEI, 79.0, True, "limpo"),
    ("1º BOpPsc (Btl Op Psic)", "Goiânia - GO", ClassificacaoCOEB.FEI, 81.0, True, "limpo"),
    ("3ª Cia FE (Forças Esp)", "Manaus - AM", ClassificacaoCOEB.FEI, 83.5, True, "limpo"),
    ("1º BAvEx", "Taubaté - SP", ClassificacaoCOEB.FEI, 88.0, True, "limpo"),
    ("2º BAvEx", "Taubaté - SP", ClassificacaoCOEB.FEI, 87.5, True, "limpo"),
    ("3º BAvEx", "Campo Grande - MS", ClassificacaoCOEB.FEI, 85.0, True, "limpo"),
    ("4º BAvEx", "Manaus - AM", ClassificacaoCOEB.FEI, 86.5, True, "limpo"),
    ("6º GMF (Mísseis/Foguetes)", "Formosa - GO", ClassificacaoCOEB.FEI, 90.0, True, "limpo"),
    ("16º GMF (Mísseis/Foguetes)", "Formosa - GO", ClassificacaoCOEB.FEI, 89.0, True, "limpo"),
    ("1º GAAAe (Def Antiaérea)", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEI, 84.0, True, "limpo"),
    ("2º GAAAe (Def Antiaérea)", "Praia Grande - SP", ClassificacaoCOEB.FEI, 82.0, True, "limpo"),
    ("3º GAAAe (Def Antiaérea)", "Caxias do Sul - RS", ClassificacaoCOEB.FEI, 80.5, True, "limpo"),
    ("4º GAAAe (Def Antiaérea)", "Belo Horizonte - MG", ClassificacaoCOEB.FEI, 79.5, True, "limpo"),
    ("11º GAAAe (Def Antiaérea)", "Brasília - DF", ClassificacaoCOEB.FEI, 85.5, True, "limpo"),
    ("12º GAAAe Sl (Def Antiaérea)", "Manaus - AM", ClassificacaoCOEB.FEI, 83.0, True, "limpo"),

    # --- FEI: TROPAS DEBRUÇADAS NA FRONTEIRA (2º PLANO PESSOAL/MATERIAL RELATIVO ÀS FEP) ---
    ("1º BIS (Amv)", "Manaus - AM", ClassificacaoCOEB.FEI, 64.0, True, "limpo"),
    ("2º BIS", "Belém - PA", ClassificacaoCOEB.FEI, 54.0, True, "limpo"),
    ("3º BIS", "Barcelos - AM", ClassificacaoCOEB.FEI, 56.0, True, "limpo"),
    ("4º BIS", "Rio Branco - AC", ClassificacaoCOEB.FEI, 55.0, True, "limpo"),
    ("5º BIS (Btl Inf Sl)", "São Gabriel da Cachoeira - AM", ClassificacaoCOEB.FEI, 59.0, True, "limpo"),
    ("6º BIS", "Guajará-Mirim - RO", ClassificacaoCOEB.FEI, 54.5, True, "limpo"),
    ("7º BIS", "Boa Vista - RR", ClassificacaoCOEB.FEI, 60.5, True, "limpo"),
    ("8º BIS", "Tabatinga - AM", ClassificacaoCOEB.FEI, 62.0, True, "limpo"),
    ("17º BIS", "Tefé - AM", ClassificacaoCOEB.FEI, 55.5, True, "limpo"),
    ("24º BIS", "São Luís - MA", ClassificacaoCOEB.FEI, 49.0, False, "limpo"),
    ("54º BIS", "Humaitá - AM", ClassificacaoCOEB.FEI, 52.5, True, "limpo"),
    ("61º BIS", "Cruzeiro do Sul - AC", ClassificacaoCOEB.FEI, 54.0, True, "limpo"),
    ("1º Esqd C Sl", "Boa Vista - RR", ClassificacaoCOEB.FEI, 58.0, True, "limpo"),
    ("12º Esqd C Mec", "Boa Vista - RR", ClassificacaoCOEB.FEI, 57.0, True, "limpo"),
    ("10º GAC Sl", "Boa Vista - RR", ClassificacaoCOEB.FEI, 56.0, True, "limpo"),
    ("34º BI Mec (Tríplice Front.)", "Foz do Iguaçu - PR", ClassificacaoCOEB.FEI, 63.0, True, "limpo"),
    ("2º Btl Fron", "Cáceres - MT", ClassificacaoCOEB.FEI, 53.0, True, "limpo"),
    ("17º Btl Fron", "Corumbá - MS", ClassificacaoCOEB.FEI, 55.0, True, "limpo"),
    ("10º RC Mec", "Bela Vista - MS", ClassificacaoCOEB.FEI, 54.0, True, "limpo"),
    ("11º RC Mec", "Ponta Porã - MS", ClassificacaoCOEB.FEI, 56.0, True, "limpo"),
    ("17º RC Mec", "Amambai - MS", ClassificacaoCOEB.FEI, 55.0, True, "limpo"),
    ("5º RC Mec", "Quaraí - RS", ClassificacaoCOEB.FEI, 53.0, True, "limpo"),
    ("7º RC Mec", "Santana do Livramento - RS", ClassificacaoCOEB.FEI, 54.0, True, "limpo"),
    ("8º RC Mec", "Uruguaiana - RS", ClassificacaoCOEB.FEI, 56.0, True, "limpo"),
    ("12º RC Mec", "Jaguarão - RS", ClassificacaoCOEB.FEI, 52.0, True, "limpo"),
    ("2º RC Mec", "São Borja - RS", ClassificacaoCOEB.FEI, 53.0, True, "limpo"),
    ("14º RC Mec", "São Miguel do Oeste - SC", ClassificacaoCOEB.FEC, 54.0, False, "limpo"),
    ("16º Esqd C Mec", "Francisco Beltrão - PR", ClassificacaoCOEB.FEC, 54.0, False, "limpo"),
    ("15ª Cia Inf Mtz", "Guaíra - PR", ClassificacaoCOEB.FEI, 55.0, True, "limpo"),
    ("34º BIS (Cia Fron Amapá)", "Macapá - AP", ClassificacaoCOEB.FEI, 52.0, True, "limpo"),
    ("Cia Esp Fron Oiapoque", "Oiapoque - AP", ClassificacaoCOEB.FEI, 51.0, True, "limpo"),
    ("PEF Pacaraima", "Pacaraima - RR", ClassificacaoCOEB.FEI, 49.0, True, "limpo"),
    ("PEF Bonfim", "Bonfim - RR", ClassificacaoCOEB.FEI, 48.0, True, "limpo"),
    ("PEF Epitaciolândia", "Epitaciolândia - AC", ClassificacaoCOEB.FEI, 47.0, True, "limpo"),
    ("1º Cia Com Sl", "Manaus - AM", ClassificacaoCOEB.FEI, 66.0, True, "limpo"),
    ("2º Cia Com Sl", "São Gabriel da Cachoeira - AM", ClassificacaoCOEB.FEI, 62.0, True, "limpo"),
    ("16ª Cia Com Sl", "Tefé - AM", ClassificacaoCOEB.FEI, 60.0, True, "limpo"),
    ("17ª Cia Com Sl", "Porto Velho - RO", ClassificacaoCOEB.FEI, 61.0, True, "limpo"),
    ("2º RCC", "Pirassununga - SP", ClassificacaoCOEB.FEC, 62.0, False, "limpo"),

    # --- FEI: AS 12 BRIGADAS DA FAIXA DE FRONTEIRA | FEC: BRIGADAS DO INTERIOR / LITORAL (EXCETUADAS AS 5 FEP) ---
    ("1º RCC", "Santa Maria - RS", ClassificacaoCOEB.FEC, 68.0, False, "limpo"),
    ("4º RCC", "Rosário do Sul - RS", ClassificacaoCOEB.FEC, 66.0, False, "limpo"),
    ("7º BIB", "Santa Maria - RS", ClassificacaoCOEB.FEC, 62.0, False, "limpo"),
    ("29º BIB", "Santa Maria - RS", ClassificacaoCOEB.FEC, 65.0, False, "limpo"),
    ("1º RCB", "Uruguaiana - RS", ClassificacaoCOEB.FEI, 60.0, True, "limpo"),
    ("4º RCB", "Santo Ângelo - RS", ClassificacaoCOEB.FEI, 61.0, True, "limpo"),
    ("6º RCB", "Alegrete - RS", ClassificacaoCOEB.FEI, 64.0, True, "limpo"),
    ("9º RCB", "São Gabriel - RS", ClassificacaoCOEB.FEI, 62.0, True, "limpo"),
    ("19º RC Mec", "Santa Rosa - RS", ClassificacaoCOEB.FEI, 63.0, True, "limpo"),
    ("1º RC Mec", "Itaqui - RS", ClassificacaoCOEB.FEI, 61.0, True, "limpo"),
    ("3º RC Mec", "Bagé - RS", ClassificacaoCOEB.FEI, 62.0, True, "limpo"),
    ("30º BI Mec", "Apucarana - PR", ClassificacaoCOEB.FEI, 61.0, True, "limpo"),
    ("33º BI Mec", "Cascavel - PR", ClassificacaoCOEB.FEI, 65.0, True, "limpo"),
    ("36º BI Mec", "Uberlândia - MG", ClassificacaoCOEB.FEC, 60.0, False, "limpo"),
    ("20º RCB", "Campo Grande - MS", ClassificacaoCOEB.FEI, 63.0, True, "limpo"),
    ("47º BI", "Coxim - MS", ClassificacaoCOEB.FEI, 55.0, True, "prontidao"),
    ("58º BI Mtz", "Barra do Garças - MT", ClassificacaoCOEB.FEI, 54.0, True, "limpo"),
    ("44º BI Mtz", "Cuiabá - MT", ClassificacaoCOEB.FEI, 57.0, True, "limpo"),
    ("22º BI", "Palmas - TO", ClassificacaoCOEB.FEC, 56.0, False, "limpo"),
    ("41º BI Mtz", "Jataí - GO", ClassificacaoCOEB.FEC, 53.0, False, "limpo"),
    ("1º BI Mtz (Es)", "Vila Militar - RJ", ClassificacaoCOEB.FEC, 63.0, False, "limpo"),
    ("2º BI Mtz (Es)", "Vila Militar - RJ", ClassificacaoCOEB.FEC, 61.0, False, "limpo"),
    ("57º BI Mtz (Es)", "Vila Militar - RJ", ClassificacaoCOEB.FEC, 60.0, False, "limpo"),
    ("32º BI L Mth", "Petrópolis - RJ", ClassificacaoCOEB.FEC, 59.0, False, "limpo"),
    ("11º BI Mth", "São João del-Rei - MG", ClassificacaoCOEB.FEC, 62.0, False, "limpo"),
    ("10º BI L Mth", "Juiz de Fora - MG", ClassificacaoCOEB.FEC, 57.0, False, "limpo"),
    ("71º BI Mtz (Caatinga)", "Garanhuns - PE", ClassificacaoCOEB.FEC, 58.0, False, "limpo"),
    ("72º BI Caat", "Petrolina - PE", ClassificacaoCOEB.FEC, 64.0, False, "limpo"),
    ("14º BI Mtz", "Jaboatão dos Guararapes - PE", ClassificacaoCOEB.FEC, 55.0, False, "limpo"),
    ("15º BI Mtz", "João Pessoa - PB", ClassificacaoCOEB.FEC, 52.0, False, "limpo"),
    ("16º BI Mtz", "Natal - RN", ClassificacaoCOEB.FEC, 53.0, False, "limpo"),
    ("16º RC Mec", "João Pessoa - PB", ClassificacaoCOEB.FEC, 56.0, False, "limpo"),
    ("35º BI", "Feira de Santana - BA", ClassificacaoCOEB.FEC, 51.0, False, "limpo"),
    # --- GRUPAMENTOS DE ENGENHARIA (1º ao 5º Gpt E) E UNIDADES DE ENGENHARIA ---
    # 1º Grupamento de Engenharia (1º Gpt E - CMNE) -> FEC (fora da faixa de fronteira)
    ("Cmdo 1º Gpt E", "João Pessoa - PB", ClassificacaoCOEB.FEC, 60.0, False, "limpo"),
    ("1º BEC", "Caicó - RN", ClassificacaoCOEB.FEC, 58.0, False, "limpo"),
    ("2º BEC", "Teresina - PI", ClassificacaoCOEB.FEC, 56.0, False, "limpo"),
    ("3º BEC", "Picos - PI", ClassificacaoCOEB.FEC, 55.0, False, "limpo"),
    ("4º BEC", "Barreiras - BA", ClassificacaoCOEB.FEC, 57.0, False, "limpo"),
    ("7º BE Cmb", "Natal - RN", ClassificacaoCOEB.FEC, 62.0, False, "limpo"),
    ("CRO/7 (Comissão Reg Obras)", "Recife - PE", ClassificacaoCOEB.FEC, 26.0, False, "limpo"),
    # 2º Grupamento de Engenharia (2º Gpt E - CMA)
    ("Cmdo 2º Gpt E", "Manaus - AM", ClassificacaoCOEB.FEC, 63.0, False, "limpo"),
    ("5º BEC", "Porto Velho - RO", ClassificacaoCOEB.FEI, 61.0, True, "limpo"),
    ("6º BEC", "Boa Vista - RR", ClassificacaoCOEB.FEI, 62.0, True, "limpo"),
    ("7º BEC", "Rio Branco - AC", ClassificacaoCOEB.FEI, 60.0, True, "limpo"),
    ("8º BEC", "Santarém - PA", ClassificacaoCOEB.FEC, 59.0, False, "limpo"),
    ("21ª Cia Eng Cnst", "São Gabriel da Cachoeira - AM", ClassificacaoCOEB.FEI, 61.0, True, "limpo"),
    ("CRO/12 (Comissão Reg Obras)", "Manaus - AM", ClassificacaoCOEB.FEC, 28.0, False, "limpo"),
    # 3º Grupamento de Engenharia (3º Gpt E - CMO)
    ("Cmdo 3º Gpt E", "Campo Grande - MS", ClassificacaoCOEB.FEC, 62.0, False, "limpo"),
    ("9º BEC", "Cuiabá - MT", ClassificacaoCOEB.FEC, 60.0, False, "limpo"),
    ("9º BE Cmb", "Aquidauana - MS", ClassificacaoCOEB.FEC, 63.0, False, "limpo"),
    ("CO/3º Gpt E (Comissão Obras)", "Campo Grande - MS", ClassificacaoCOEB.FEC, 27.0, False, "limpo"),
    # 4º Grupamento de Engenharia (4º Gpt E - CMS)
    ("Cmdo 4º Gpt E", "Porto Alegre - RS", ClassificacaoCOEB.FEC, 64.0, False, "limpo"),
    ("3º BE Cmb", "Cachoeira do Sul - RS", ClassificacaoCOEB.FEC, 65.0, False, "limpo"),
    ("6º BE Cmb", "São Gabriel - RS", ClassificacaoCOEB.FEI, 64.0, True, "limpo"),
    ("12º BE Cmb Bld", "Alegrete - RS", ClassificacaoCOEB.FEI, 65.0, True, "limpo"),
    ("1º B Fv (Btl Ferroviário)", "Lages - SC", ClassificacaoCOEB.FEC, 61.0, False, "limpo"),
    ("CRO/3 (Comissão Reg Obras)", "Porto Alegre - RS", ClassificacaoCOEB.FEC, 27.0, False, "limpo"),
    ("CRO/5 (Comissão Reg Obras)", "Curitiba - PR", ClassificacaoCOEB.FEC, 27.0, False, "limpo"),
    # 5º Grupamento de Engenharia (5º Gpt E - CML) -> FEC (fora da faixa de fronteira)
    ("Cmdo 5º Gpt E", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEC, 63.0, False, "limpo"),
    ("1º BE Cmb (Es)", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEC, 64.0, False, "limpo"),
    ("4º BE Cmb", "Itajubá - MG", ClassificacaoCOEB.FEC, 61.0, False, "limpo"),
    ("CRO/1 (Comissão Reg Obras)", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEC, 27.0, False, "limpo"),
    # Engenharia de Combate vinculada à 2ª DE (CMSE)
    ("2º BE Cmb", "Pindamonhangaba - SP", ClassificacaoCOEB.FEC, 64.0, False, "limpo"),
    ("3º GAC AP", "Santa Maria - RS", ClassificacaoCOEB.FEC, 69.0, False, "limpo"),
    ("4º GAC L Mth", "Juiz de Fora - MG", ClassificacaoCOEB.FEC, 60.0, False, "limpo"),
    ("6º GAC", "Rio Grande - RS", ClassificacaoCOEB.FEC, 59.0, False, "limpo"),
    ("7º GAC", "Olinda - PE", ClassificacaoCOEB.FEC, 57.0, False, "limpo"),
    ("9º GAC", "Jardim - MS", ClassificacaoCOEB.FEI, 60.0, True, "limpo"),
    ("13º GAC", "Cachoeira do Sul - RS", ClassificacaoCOEB.FEC, 58.0, False, "limpo"),
    ("14º GAC", "Pouso Alegre - MG", ClassificacaoCOEB.FEC, 59.0, False, "limpo"),
    ("17º GAC", "Natal - RN", ClassificacaoCOEB.FEC, 55.0, False, "limpo"),
    ("18º GAC", "Rondonópolis - MT", ClassificacaoCOEB.FEI, 60.0, True, "limpo"),
    ("19º GAC", "Santiago - RS", ClassificacaoCOEB.FEI, 61.0, True, "limpo"),
    ("21º GAC", "Niterói - RJ", ClassificacaoCOEB.FEC, 62.0, False, "limpo"),
    ("22º GAC AP", "Uruguaiana - RS", ClassificacaoCOEB.FEI, 65.0, True, "limpo"),
    ("25º GAC", "Bagé - RS", ClassificacaoCOEB.FEI, 60.0, True, "limpo"),
    ("26º GAC", "Guarapuava - PR", ClassificacaoCOEB.FEI, 61.0, True, "limpo"),
    ("27º GAC", "Ijuí - RS", ClassificacaoCOEB.FEC, 58.0, False, "limpo"),
    ("28º GAC", "Criciúma - SC", ClassificacaoCOEB.FEC, 57.0, False, "limpo"),
    ("29º GAC AP", "Cruz Alta - RS", ClassificacaoCOEB.FEC, 66.0, False, "limpo"),
    ("31º GAC (Es)", "Vila Militar - RJ", ClassificacaoCOEB.FEC, 64.0, False, "limpo"),
    ("32º GAC", "Brasília - DF", ClassificacaoCOEB.FEC, 66.0, False, "limpo"),
    ("1º BCom", "Santo Ângelo - RS", ClassificacaoCOEB.FEI, 74.0, True, "limpo"),
    ("2º BCom", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEC, 76.0, False, "limpo"),
    ("3º BCom", "Porto Alegre - RS", ClassificacaoCOEB.FEC, 75.0, False, "limpo"),
    ("4º BCom", "Manaus - AM", ClassificacaoCOEB.FEC, 79.0, False, "limpo"),
    ("5º BCom", "Curitiba - PR", ClassificacaoCOEB.FEC, 73.0, False, "limpo"),
    ("6º BCom", "Cristalina - GO", ClassificacaoCOEB.FEC, 74.0, False, "limpo"),
    ("7º BCom", "Recife - PE", ClassificacaoCOEB.FEC, 71.0, False, "limpo"),
    ("9º BCom GE", "Campo Grande - MS", ClassificacaoCOEB.FEI, 78.0, True, "limpo"),
    ("1º BLog", "Santiago - RS", ClassificacaoCOEB.FEI, 56.0, True, "limpo"),
    ("3º BLog", "Bagé - RS", ClassificacaoCOEB.FEI, 55.0, True, "limpo"),
    ("4º BLog", "Santa Maria - RS", ClassificacaoCOEB.FEC, 59.0, False, "limpo"),
    ("9º BLog", "Campo Grande - MS", ClassificacaoCOEB.FEC, 58.0, False, "limpo"),
    ("10º BLog", "Alegrete - RS", ClassificacaoCOEB.FEI, 54.0, True, "limpo"),
    ("15º BLog", "Cascavel - PR", ClassificacaoCOEB.FEI, 56.0, True, "limpo"),
    ("16º BLog", "Brasília - DF", ClassificacaoCOEB.FEC, 60.0, False, "limpo"),
    ("17º BLog L Mth", "Juiz de Fora - MG", ClassificacaoCOEB.FEC, 58.0, False, "limpo"),
    ("22º BLog L", "Barueri - SP", ClassificacaoCOEB.FEC, 57.0, False, "limpo"),
    ("28º BLog", "Dourados - MS", ClassificacaoCOEB.FEI, 58.0, True, "limpo"),
    ("1º Btl Log Sl", "Boa Vista - RR", ClassificacaoCOEB.FEI, 57.0, True, "limpo"),
    ("12º Btl Sup", "Manaus - AM", ClassificacaoCOEB.FEC, 54.0, False, "limpo"),
    ("1º Btl Mnt", "Manaus - AM", ClassificacaoCOEB.FEC, 59.0, False, "limpo"),
    ("2º B Fv (Btl Ferroviário)", "Araguari - MG", ClassificacaoCOEB.FEC, 55.0, False, "limpo"),
    ("1º BPE", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEC, 50.0, False, "limpo"),

    # --- FEC: FORÇAS DE EMPREGO CONDICIONADO (GUARDA, PE TERRITORIAL, GUARNIÇÕES CONVENCIONAIS, DEPÓSITOS, ARSENAIS, RM) ---
    ("1º BG (Btl Guarda)", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEC, 19.0, False, "folha"),
    ("BGP (Btl Guarda Presidencial)", "Brasília - DF", ClassificacaoCOEB.FEC, 24.0, False, "limpo"),
    ("1º RCG (Dragões Independência)", "Brasília - DF", ClassificacaoCOEB.FEC, 21.0, False, "limpo"),
    ("2º RCG (Reg C Guarda)", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEC, 18.0, False, "ambos"),
    ("3º RCG (Reg C Guarda)", "Porto Alegre - RS", ClassificacaoCOEB.FEC, 17.0, False, "folha"),
    ("2º BPE", "Osasco - SP", ClassificacaoCOEB.FEC, 32.0, False, "limpo"),
    ("3º BPE", "Porto Alegre - RS", ClassificacaoCOEB.FEC, 30.0, False, "folha"),
    ("4º BPE", "Recife - PE", ClassificacaoCOEB.FEC, 29.0, False, "financeiro"),
    ("5º BPE", "Curitiba - PR", ClassificacaoCOEB.FEC, 31.0, False, "limpo"),
    ("6º BPE", "Salvador - BA", ClassificacaoCOEB.FEC, 27.0, False, "ambos"),
    ("7º BPE", "Manaus - AM", ClassificacaoCOEB.FEC, 33.0, False, "limpo"),
    ("8º BPE", "São Paulo - SP", ClassificacaoCOEB.FEC, 30.0, False, "financeiro"),
    ("11º BPE", "Brasília - DF", ClassificacaoCOEB.FEC, 34.0, False, "limpo"),
    ("19º BC", "Salvador - BA", ClassificacaoCOEB.FEC, 22.0, False, "ambos"),
    ("23º BC", "Fortaleza - CE", ClassificacaoCOEB.FEC, 25.0, False, "folha"),
    ("25º BC", "Teresina - PI", ClassificacaoCOEB.FEC, 23.0, False, "financeiro"),
    ("28º BC", "Aracaju - SE", ClassificacaoCOEB.FEC, 28.0, False, "ambos"),
    ("40º BI", "Crateús - CE", ClassificacaoCOEB.FEC, 24.0, False, "limpo"),
    ("59º BI Mtz", "Maceió - AL", ClassificacaoCOEB.FEC, 26.0, False, "folha"),
    ("38º BI", "Vila Velha - ES", ClassificacaoCOEB.FEC, 27.0, False, "ambos"),
    ("12º BI", "Belo Horizonte - MG", ClassificacaoCOEB.FEC, 25.0, False, "ambos"),
    ("55º BI", "Montes Claros - MG", ClassificacaoCOEB.FEC, 24.0, False, "limpo"),
    ("23º BI", "Blumenau - SC", ClassificacaoCOEB.FEC, 48.0, False, "limpo"),
    ("62º BI", "Joinville - SC", ClassificacaoCOEB.FEC, 28.0, False, "folha"),
    ("63º BI", "Florianópolis - SC", ClassificacaoCOEB.FEC, 23.0, False, "ambos"),
    ("9º BI Mtz", "Pelotas - RS", ClassificacaoCOEB.FEC, 26.0, False, "folha"),
    ("18º BI Mtz", "Sapucaia do Sul - RS", ClassificacaoCOEB.FEC, 24.0, False, "financeiro"),
    ("19º BI Mtz", "São Leopoldo - RS", ClassificacaoCOEB.FEC, 25.0, False, "folha"),
    ("31º BI Mtz", "Campina Grande - PB", ClassificacaoCOEB.FEC, 46.0, False, "limpo"),
    ("21º BI", "Recife - PE", ClassificacaoCOEB.FEC, 22.0, False, "ambos"),
    ("56º BI", "Campos dos Goytacazes - RJ", ClassificacaoCOEB.FEC, 21.0, False, "folha"),
    ("3º BI", "Niterói - RJ", ClassificacaoCOEB.FEC, 20.0, False, "ambos"),
    ("26º BI", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEC, 19.0, False, "ambos"),
    ("Cia Gd CML", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEC, 18.0, False, "ambos"),
    ("2º BI", "São Paulo - SP", ClassificacaoCOEB.FEC, 20.0, False, "ambos"),
    ("4º BI", "São Paulo - SP", ClassificacaoCOEB.FEC, 18.5, False, "ambos"),
    ("1º DSup (Depósito Suprimento)", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEC, 22.0, False, "financeiro"),
    ("2º DSup (Depósito Suprimento)", "São Paulo - SP", ClassificacaoCOEB.FEC, 23.0, False, "financeiro"),
    ("3º DSup (Depósito Suprimento)", "Porto Alegre - RS", ClassificacaoCOEB.FEC, 21.0, False, "folha"),
    ("4º DSup (Depósito Suprimento)", "Juiz de Fora - MG", ClassificacaoCOEB.FEC, 24.0, False, "limpo"),
    ("5º DSup (Depósito Suprimento)", "Curitiba - PR", ClassificacaoCOEB.FEC, 25.0, False, "limpo"),
    ("6º DSup (Depósito Suprimento)", "Salvador - BA", ClassificacaoCOEB.FEC, 20.0, False, "ambos"),
    ("7º DSup (Depósito Suprimento)", "Recife - PE", ClassificacaoCOEB.FEC, 22.0, False, "financeiro"),
    ("8º DSup (Depósito Suprimento)", "Belém - PA", ClassificacaoCOEB.FEC, 23.0, False, "limpo"),
    ("9º DSup (Depósito Suprimento)", "Campo Grande - MS", ClassificacaoCOEB.FEC, 26.0, False, "limpo"),
    ("10º DSup (Depósito Suprimento)", "Fortaleza - CE", ClassificacaoCOEB.FEC, 21.0, False, "folha"),
    ("11º DSup (Depósito Suprimento)", "Brasília - DF", ClassificacaoCOEB.FEC, 27.0, False, "limpo"),
    ("AGR (Arsenal Guerra RJ)", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEC, 35.0, False, "financeiro"),
    ("AGSP (Arsenal Guerra SP)", "Barueri - SP", ClassificacaoCOEB.FEC, 37.0, False, "limpo"),
    ("AGRS (Arsenal Guerra RS)", "Porto Alegre - RS", ClassificacaoCOEB.FEC, 34.0, False, "folha"),
    ("BApLogEx (Base Apoio Log)", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEC, 31.0, False, "ambos"),
    ("PqRMnt/1", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEC, 29.0, False, "financeiro"),
    ("PqRMnt/2", "São Paulo - SP", ClassificacaoCOEB.FEC, 30.0, False, "financeiro"),
    ("PqRMnt/3", "Santa Maria - RS", ClassificacaoCOEB.FEC, 32.0, False, "limpo"),
    ("PqRMnt/5", "Curitiba - PR", ClassificacaoCOEB.FEC, 31.0, False, "limpo"),
    ("PqRMnt/7", "Recife - PE", ClassificacaoCOEB.FEC, 28.0, False, "folha"),
    ("PqRMnt/8", "Belém - PA", ClassificacaoCOEB.FEC, 29.0, False, "limpo"),
    ("PqRMnt/9", "Campo Grande - MS", ClassificacaoCOEB.FEC, 30.0, False, "limpo"),
    ("PqRMnt/10", "Fortaleza - CE", ClassificacaoCOEB.FEC, 27.0, False, "folha"),
    ("PqRMnt/12", "Manaus - AM", ClassificacaoCOEB.FEC, 33.0, False, "limpo"),
    # --- SAUDE: REDE DE ORGANIZAÇÕES MILITARES DE SAÚDE (DSau / SAMMED-FUSEx) ---
    ("HCE (Hospital Central Ex)", "Rio de Janeiro - RJ", ClassificacaoCOEB.SAUDE, 68.0, False, "financeiro"),
    ("HMASP (Hosp Mil Área SP)", "São Paulo - SP", ClassificacaoCOEB.SAUDE, 66.0, False, "limpo"),
    ("HMAPA (Hosp Mil Área PA)", "Porto Alegre - RS", ClassificacaoCOEB.SAUDE, 65.0, False, "limpo"),
    ("HMAR (Hosp Mil Área Recife)", "Recife - PE", ClassificacaoCOEB.SAUDE, 62.0, False, "limpo"),
    ("HMAB (Hosp Mil Área Brasília)", "Brasília - DF", ClassificacaoCOEB.SAUDE, 67.0, False, "limpo"),
    ("HMAM (Hosp Mil Área Manaus)", "Manaus - AM", ClassificacaoCOEB.SAUDE, 66.0, False, "limpo"),
    ("HMACG (Hosp Mil Área Campo Grande)", "Campo Grande - MS", ClassificacaoCOEB.SAUDE, 64.0, False, "limpo"),
    ("HGeRJ (Hosp Geral Vila Militar)", "Vila Militar - RJ", ClassificacaoCOEB.SAUDE, 63.0, False, "limpo"),
    ("HGeS (Hosp Geral Salvador)", "Salvador - BA", ClassificacaoCOEB.SAUDE, 56.0, False, "folha"),
    ("HGeF (Hosp Geral Fortaleza)", "Fortaleza - CE", ClassificacaoCOEB.SAUDE, 58.0, False, "limpo"),
    ("HGeC (Hosp Geral Curitiba)", "Curitiba - PR", ClassificacaoCOEB.SAUDE, 61.0, False, "limpo"),
    ("HGeJF (Hosp Geral Juiz de Fora)", "Juiz de Fora - MG", ClassificacaoCOEB.SAUDE, 59.0, False, "limpo"),
    ("HGeBE (Hosp Geral Belém)", "Belém - PA", ClassificacaoCOEB.SAUDE, 60.0, False, "limpo"),
    ("HGeSM (Hosp Geral Santa Maria)", "Santa Maria - RS", ClassificacaoCOEB.SAUDE, 62.0, False, "limpo"),
    ("HGuJP (Hosp Guarnição João Pessoa)", "João Pessoa - PB", ClassificacaoCOEB.SAUDE, 58.0, False, "limpo"),
    ("HGuTab (Hosp Guarnição Tabatinga)", "Tabatinga - AM", ClassificacaoCOEB.SAUDE, 61.0, False, "limpo"),
    ("HGuSGC (Hosp Guarnição S G Cachoeira)", "São Gabriel da Cachoeira - AM", ClassificacaoCOEB.SAUDE, 60.0, False, "limpo"),
    ("HGuPV (Hosp Guarnição Porto Velho)", "Porto Velho - RO", ClassificacaoCOEB.SAUDE, 59.0, False, "limpo"),
    ("HGuMa (Hosp Guarnição Marabá)", "Marabá - PA", ClassificacaoCOEB.SAUDE, 58.0, False, "limpo"),
    ("HGuN (Hosp Guarnição Natal)", "Natal - RN", ClassificacaoCOEB.SAUDE, 57.0, False, "limpo"),
    ("HGuF (Hosp Guarnição Florianópolis)", "Florianópolis - SC", ClassificacaoCOEB.SAUDE, 59.0, False, "limpo"),
    ("HGuA (Hosp Guarnição Alegrete)", "Alegrete - RS", ClassificacaoCOEB.SAUDE, 57.0, False, "limpo"),
    ("HGuBa (Hosp Guarnição Bagé)", "Bagé - RS", ClassificacaoCOEB.SAUDE, 56.0, False, "limpo"),
    ("HGuS (Hosp Guarnição Santiago)", "Santiago - RS", ClassificacaoCOEB.SAUDE, 56.0, False, "limpo"),
    ("HGuSA (Hosp Guarnição Santo Ângelo)", "Santo Ângelo - RS", ClassificacaoCOEB.SAUDE, 57.0, False, "limpo"),
    ("PMRJ (Policlínica Militar RJ)", "Rio de Janeiro - RJ", ClassificacaoCOEB.SAUDE, 63.0, False, "limpo"),
    ("PMPV (Policlínica Mil Praia Vermelha)", "Rio de Janeiro - RJ", ClassificacaoCOEB.SAUDE, 62.0, False, "limpo"),
    ("PMN (Policlínica Militar Niterói)", "Niterói - RJ", ClassificacaoCOEB.SAUDE, 59.0, False, "limpo"),
    ("PMPA (Policlínica Mil Porto Alegre)", "Porto Alegre - RS", ClassificacaoCOEB.SAUDE, 60.0, False, "limpo"),
    ("PMCG (Policlínica Mil Campo Grande)", "Campo Grande - MS", ClassificacaoCOEB.SAUDE, 58.0, False, "limpo"),
    ("PMCamp (Policlínica Mil Campinas)", "Campinas - SP", ClassificacaoCOEB.SAUDE, 61.0, False, "limpo"),
    ("OCEx (Odontoclínica Central Ex)", "Rio de Janeiro - RJ", ClassificacaoCOEB.SAUDE, 62.0, False, "limpo"),
    ("IBEx (Instituto Biologia Ex)", "Rio de Janeiro - RJ", ClassificacaoCOEB.SAUDE, 66.0, False, "limpo"),
    ("LQFEx (Lab Químico Farmacêutico Ex)", "Rio de Janeiro - RJ", ClassificacaoCOEB.SAUDE, 65.0, False, "limpo"),
    ("Cia Cmdo 1ª RM", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEC, 24.0, False, "ambos"),
    ("Cia Cmdo 2ª RM", "São Paulo - SP", ClassificacaoCOEB.FEC, 25.0, False, "financeiro"),
    ("Cia Cmdo 3ª RM", "Porto Alegre - RS", ClassificacaoCOEB.FEC, 24.0, False, "folha"),
    ("Cia Cmdo 4ª RM", "Belo Horizonte - MG", ClassificacaoCOEB.FEC, 23.0, False, "limpo"),
    ("Cia Cmdo 5ª RM", "Curitiba - PR", ClassificacaoCOEB.FEC, 26.0, False, "limpo"),
    ("Cia Cmdo 6ª RM", "Salvador - BA", ClassificacaoCOEB.FEC, 21.0, False, "ambos"),
    ("Cia Cmdo 7ª RM", "Recife - PE", ClassificacaoCOEB.FEC, 23.0, False, "folha"),
    ("Cia Cmdo 8ª RM", "Belém - PA", ClassificacaoCOEB.FEC, 24.0, False, "limpo"),
    ("Cia Cmdo 9ª RM", "Campo Grande - MS", ClassificacaoCOEB.FEC, 25.0, False, "limpo"),
    ("Cia Cmdo 10ª RM", "Fortaleza - CE", ClassificacaoCOEB.FEC, 22.0, False, "folha"),
    ("Cia Cmdo 11ª RM", "Brasília - DF", ClassificacaoCOEB.FEC, 27.0, False, "limpo"),
    ("Cia Cmdo 12ª RM", "Manaus - AM", ClassificacaoCOEB.FEC, 26.0, False, "limpo"),
    ("Cia Cmdo CML", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEC, 28.0, False, "limpo"),
    ("Cia Cmdo CMSE", "São Paulo - SP", ClassificacaoCOEB.FEC, 29.0, False, "limpo"),
    ("Cia Cmdo CMS", "Porto Alegre - RS", ClassificacaoCOEB.FEC, 28.0, False, "limpo"),
    ("Cia Cmdo CMNE", "Recife - PE", ClassificacaoCOEB.FEC, 27.0, False, "limpo"),
    ("Cia Cmdo CMO", "Campo Grande - MS", ClassificacaoCOEB.FEC, 28.0, False, "limpo"),
    ("Cia Cmdo CMP", "Brasília - DF", ClassificacaoCOEB.FEC, 30.0, False, "limpo"),
    ("Cia Cmdo CMA", "Manaus - AM", ClassificacaoCOEB.FEC, 29.0, False, "limpo"),
    ("Cia Cmdo CMN", "Belém - PA", ClassificacaoCOEB.FEC, 27.0, False, "limpo"),
    ("3º Esqd C L", "Três Corações - MG", ClassificacaoCOEB.FEC, 26.0, False, "limpo"),
    ("1º Btl Instr (Apoio)", "Resende - RJ", ClassificacaoCOEB.FEC, 33.0, False, "limpo"),
    ("Btl Cmdo Sv AMAN", "Resende - RJ", ClassificacaoCOEB.FEC, 29.0, False, "limpo"),
    ("Btl Cmdo Sv EsSA", "Três Corações - MG", ClassificacaoCOEB.FEC, 28.0, False, "limpo"),
    ("1º Cia Intlg (CML)", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEI, 85.0, True, "limpo"),
    ("2º Cia Intlg (CMSE)", "São Paulo - SP", ClassificacaoCOEB.FEI, 86.0, True, "limpo"),
    ("4º Cia Intlg (CMP)", "Brasília - DF", ClassificacaoCOEB.FEI, 87.0, True, "limpo"),
    ("6º Cia Com", "Cristalina - GO", ClassificacaoCOEB.FEC, 70.0, False, "limpo"),
    ("15º Cia Com Mec", "Cascavel - PR", ClassificacaoCOEB.FEI, 72.0, True, "limpo"),
    ("1ª Cia Eng Cmb Mec", "São Borja - RS", ClassificacaoCOEB.FEI, 58.0, True, "limpo"),
    ("2ª Cia Eng Cmb Mec", "Alegrete - RS", ClassificacaoCOEB.FEI, 64.0, True, "limpo"),
    ("3ª Cia Eng Cmb Mec", "Dom Pedrito - RS", ClassificacaoCOEB.FEI, 63.0, True, "limpo"),
    ("4ª Cia Eng Cmb Mec", "Jardim - MS", ClassificacaoCOEB.FEI, 64.0, True, "limpo"),
    ("10ª Cia Eng Cmb", "São Bento do Una - PE", ClassificacaoCOEB.FEC, 59.0, False, "limpo"),
    ("14ª Cia Eng Cmb", "Tubarão - SC", ClassificacaoCOEB.FEC, 60.0, False, "limpo"),
    ("9ª Bia AAAe (Es)", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEI, 78.0, True, "limpo"),
    ("14º Pel PE", "Florianópolis - SC", ClassificacaoCOEB.FEC, 27.0, False, "limpo"),
    ("38º Pel PE", "Goiânia - GO", ClassificacaoCOEB.FEC, 29.0, False, "limpo"),
    ("10º Pel PE", "Fortaleza - CE", ClassificacaoCOEB.FEC, 26.0, False, "limpo"),
    ("Cmdo 1ª DE", "Vila Militar - RJ", ClassificacaoCOEB.FEC, 64.0, False, "limpo"),
    ("Cmdo 2ª DE", "São Paulo - SP", ClassificacaoCOEB.FEC, 64.0, False, "limpo"),
    ("Cmdo 3ª DE", "Santa Maria - RS", ClassificacaoCOEB.FEC, 65.0, False, "limpo"),
    ("Cmdo 5ª DE", "Curitiba - PR", ClassificacaoCOEB.FEC, 63.0, False, "limpo"),
    ("Cmdo 6ª DE", "Porto Alegre - RS", ClassificacaoCOEB.FEC, 62.0, False, "limpo"),
    ("Cmdo 7ª DE", "Recife - PE", ClassificacaoCOEB.FEC, 60.0, False, "limpo"),
    ("Cia Cmdo 5ª DE", "Curitiba - PR", ClassificacaoCOEB.FEC, 58.0, False, "limpo"),
    ("Cia Cmdo 3ª DE", "Santa Maria - RS", ClassificacaoCOEB.FEC, 60.0, False, "limpo"),
    ("Cia Cmdo 6ª DE", "Porto Alegre - RS", ClassificacaoCOEB.FEC, 57.0, False, "limpo"),
    ("Cia Cmdo 1ª DE", "Vila Militar - RJ", ClassificacaoCOEB.FEC, 59.0, False, "limpo"),
    ("Cia Cmdo 2ª DE", "São Paulo - SP", ClassificacaoCOEB.FEC, 59.0, False, "limpo"),
    ("Cia Cmdo 7ª DE", "Recife - PE", ClassificacaoCOEB.FEC, 55.0, False, "limpo"),
    ("Esqd Cmdo 6ª Bda C Bld", "Santa Maria - RS", ClassificacaoCOEB.FEC, 65.0, False, "limpo"),
    ("Esqd Cmdo 1ª Bda C Mec", "Santiago - RS", ClassificacaoCOEB.FEI, 61.0, True, "limpo"),
    ("Esqd Cmdo 2ª Bda C Mec", "Uruguaiana - RS", ClassificacaoCOEB.FEI, 62.0, True, "limpo"),
    ("Esqd Cmdo 3ª Bda C Mec", "Bagé - RS", ClassificacaoCOEB.FEI, 60.0, True, "limpo"),
    ("Esqd Cmdo 4ª Bda C Mec", "Dourados - MS", ClassificacaoCOEB.FEI, 63.0, True, "limpo"),
    ("Cia Cmdo 13ª Bda Inf Mtz", "Cuiabá - MT", ClassificacaoCOEB.FEI, 58.0, True, "limpo"),
    ("Cia Cmdo 3ª Bda Inf Mec", "Cristalina - GO", ClassificacaoCOEB.FEC, 62.0, False, "limpo"),
    ("Cia Cmdo 4ª Bda Inf L Mth", "Juiz de Fora - MG", ClassificacaoCOEB.FEC, 60.0, False, "limpo"),
    ("Cia Cmdo 7ª Bda Inf Mtz", "Natal - RN", ClassificacaoCOEB.FEC, 57.0, False, "limpo"),
    ("Cia Cmdo 8ª Bda Inf Mtz", "Pelotas - RS", ClassificacaoCOEB.FEC, 58.0, False, "limpo"),
    ("Cia Cmdo GUEs / 9ª Bda Inf Mtz", "Vila Militar - RJ", ClassificacaoCOEB.FEC, 62.0, False, "limpo"),
    ("Cia Cmdo 10ª Bda Inf Mtz", "Recife - PE", ClassificacaoCOEB.FEC, 58.0, False, "limpo"),
    ("Cia Cmdo 14ª Bda Inf Mtz", "Florianópolis - SC", ClassificacaoCOEB.FEC, 59.0, False, "limpo"),
    ("Cmdo 1ª Bda AAAe (Def Antiaérea)", "Guarujá - SP", ClassificacaoCOEB.FEI, 84.0, True, "limpo"),
    ("Bia Cmdo 1ª Bda AAAe", "Guarujá - SP", ClassificacaoCOEB.FEI, 76.0, True, "limpo"),
    ("Cmdo Art Ex (Artilharia Ex)", "Formosa - GO", ClassificacaoCOEB.FEI, 85.0, True, "limpo"),
    ("Cia Cmdo 15ª Bda Inf Mec", "Cascavel - PR", ClassificacaoCOEB.FEI, 64.0, True, "limpo"),
    ("Cia Cmdo 16ª Bda Inf Sl", "Tefé - AM", ClassificacaoCOEB.FEI, 58.0, True, "limpo"),
    ("Cia Cmdo 17ª Bda Inf Sl", "Porto Velho - RO", ClassificacaoCOEB.FEI, 59.0, True, "limpo"),
    ("Cia Cmdo 2ª Bda Inf Sl", "São Gabriel da Cachoeira - AM", ClassificacaoCOEB.FEI, 60.0, True, "limpo"),
    ("Cia Cmdo 1ª Bda Inf Sl", "Boa Vista - RR", ClassificacaoCOEB.FEI, 60.0, True, "limpo"),
    ("Cia Cmdo 22ª Bda Inf Sl", "Macapá - AP", ClassificacaoCOEB.FEI, 56.0, True, "limpo"),
    ("Cia Cmdo 18ª Bda Inf Pan", "Corumbá - MS", ClassificacaoCOEB.FEI, 58.0, True, "limpo"),
    ("18º Btl Trns (Transporte)", "Campo Grande - MS", ClassificacaoCOEB.FEC, 52.0, False, "limpo"),
    ("1º Btl Trns", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEC, 26.0, False, "financeiro"),
    ("2º Btl Trns", "São Paulo - SP", ClassificacaoCOEB.FEC, 27.0, False, "limpo"),
    ("3º Btl Trns", "Porto Alegre - RS", ClassificacaoCOEB.FEC, 25.0, False, "folha"),
    ("CIGE (Centro Intlg Ex)", "Brasília - DF", ClassificacaoCOEB.FEI, 96.0, True, "limpo"),
    ("CDS (Centro Desenv Sist)", "Brasília - DF", ClassificacaoCOEB.FEI, 95.0, True, "limpo"),
    ("CTEx (Centro Tecnol Ex)", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEI, 93.0, True, "limpo"),
    ("CAEx (Campo Provas Marambaia)", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEI, 84.0, True, "limpo"),
    ("CITEx (Centro Integrado Telem)", "Brasília - DF", ClassificacaoCOEB.FEI, 94.0, True, "limpo"),
    ("1º CTA (Centro Telemática)", "Porto Alegre - RS", ClassificacaoCOEB.FEI, 82.0, False, "limpo"),
    ("2º CTA (Centro Telemática)", "São Paulo - SP", ClassificacaoCOEB.FEI, 83.0, False, "limpo"),
    ("3º CTA (Centro Telemática)", "Rio de Janeiro - RJ", ClassificacaoCOEB.FEI, 84.0, False, "limpo"),
    ("4º CTA (Centro Telemática)", "Manaus - AM", ClassificacaoCOEB.FEI, 86.0, True, "limpo"),
    ("5º CTA (Centro Telemática)", "Recife - PE", ClassificacaoCOEB.FEI, 80.0, False, "limpo"),
    ("6º CTA (Centro Telemática)", "Campo Grande - MS", ClassificacaoCOEB.FEI, 81.0, False, "limpo"),
    ("7º CTA (Centro Telemática)", "Brasília - DF", ClassificacaoCOEB.FEI, 88.0, True, "limpo"),
]


def gerar_oms(reset: bool = True) -> int:
    """Popula o banco de dados com todo o catálogo de OMs do Exército Brasileiro."""
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        if reset:
            db.query(SaudeIndicadores).delete()
            db.query(TransparenciaDados).delete()
            db.query(Sislog).delete()
            db.query(Estrategia).delete()
            db.query(Sigpes).delete()
            db.query(PatrimonioUniao).delete()
            db.query(DoutrinaTecnologia).delete()
            db.query(OM).delete()
            db.commit()

        contador_cidade: Dict[str, int] = {}

        for idx, (sigla, guarnicao, coeb, c4isr, a2ad, perfil_anomalia) in enumerate(CATALOGO_OMS, start=1):
            base_lat, base_lon, dist_fronteira, area_urbana, mult_spu = GUARNICOES[guarnicao]
            ocorrencia = contador_cidade.get(guarnicao, 0)
            contador_cidade[guarnicao] = ocorrencia + 1

            # Pequeno deslocamento em espiral para OMs na mesma guarnição não se sobreporem no mapa
            angulo = ocorrencia * 0.9
            raio = 0.008 * (ocorrencia % 6)
            lat = round(base_lat + (raio * (1 if ocorrencia % 2 == 0 else -1) * (0.5 + (angulo % 1))), 6)
            lon = round(base_lon + (raio * (-1 if ocorrencia % 3 == 0 else 1) * (0.4 + (angulo % 1))), 6)

            # Perfil de efetivo, custeio, prontidão e valor imobiliário coerente com COEB
            if sigla.startswith("1º BInt"):
                ef_decl, ef_fim = 185, 165
                valor_spu = 42_000_000.0
                custeio_decl = 18_500_000.0
                acionamentos, disponibilidade = 48, 96.5
            elif sigla.startswith("2º BG"):
                ef_decl, ef_fim = 780, 320
                valor_spu = 485_000_000.0
                custeio_decl = 34_000_000.0
                acionamentos, disponibilidade = 1, 58.0
            elif coeb == ClassificacaoCOEB.FEP:
                # 1ª prioridade COEB: maior recompletamento de pessoal, material, sistemas e prontidão
                is_tech_niche = any(k in sigla for k in ("BInt", "ComDCiber", "BGE", "CIGE", "CDS", "CITEx", "CTA", "CTEx", "Cia Intlg"))
                ef_decl = random.randint(180, 320) if is_tech_niche else random.randint(520, 780)
                ef_fim = int(ef_decl * random.uniform(0.82, 0.92))
                valor_spu = round(random.uniform(42_000_000, 125_000_000) * mult_spu, 2)
                custeio_decl = round(ef_decl * random.uniform(55_000, 98_000), 2)
                acionamentos = random.randint(24, 58)
                disponibilidade = 76.0 if perfil_anomalia == "prontidao" else round(random.uniform(88.0, 98.5), 1)
            elif coeb == ClassificacaoCOEB.FEI:
                # 2º plano relativo às FEP em pessoal e material, debruçadas na fronteira / multidomínio
                is_pef = "PEF" in sigla or "Cia" in sigla
                is_tech_niche = any(k in sigla for k in ("BInt", "ComDCiber", "BGE", "CIGE", "CDS", "CITEx", "CTA", "CTEx", "Cia Intlg"))
                ef_decl = random.randint(95, 220) if is_pef else (random.randint(180, 320) if is_tech_niche else random.randint(360, 560))
                ef_fim = int(ef_decl * (random.uniform(0.82, 0.90) if is_tech_niche else random.uniform(0.64, 0.77)))
                valor_spu = round(random.uniform(12_000_000, 52_000_000) * mult_spu, 2)
                custeio_decl = round(ef_decl * random.uniform(44_000, 70_000), 2)
                acionamentos = random.randint(24, 48) if is_tech_niche else random.randint(14, 32)
                disponibilidade = (
                    69.0
                    if perfil_anomalia == "prontidao"
                    else (round(random.uniform(86.0, 94.0), 1) if is_tech_niche else round(random.uniform(79.0, 87.5), 1))
                )
            elif eh_om_saude(sigla):
                # OMS: vocação assistencial (FUSEx) + núcleo de Sustentação Sanitária (não combatente FEP)
                ef_decl = random.randint(420, 920)
                ef_fim = int(ef_decl * random.uniform(0.72, 0.84))
                valor_spu = round(random.uniform(95_000_000, 240_000_000) * mult_spu, 2)
                custeio_decl = round(ef_decl * random.uniform(52_000, 82_000), 2)
                acionamentos = random.randint(2, 6)
                disponibilidade = round(random.uniform(80.0, 93.0), 1)
            elif eh_om_ensino(sigla):
                # Capacidade Institucional (Ensino / Formação — COEB 5.6.1.4)
                ef_decl = random.randint(540, 1100)
                ef_fim = int(ef_decl * random.uniform(0.65, 0.78))
                valor_spu = round(random.uniform(110_000_000, 260_000_000) * mult_spu, 2)
                custeio_decl = round(ef_decl * random.uniform(48_000, 74_000), 2)
                acionamentos = random.randint(2, 5)
                disponibilidade = round(random.uniform(82.0, 92.0), 1)
            else:  # FEC (Reserva Estratégica / Combate / Litoral vs. Guarda / Apoio Territorial)
                local_eb = inferir_localizacao_militar(sigla, endereco)
                sigla_up = sigla.upper()
                is_de_c2 = bool(re.search(r"\bCMDO\b.*\bDE\b", sigla_up))
                is_fec_comb_ou_apoio = (
                    local_eb["brigada"] in BRIGADAS_FEC_COMBATE_DE
                    or is_de_c2
                    or any(k in sigla_up for k in ("BE CMB", "BEC", "B FV", "ARSENAL", "BLOG"))
                )
                ef_decl = random.randint(360, 820)
                if is_fec_comb_ou_apoio and perfil_anomalia == "limpo":
                    ef_fim = int(ef_decl * random.uniform(0.60, 0.72))
                    acionamentos = random.randint(3, 6)
                    disponibilidade = round(random.uniform(72.0, 84.0), 1)
                else:
                    ef_fim = int(ef_decl * random.uniform(0.32, 0.48))
                    acionamentos = random.randint(0, 4)
                    disponibilidade = round(random.uniform(50.0, 76.0), 1)
                valor_spu = round(random.uniform(85_000_000, 210_000_000) * mult_spu, 2)
                custeio_decl = round(ef_decl * random.uniform(42_000, 68_000), 2)

            # Aplica divergências CGU/SIGPES conforme perfil de auditoria
            if perfil_anomalia in ("folha", "ambos"):
                cpfs_ativos = int(ef_decl * random.uniform(0.80, 0.89))
                cpfs_reserva = random.randint(110, 260)
            else:
                cpfs_ativos = max(1, ef_decl - random.randint(0, 3))
                cpfs_reserva = random.randint(6, 45)

            if perfil_anomalia in ("financeiro", "ambos"):
                empenhado_cgu = round(custeio_decl * random.uniform(1.09, 1.18), 2)
            else:
                empenhado_cgu = round(custeio_decl * random.uniform(0.985, 1.02), 2)

            uasg = f"160{500 + idx:03d}"
            rip = f"RIP-{7000 + idx:04d}-SPU"
            cnpj = fake.cnpj()
            cep = fake.postcode()
            endereco = f"{fake.street_address()}, {guarnicao}"

            om = OM(
                codigo_uasg=uasg,
                rip_spu=rip,
                cnpj_ug=cnpj,
                sigla=sigla,
                cep=cep,
                endereco=endereco,
                latitude=lat,
                longitude=lon,
                alertas_auditoria=[],
            )
            db.add(om)
            db.flush()

            db.add(
                DoutrinaTecnologia(
                    id_om=om.id_om,
                    classificacao_coeb=coeb,
                    indice_tecnologia_c4isr=c4isr,
                    papel_a2ad=a2ad,
                )
            )
            db.add(
                PatrimonioUniao(
                    id_om=om.id_om,
                    rip_spu=rip,
                    valor_imovel_brl=valor_spu,
                )
            )
            db.add(
                Sigpes(
                    id_om=om.id_om,
                    efetivo_total_declarado=ef_decl,
                    efetivo_fim=ef_fim,
                    custeio_declarado_brl=custeio_decl,
                )
            )
            db.add(
                TransparenciaDados(
                    id_om=om.id_om,
                    ano_mes="2026-10",
                    total_empenhado=empenhado_cgu,
                    cpfs_ativos=cpfs_ativos,
                    cpfs_reserva=cpfs_reserva,
                )
            )
            db.add(
                Sislog(
                    id_om=om.id_om,
                    acionamentos_reais_36m=acionamentos,
                    taxa_disponibilidade=disponibilidade,
                )
            )
            db.add(
                Estrategia(
                    id_om=om.id_om,
                    dist_fronteira_km=dist_fronteira,
                    area_urbana=area_urbana,
                )
            )
            if coeb == ClassificacaoCOEB.SAUDE or eh_om_saude(sigla):
                sigla_u = sigla.upper()
                is_policlinica = any(k in sigla_u for k in ("POLICL", "PMRJ", "PMPV", "PMN", "PMPA", "PMCG", "PMCAMP", "OCEX", "IBEX", "LQFEX"))
                is_hce_hma = "HCE" in sigla_u or "HMA" in sigla_u
                is_hge = "HGE" in sigla_u
                if is_hce_hma:
                    leitos = random.randint(180, 420) if "HCE" in sigla_u else random.randint(130, 260)
                    benef = random.randint(35_000, 92_000)
                    atend = random.randint(115_000, 240_000)
                    ocup = round(random.uniform(76.0, 88.0), 1)
                    resol = round(random.uniform(82.0, 92.0), 1)
                elif is_hge:
                    leitos = random.randint(75, 145)
                    benef = random.randint(18_000, 42_000)
                    atend = random.randint(62_000, 118_000)
                    ocup = round(random.uniform(73.0, 85.0), 1)
                    resol = round(random.uniform(76.0, 87.0), 1)
                elif is_policlinica:
                    leitos = 0
                    benef = random.randint(14_000, 38_000)
                    atend = random.randint(45_000, 95_000)
                    ocup = round(random.uniform(78.0, 90.0), 1)  # Utilização de agenda ambulatorial
                    resol = round(random.uniform(80.0, 91.0), 1)
                else:  # HGu (Tabatinga, SGC, João Pessoa, etc.)
                    leitos = random.randint(28, 68)
                    benef = random.randint(5_500, 19_000)
                    atend = random.randint(26_000, 58_000)
                    ocup = round(random.uniform(70.0, 84.0), 1)
                    resol = round(random.uniform(74.0, 86.0), 1)

                custo_unit = round(empenhado_cgu / max(atend, 1), 2)
                nota_custo = max(35.0, min(100.0, 100.0 - ((custo_unit - 180.0) / 360.0) * 65.0))
                ef_hosp = (
                    0.30 * nota_custo
                    + 0.30 * resol
                    + 0.20 * ocup
                    + 0.20 * (0.5 * c4isr + 0.5 * disponibilidade)
                )
                if perfil_anomalia != "limpo":
                    ef_hosp *= 0.85
                db.add(
                    SaudeIndicadores(
                        id_om=om.id_om,
                        atendimentos_ano=atend,
                        beneficiarios_fusex=benef,
                        leitos_operacionais=leitos,
                        taxa_ocupacao_leitos_pct=ocup,
                        custo_medio_atendimento_brl=custo_unit,
                        resolutividade_propria_pct=resol,
                        indice_eficiencia_hospitalar=round(min(100.0, max(0.0, ef_hosp)), 2),
                    )
                )

        db.commit()
        return len(CATALOGO_OMS)
    finally:
        db.close()


if __name__ == "__main__":
    total = gerar_oms(reset=True)
    print(f"[SIGA-F4] {total} OMs do Exército Brasileiro geradas e persistidas com sucesso.")
