"""Matching Game Repository — Data access for MatchingItem and MatchingGameResult models."""

from app import db
from app.models.matching_item import MatchingItem
from app.models.matching_game_result import MatchingGameResult


# ---------------------------------------------------------------------------
# MatchingItem
# ---------------------------------------------------------------------------

def create_matching_item(**kwargs):
    item = MatchingItem(**kwargs)
    db.session.add(item)
    return item


def find_matching_item_by_id(item_id: str):
    return MatchingItem.query.filter_by(item_id=item_id).first()


def find_items_by_patient(patient_id: str):
    return MatchingItem.query.filter_by(patient_id=patient_id).all()


def find_items_by_caregiver(caregiver_id: str, patient_id: str | None = None):
    query = MatchingItem.query.filter_by(caregiver_id=caregiver_id)
    if patient_id:
        query = query.filter_by(patient_id=patient_id)
    return query.order_by(MatchingItem.created_at.desc()).all()


def delete_matching_item(item):
    db.session.delete(item)


# ---------------------------------------------------------------------------
# MatchingGameResult
# ---------------------------------------------------------------------------

def create_game_result(**kwargs):
    result = MatchingGameResult(**kwargs)
    db.session.add(result)
    return result


def find_game_results_by_patient(patient_id: str):
    return (
        MatchingGameResult.query
        .filter_by(patient_id=patient_id)
        .order_by(MatchingGameResult.played_at.desc())
        .all()
    )


def commit():
    db.session.commit()
