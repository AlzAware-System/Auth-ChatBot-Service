"""System Log Repository — Data access for SystemLog model."""

from sqlalchemy import func
from app.models.system_log import SystemLog


def count_all_logs():
    return SystemLog.query.count()


def find_logs(event_type: str | None = None, limit: int = 500):
    query = SystemLog.query
    if event_type:
        query = query.filter(func.lower(SystemLog.event_type) == event_type)
    return query.order_by(SystemLog.created_at.desc()).limit(limit).all()


def find_patient_login_logs(limit: int = 500):
    return (
        SystemLog.query
        .filter(func.lower(SystemLog.event_type) == 'patient_login')
        .order_by(SystemLog.created_at.desc())
        .limit(limit)
        .all()
    )


def find_new_patient_logs(limit: int = 500):
    return (
        SystemLog.query
        .filter(func.lower(SystemLog.event_type).in_(['patient_registered', 'patient_created']))
        .order_by(SystemLog.created_at.desc())
        .limit(limit)
        .all()
    )
