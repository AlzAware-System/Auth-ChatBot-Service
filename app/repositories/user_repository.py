"""User Repository — Data access for Patient, Doctor, CareGiver, Admin models."""

from sqlalchemy import or_, func
from app import db
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.caregiver import CareGiver
from app.models.admin import Admin


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def model_by_role(role: str):
    role = (role or '').strip().lower()
    if role == 'patient':
        return Patient
    if role == 'doctor':
        return Doctor
    if role == 'caregiver':
        return CareGiver
    if role == 'admin':
        return Admin
    return None


def model_for_role(role: str):
    """Same as model_by_role but excludes Admin (for admin controller)."""
    role = (role or '').strip().lower()
    if role == 'patient':
        return Patient
    if role == 'doctor':
        return Doctor
    if role == 'caregiver':
        return CareGiver
    return None


def commit():
    db.session.commit()


def rollback():
    db.session.rollback()


def add(entity):
    db.session.add(entity)


def delete(entity):
    db.session.delete(entity)


# ---------------------------------------------------------------------------
# Patient
# ---------------------------------------------------------------------------

def find_patient_by_id(patient_id: str):
    return Patient.query.filter_by(patient_id=patient_id).first()


def find_patient_by_email(email: str):
    return Patient.query.filter(func.lower(Patient.email) == email).first()


def find_patient_by_identifier(identifier_lower: str, identifier: str):
    return Patient.query.filter(
        or_(func.lower(Patient.email) == identifier_lower, Patient.name == identifier)
    ).first()


def count_active_patients():
    return Patient.query.filter_by(active=True).count()


def find_all_active_patients():
    return Patient.query.filter_by(active=True).all()


def create_patient(**kwargs):
    patient = Patient(**kwargs)
    db.session.add(patient)
    return patient


# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------

def find_doctor_by_id(doctor_id: str):
    return Doctor.query.filter_by(doctor_id=doctor_id).first()


def find_doctor_by_email(email: str):
    return Doctor.query.filter(func.lower(Doctor.email) == email).first()


def find_doctor_by_identifier(identifier_lower: str, identifier: str):
    return Doctor.query.filter(
        or_(func.lower(Doctor.email) == identifier_lower, Doctor.name == identifier)
    ).first()


def count_active_doctors():
    return Doctor.query.filter_by(active=True).count()


def find_all_active_doctors():
    return Doctor.query.filter_by(active=True).all()


def create_doctor(**kwargs):
    doctor = Doctor(**kwargs)
    db.session.add(doctor)
    return doctor


# ---------------------------------------------------------------------------
# CareGiver
# ---------------------------------------------------------------------------

def find_caregiver_by_id(care_giver_id: str):
    return CareGiver.query.filter_by(care_giver_id=care_giver_id).first()


def find_caregiver_by_email(email: str):
    return CareGiver.query.filter(func.lower(CareGiver.email) == email).first()


def find_caregiver_by_identifier(identifier_lower: str, identifier: str):
    return CareGiver.query.filter(
        or_(func.lower(CareGiver.email) == identifier_lower, CareGiver.name == identifier)
    ).first()


def count_active_caregivers():
    return CareGiver.query.filter_by(active=True).count()


def find_all_active_caregivers():
    return CareGiver.query.filter_by(active=True).all()


def create_caregiver(**kwargs):
    caregiver = CareGiver(**kwargs)
    db.session.add(caregiver)
    return caregiver


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

def find_admin_by_id(admin_id: str):
    return Admin.query.filter_by(admin_id=admin_id).first()


def find_admin_by_email(email: str):
    return Admin.query.filter(func.lower(Admin.email) == email).first()


def find_admin_by_identifier(identifier_lower: str, identifier: str):
    return Admin.query.filter(
        or_(func.lower(Admin.email) == identifier_lower, Admin.name == identifier)
    ).first()


def count_active_admins():
    return Admin.query.filter_by(active=True).count()


# ---------------------------------------------------------------------------
# Cross-table email check
# ---------------------------------------------------------------------------

def email_exists_in_any_table(email: str):
    """Returns True if the email exists in any user table."""
    if Patient.query.filter(func.lower(Patient.email) == email).first():
        return True
    if Doctor.query.filter(func.lower(Doctor.email) == email).first():
        return True
    if CareGiver.query.filter(func.lower(CareGiver.email) == email).first():
        return True
    if Admin.query.filter(func.lower(Admin.email) == email).first():
        return True
    return False


