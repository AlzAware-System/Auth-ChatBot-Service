from datetime import datetime

from app import db


class MatchingItem(db.Model):
    """Stores an image+name pair uploaded by a caregiver for the matching game."""

    __tablename__ = 'Matching_Items'
    __table_args__ = {'schema': 'dbo'}

    item_id = db.Column(db.String(50), primary_key=True)
    patient_id = db.Column(
        db.String(50),
        db.ForeignKey('dbo.Patients.patient_id'),
        nullable=False,
    )
    caregiver_id = db.Column(
        db.String(50),
        db.ForeignKey('dbo.Care_givers.care_giver_id'),
        nullable=False,
    )
    person_name = db.Column(db.String(255), nullable=False)
    image_filename = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    patient = db.relationship('Patient', backref=db.backref('matching_items', lazy=True))
    caregiver = db.relationship('CareGiver', backref=db.backref('matching_items', lazy=True))
