"""Modelagem SQLAlchemy das 7 tabelas do SIGA-F4 (COEB / Força 4.0 / JEV)."""

import enum
from sqlalchemy import (
    Boolean,
    Column,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from backend.models.database import Base


class ClassificacaoCOEB(str, enum.Enum):
    """Classificação doutrinária conforme o COEB e a Política de Transformação (EB10-P-01.031)."""

    FEI = "FEI"  # Força de Emprego Imediato (faixa de fronteira / resposta inicial)
    FEP = "FEP"  # Força de Emprego de Prontidão (poder de combate ofensivo / 1ª prioridade)
    FEC = "FEC"  # Força de Emprego Continuado (dissuasão, presença, defesa territorial e mobilização)


JSONBCompat = JSON().with_variant(JSONB, "postgresql")


class OM(Base):
    """1. Cadastro central da Organização Militar (tb_om)."""

    __tablename__ = "tb_om"

    id_om = Column(Integer, primary_key=True, index=True, autoincrement=True)
    codigo_uasg = Column(String(10), unique=True, nullable=False, index=True)
    rip_spu = Column(String(20), unique=True, nullable=False, index=True)
    cnpj_ug = Column(String(18), unique=True, nullable=False)
    sigla = Column(String(40), nullable=False, index=True)
    cep = Column(String(10), nullable=False)
    endereco = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    alertas_auditoria = Column(JSONBCompat, nullable=False, default=list)

    doutrina_tecnologia = relationship(
        "DoutrinaTecnologia", back_populates="om", uselist=False, cascade="all, delete-orphan"
    )
    patrimonio_uniao = relationship(
        "PatrimonioUniao", back_populates="om", uselist=False, cascade="all, delete-orphan"
    )
    sigpes = relationship(
        "Sigpes", back_populates="om", uselist=False, cascade="all, delete-orphan"
    )
    transparencia_dados = relationship(
        "TransparenciaDados", back_populates="om", cascade="all, delete-orphan"
    )
    sislog = relationship(
        "Sislog", back_populates="om", uselist=False, cascade="all, delete-orphan"
    )
    estrategia = relationship(
        "Estrategia", back_populates="om", uselist=False, cascade="all, delete-orphan"
    )


class DoutrinaTecnologia(Base):
    """2. Enquadramento COEB, maturidade tecnológica C4ISR e papel A2/AD (tb_doutrina_tecnologia)."""

    __tablename__ = "tb_doutrina_tecnologia"

    id_om = Column(Integer, ForeignKey("tb_om.id_om", ondelete="CASCADE"), primary_key=True)
    classificacao_coeb = Column(Enum(ClassificacaoCOEB, name="coeb_enum"), nullable=False)
    indice_tecnologia_c4isr = Column(Float, nullable=False, default=0.0)  # Escala 0 a 100
    papel_a2ad = Column(Boolean, nullable=False, default=False)

    om = relationship("OM", back_populates="doutrina_tecnologia")


class PatrimonioUniao(Base):
    """3. Dados patrimoniais da SPU para Custo de Oportunidade Imobiliária (tb_patrimonio_uniao)."""

    __tablename__ = "tb_patrimonio_uniao"

    id_om = Column(Integer, ForeignKey("tb_om.id_om", ondelete="CASCADE"), primary_key=True)
    rip_spu = Column(String(20), nullable=False, index=True)
    valor_imovel_brl = Column(Float, nullable=False, default=0.0)

    om = relationship("OM", back_populates="patrimonio_uniao")


class Sigpes(Base):
    """4. Efetivo e custeio declarados internamente via SIGPES (tb_sigpes)."""

    __tablename__ = "tb_sigpes"

    id_om = Column(Integer, ForeignKey("tb_om.id_om", ondelete="CASCADE"), primary_key=True)
    efetivo_total_declarado = Column(Integer, nullable=False, default=0)
    efetivo_fim = Column(Integer, nullable=False, default=0)
    custeio_declarado_brl = Column(Float, nullable=False, default=0.0)

    om = relationship("OM", back_populates="sigpes")


class TransparenciaDados(Base):
    """5. Dados abertos auditados da CGU / Portal da Transparência (tb_transparencia_dados)."""

    __tablename__ = "tb_transparencia_dados"

    id_registro = Column(Integer, primary_key=True, autoincrement=True)
    id_om = Column(Integer, ForeignKey("tb_om.id_om", ondelete="CASCADE"), nullable=False, index=True)
    ano_mes = Column(String(7), nullable=False, index=True)  # Formato YYYY-MM
    total_empenhado = Column(Float, nullable=False, default=0.0)
    cpfs_ativos = Column(Integer, nullable=False, default=0)
    cpfs_reserva = Column(Integer, nullable=False, default=0)

    om = relationship("OM", back_populates="transparencia_dados")


class Sislog(Base):
    """6. Prontidão logística e emprego real nos últimos 36 meses (tb_sislog)."""

    __tablename__ = "tb_sislog"

    id_om = Column(Integer, ForeignKey("tb_om.id_om", ondelete="CASCADE"), primary_key=True)
    acionamentos_reais_36m = Column(Integer, nullable=False, default=0)
    taxa_disponibilidade = Column(Float, nullable=False, default=0.0)  # Percentual 0 a 100

    om = relationship("OM", back_populates="sislog")


class Estrategia(Base):
    """7. Posicionamento geoestratégico e área de atuação (tb_estrategia)."""

    __tablename__ = "tb_estrategia"

    id_om = Column(Integer, ForeignKey("tb_om.id_om", ondelete="CASCADE"), primary_key=True)
    dist_fronteira_km = Column(Float, nullable=False, default=0.0)
    area_urbana = Column(Boolean, nullable=False, default=True)

    om = relationship("OM", back_populates="estrategia")