def email_exists_cross_table_for_update(new_email: str, role: str, user_id: str):
    """Check for email duplicates across ALL tables for admin email update.
    Returns (is_duplicate: bool, error_message: str | None)."""
    if (Patient.query.filter(func.lower(Patient.email) == new_email).first() and role != 'patient') or \
       (Doctor.query.filter(func.lower(Doctor.email) == new_email).first() and role != 'doctor') or \
       (CareGiver.query.filter(func.lower(CareGiver.email) == new_email).first() and role != 'caregiver') or \
       (Admin.query.filter(func.lower(Admin.email) == new_email).first()):

        # If it exists in the SAME table, ensure it's the exact same user
        model = model_for_role(role)
        duplicate = model.query.filter(func.lower(model.email) == new_email).first()
        if duplicate:
            same_id = getattr(duplicate, 'patient_id', None) == user_id or \
                      getattr(duplicate, 'doctor_id', None) == user_id or \
                      getattr(duplicate, 'care_giver_id', None) == user_id
            if not same_id:
                return True, 'Email already exists'
        else:
            return True, 'Email already exists in another role'

    return False, None


# ---------------------------------------------------------------------------
# Password reset token queries
# ---------------------------------------------------------------------------

def find_user_by_reset_token(hashed_token: str, now_utc):
    """Search all tables for a user with a valid (non-expired) reset token."""
    user_obj = Patient.query.filter(
        Patient.password_reset_token == hashed_token,
        Patient.password_reset_expires > now_utc,
    ).first()
    if user_obj:
        return user_obj, 'patient'

    user_obj = Doctor.query.filter(
        Doctor.password_reset_token == hashed_token,
        Doctor.password_reset_expires > now_utc,
    ).first()
    if user_obj:
        return user_obj, 'doctor'

    user_obj = CareGiver.query.filter(
        CareGiver.password_reset_token == hashed_token,
        CareGiver.password_reset_expires > now_utc,
    ).first()
    if user_obj:
        return user_obj, 'caregiver'

    user_obj = Admin.query.filter(
        Admin.password_reset_token == hashed_token,
        Admin.password_reset_expires > now_utc,
    ).first()
    if user_obj:
        return user_obj, 'admin'

    return None, None


# ---------------------------------------------------------------------------
# Resolve user by email (with optional role)
# ---------------------------------------------------------------------------

def resolve_user_by_email(email: str, role: str | None):
    """Find user by email across tables, optionally limited to a specific role.
    Returns (user_obj, resolved_role) or (None, None).
    Raises ValueError if multiple matches found without role."""
    if role:
        model = model_by_role(role)
        if not model:
            raise ValueError('Invalid role. Allowed: patient, doctor, caregiver, admin')
        user_obj = model.query.filter(func.lower(model.email) == email).first()
        return user_obj, role

    matches = []
    patient = Patient.query.filter(func.lower(Patient.email) == email).first()
    if patient:
        matches.append((patient, 'patient'))
    doctor = Doctor.query.filter(func.lower(Doctor.email) == email).first()
    if doctor:
        matches.append((doctor, 'doctor'))
    caregiver = CareGiver.query.filter(func.lower(CareGiver.email) == email).first()
    if caregiver:
        matches.append((caregiver, 'caregiver'))
    admin = Admin.query.filter(func.lower(Admin.email) == email).first()
    if admin:
        matches.append((admin, 'admin'))

    if len(matches) > 1:
        raise ValueError('Email exists in multiple accounts; provide role (patient/doctor/caregiver/admin)')
    if len(matches) == 1:
        return matches[0]
    return None, None


# ---------------------------------------------------------------------------
# Fetch user by role + id (for admin controller)
# ---------------------------------------------------------------------------

def fetch_user_by_role_and_id(role: str, user_id: str):
    """Find a user by role and their ID field. Returns None if not found."""
    model = model_for_role(role)
    if not model:
        return None
    id_field = 'patient_id' if role == 'patient' else 'doctor_id' if role == 'doctor' else 'care_giver_id'
    return model.query.filter(getattr(model, id_field) == user_id).first()


# ---------------------------------------------------------------------------
# Find user by role + subject (for token identity resolution)
# ---------------------------------------------------------------------------

def find_user_by_role_and_subject(role: str, subject: str):
    """Find a user by their role and JWT subject."""
    if role == 'patient':
        return Patient.query.filter_by(patient_id=subject).first()
    if role == 'doctor':
        return Doctor.query.filter_by(doctor_id=subject).first()
    if role == 'caregiver':
        return CareGiver.query.filter_by(care_giver_id=subject).first()
    if role == 'admin':
        return Admin.query.filter_by(admin_id=subject).first()
    return None
