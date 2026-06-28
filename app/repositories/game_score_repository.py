"""Game Score Repository — Data access for GameScore model."""

from app import db
from app.models.game_score import GameScore


def create_game_score(**kwargs):
    game_score = GameScore(**kwargs)
    db.session.add(game_score)
    return game_score


def find_scores_by_patient(patient_id: str):
    return (
        GameScore.query
        .filter_by(patient_id=patient_id)
        .order_by(GameScore.created_at.desc())
        .all()
    )


def commit():
    db.session.commit()
