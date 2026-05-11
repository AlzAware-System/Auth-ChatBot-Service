from datetime import datetime

from app import db


class MatchingGameResult(db.Model):
    """Stores the result of a single matching-game session played by a patient."""

    __tablename__ = 'Matching_Game_Results'
    __table_args__ = {'schema': 'dbo'}

    result_id = db.Column(db.String(50), primary_key=True)
    patient_id = db.Column(
        db.String(50),
        db.ForeignKey('dbo.Patients.patient_id'),
        nullable=False,
    )
    total_items = db.Column(db.Integer, nullable=False)
    correct_count = db.Column(db.Integer, nullable=False)
    wrong_count = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Integer, nullable=False)  # percentage 0-100
    played_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    patient = db.relationship(
        'Patient',
        backref=db.backref('matching_game_results', lazy=True, order_by='desc(MatchingGameResult.played_at)'),
    )
