"""Aplicação principal FastAPI do SIGA-F4."""

from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router as siga_router
from backend.models.database import Base, engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Garante criação das tabelas no startup da aplicação."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="SIGA-F4 API",
    description=(
        "Sistema de Governança Algorítmica de Força — Motor JEV para diagnóstico "
        "doutrinário (COEB / Força 4.0), auditoria CGU/SPU e Digital Twin."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(siga_router)


@app.get("/health", tags=["Sistema"])
def health_check() -> Dict[str, str]:
    """Verificação de integridade da API."""
    return {"status": "ok", "servico": "SIGA-F4"}
