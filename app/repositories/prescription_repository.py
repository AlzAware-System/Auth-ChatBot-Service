"""Prescription Repository — Data access for MPrescription model."""

from app import db
from app.models.prescription import MPrescription
from app.models.medicine import Medicine


def find_medicine_by_id(medicine_id):
    return Medicine.query.filter_by(medicine_id=medicine_id).first()


def find_prescription(patient_id: str, medicine_id):
    return MPrescription.query.filter_by(patient_id=patient_id, medicine_id=medicine_id).first()


def create_prescription(**kwargs):
    prescription = MPrescription(**kwargs)
    db.session.add(prescription)
    return prescription


def commit():
    db.session.commit()
