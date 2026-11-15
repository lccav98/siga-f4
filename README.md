# SIGA-F4 (Sistema de Governança Algorítmica de Força)

O **SIGA-F4** é um motor de prescrição estratégica e diagnóstico preditivo para o Exército Brasileiro. Ele aplica o framework **JEV (Julgamento, Estratégia e Validação)** para calcular o Índice de Valor Estratégico (IVE) das Organizações Militares (OMs), cruzando dados operacionais internos com auditoria financeira pública.

## 🎯 Objetivos Doutrinários
- **Adequação ao COEB:** Classificação ponderada entre Forças de Emprego Imediato (FEI), Pronto (FEP) e Condicionado (FEC).
- **Racionalização (Política de Transformação):** Cálculo do "Custo de Oportunidade Imobiliária" integrando dados da SPU (Secretaria do Patrimônio da União) para identificar OMs passíveis de desativação e alienação.
- **Força 4.0:** Digital Twins para simulação de evolução tecnológica (C4ISR) e transferência de capital.
- **Auditoria de Transparência:** Sincronismo com a CGU via UASG para auditar "Efetivo Fantasma" (isolando CPFs de Inativos/Pensionistas do cálculo de prontidão) e Burn Rate.

## 🛠️ Stack Tecnológico
- **Backend:** Python, FastAPI, SQLAlchemy
- **Database:** PostgreSQL (Deploy via Railway)
- **Data/Math:** Pandas, Geopy
- **Frontend:** Streamlit, Folium (Deploy via Vercel)
- **Automação:** APScheduler, HTTPX (APIs CGU/SPU)

## 🚀 Como rodar o MVP localmente (Windows/PowerShell)

1. **Clone o repositório e crie o ambiente virtual:**
   ```powershell
   git clone https://github.com/lccav98/siga-f4.git
   cd siga-f4
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. **Instale as dependências:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Gere os dados de teste (Faker):**
   ```powershell
   python scripts/gerador_mock.py
   ```

4. **Inicie a API (Backend):**
   ```powershell
   uvicorn backend.api.main:app --reload
   ```

5. **Inicie o Dashboard Executivo (Frontend) em outro terminal:**
   ```powershell
   streamlit run frontend/app.py
   ```
