"""Rotina agendada (APScheduler) para sincronização noturna CGU/SPU e recálculo JEV."""

import logging
import sys
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.core.motor_jev import MotorIVE
from backend.models.database import SessionLocal
from backend.models.schemas import OM
from backend.services.cgu_sync import TransparenciaSyncService
from backend.services.spu_sync import PatrimonioSyncService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("siga_f4.scheduler")


def executar_rotina_noturna() -> None:
    """Sincroniza dados CGU/SPU e recalcula alertas e diagnósticos JEV para todas as OMs."""
    logger.info("Iniciando sincronização noturna SIGA-F4 (CGU / SPU / Motor JEV)...")
    db = SessionLocal()
    cgu_service = TransparenciaSyncService()
    spu_service = PatrimonioSyncService()
    motor = MotorIVE()

    try:
        oms = db.query(OM).all()
        for om in oms:
            cgu_service.sincronizar_om(db, om.id_om)
            spu_service.sincronizar_om(db, om.id_om)

        diagnosticos = motor.diagnosticar_todas(db, persistir_alertas=True)
        logger.info("Rotina concluída com sucesso. %d OMs auditadas e recalculadas.", len(diagnosticos))
    finally:
        db.close()


if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(executar_rotina_noturna, trigger="cron", hour=2, minute=0)
    logger.info("Scheduler SIGA-F4 ativo (execução diária às 02:00 BRT).")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler SIGA-F4 encerrado.")
