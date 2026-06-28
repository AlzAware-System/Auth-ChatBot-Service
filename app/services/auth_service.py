"""Auth Service — Business logic for authentication operations."""

import re
import secrets
import hashlib
import os
from uuid import uuid4
from datetime import datetime, timedelta

import bcrypt

from app.utils.jwt import create_access_token, decode_token, JWTError, revoke_token, build_password_signature
from app.utils.error_handler import AppError, ValidationError, AuthError, NotFoundError
from app.utils.response import success_response
from app.utils.email import send_password_reset_email
from app.utils.audit import record_system_log
from app.repositories import user_repository as user_repo

DUMMY_PASSWORD_HASH = b'$2b$12$KIXe8P7v4Z4PqM7w8rE5IeM6bHq7.Hq7Hq7Hq7Hq7Hq7Hq7Hq7Hq'


def _dummy_verify(password: str | None = None):
    if not password:
        password = 'dummy'
    if isinstance(password, str):
        password = password.encode('utf-8')
    try:
        bcrypt.checkpw(password[:72], DUMMY_PASSWORD_HASH)
    except Exception:
        pass


def _normalize_email(email: str):
    return email.strip().lower()


def _missing_fields(data: dict, required: list[str]):
    return [f for f in required if not data.get(f)]


def _validate_email(email: str):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email)


def _issue_token(subject: str, role: str, password_hash: str | None = None):
    extra = None
    pwd_sig = build_password_signature(password_hash)
    if pwd_sig:
        extra = {'pwd_sig': pwd_sig}
    return create_access_token(subject, role=role, extra=extra)


def _subject_for_user(user_obj, role: str):
    if role == 'patient':
        return str(user_obj.patient_id)
    if role == 'doctor':
        return str(user_obj.doctor_id)
    if role == 'admin':
        return str(user_obj.admin_id)
    return str(user_obj.care_giver_id)


# ---------------------------------------------------------------------------
# Serialization helpers (moved from controller — used by service return data)
# ---------------------------------------------------------------------------

def patient_to_dict(patient):
    presc_list = []
    for pres in patient.prescriptions:
        schedule_time_str = pres.schedule_time.strftime('%H:%M:%S') if pres.schedule_time else None
        presc_list.append({
            'medicine_id': pres.medicine_id,
            'medicine_name': pres.medicine.name if pres.medicine else pres.medicine_name,
            'schedule_time': schedule_time_str,
            'alzhiemer_level': pres.alzhiemer_level,
            'notes': pres.notes
        })
    return {
        'patient_id': patient.patient_id,
        'name': patient.name,
        'email': patient.email,
        'age': patient.age,
        'gender': patient.gender,
        'phone': patient.phone,
        'city': patient.city,
        'address': patient.address,
        'age_category': patient.age_category,
        'chronic_disease': patient.chronic_disease,
        'hospital_address': patient.hospital_address,
        'doctor': (
            {
                'doctor_id': patient.doctor.doctor_id,
                'name': patient.doctor.name,
                'specialization': patient.doctor.specialization,
                'phone': patient.doctor.phone,
                'clinic_address': patient.doctor.clinic_address
            } if patient.doctor else None
        ),
        'care_giver': (
            {
                'care_giver_id': patient.care_giver.care_giver_id,
                'name': patient.care_giver.name,
                'relation': patient.care_giver.relation,
                'phone': patient.care_giver.phone,
                'city': patient.care_giver.city
            } if patient.care_giver else None
        ),
        'prescriptions': presc_list
    }


def caregiver_to_dict(caregiver):
    return {
        'care_giver_id': caregiver.care_giver_id,
        'name': caregiver.name,
        'email': caregiver.email,
        'relation': caregiver.relation,
        'phone': caregiver.phone,
        'city': caregiver.city,
        'address': caregiver.address,
        'patients': [
            {
                'patient_id': p.patient_id,
                'name': p.name,
                'age': p.age,
                'gender': p.gender,
                'email': p.email
            } for p in caregiver.patients
        ]
    }


def doctor_to_dict(doctor):
    return {
        'doctor_id': doctor.doctor_id,
        'name': doctor.name,
        'email': doctor.email,
        'gender': doctor.gender,
        'specialization': doctor.specialization,
        'age': doctor.age,
        'phone': doctor.phone,
        'city': doctor.city,
        'clinic_address': doctor.clinic_address,
        'patients': [
            {
                'patient_id': p.patient_id,
                'name': p.name,
                'age': p.age,
                'gender': p.gender,
                'email': p.email
            } for p in doctor.patients
        ]
    }


def admin_to_dict(admin):
    return {
        'admin_id': admin.admin_id,
        'name': admin.name,
        'email': admin.email,
        'active': admin.active,
    }


def public_user_payload(user_obj, role: str):
    if role == 'patient':
        return {'patient': patient_to_dict(user_obj)}
    if role == 'doctor':
        return {'doctor': doctor_to_dict(user_obj)}
    if role == 'admin':
        return {'admin': admin_to_dict(user_obj)}
    return {'caregiver': caregiver_to_dict(user_obj)}


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def _build_reset_url(raw_token: str, request_host_url: str = ''):
    template = (
        os.getenv('MOBILE_RESET_PASSWORD_URL_TEMPLATE')
        or os.getenv('RESET_PASSWORD_DEEP_LINK_TEMPLATE')
        or 'alzaware://resetpassword?token={token}'
    )
    if '{token}' in template:
        return template.format(token=raw_token)
    separator = '&' if '?' in template else '?'
    return f'{template}{separator}token={raw_token}'


def _build_reset_click_url(raw_token: str, request_host_url: str = ''):
    template = os.getenv('RESET_PASSWORD_CLICK_URL_TEMPLATE')
    if template:
        if '{token}' in template:
            return template.format(token=raw_token)
        separator = '&' if '?' in template else '?'
        return f'{template}{separator}token={raw_token}'
    base_url = (request_host_url or '').rstrip('/')
    return f'{base_url}/auth/resetpassword/open?token={raw_token}'


def _generate_reset_token_pair():
    raw_token = secrets.token_urlsafe(32)
    hashed_token = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    return raw_token, hashed_token


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_patient(data: dict, issue_token: bool = True, log_event: bool = True):
    required = ['name', 'email', 'password', 'doctor_id', 'care_giver_id']
    missing = _missing_fields(data, required)
    if missing:
        raise ValidationError(f'Missing required fields: {", ".join(missing)}', details={'fields': missing})

    email = _normalize_email(data['email'])
    if not _validate_email(email):
        raise ValidationError('Invalid email format')

    doctor = user_repo.find_doctor_by_id(data['doctor_id'])
    if not doctor:
        raise ValidationError(f'Doctor with id {data["doctor_id"]} does not exist')

    caregiver = user_repo.find_caregiver_by_id(data['care_giver_id'])
    if not caregiver:
        raise ValidationError(f'CareGiver with id {data["care_giver_id"]} does not exist')

    if user_repo.email_exists_in_any_table(email):
        _dummy_verify(data['password'])
        return success_response(
            message='If registration can proceed, further instructions will be provided.',
            status_code=200,
        )

    patient = user_repo.create_patient(
        patient_id=data.get('patient_id') or str(uuid4()),
        name=data['name'],
        email=email,
        age=data.get('age'),
        gender=data.get('gender'),
        phone=data.get('phone'),
        chronic_disease=data.get('chronic_disease'),
        city=data.get('city'),
        address=data.get('address'),
        age_category=data.get('age_category') or 'Unknown',
        hospital_address=data.get('hospital_address') or 'Not specified',
        doctor_id=data['doctor_id'],
        care_giver_id=data['care_giver_id'],
    )
    patient.set_password(data['password'])
    user_repo.commit()

    if log_event:
        record_system_log(
            event_type='patient_registered',
            message='Patient registered',
            target_role='patient',
            target_id=patient.patient_id,
            target_email=patient.email,
            details={'name': patient.name},
        )
        user_repo.commit()

    return success_response(
        message='If registration can proceed, further instructions will be provided.',
        status_code=200,
    )


def register_doctor(data: dict, issue_token: bool = True, log_event: bool = True):
    required = ['name', 'email', 'password']
    missing = _missing_fields(data, required)
    if missing:
        raise ValidationError(f'Missing fields: {", ".join(missing)}', details={'fields': missing})

    email = _normalize_email(data['email'])
    if not _validate_email(email):
        raise ValidationError('Invalid email format')

    if user_repo.email_exists_in_any_table(email):
        _dummy_verify(data['password'])
        return success_response(
            message='If registration can proceed, further instructions will be provided.',
            status_code=200,
        )

    doctor = user_repo.create_doctor(
        doctor_id=data.get('doctor_id') or str(uuid4()),
        name=data['name'],
        email=email,
        gender=data.get('gender'),
        specialization=data.get('specialization'),
        age=data.get('age'),
        phone=data.get('phone'),
        city=data.get('city'),
        clinic_address=data.get('clinic_address'),
    )
    doctor.set_password(data['password'])
    user_repo.commit()

    if log_event:
        record_system_log(
            event_type='doctor_created',
            message='Doctor registered',
            target_role='doctor',
            target_id=doctor.doctor_id,
            target_email=doctor.email,
            details={'name': doctor.name},
        )
        user_repo.commit()

    return success_response(
        message='If registration can proceed, further instructions will be provided.',
        status_code=200,
    )


def register_caregiver(data: dict, issue_token: bool = True, log_event: bool = True):
    required = ['name', 'email', 'password']
    missing = _missing_fields(data, required)
    if missing:
        raise ValidationError(f'Missing fields: {", ".join(missing)}', details={'fields': missing})

    email = _normalize_email(data['email'])
    if not _validate_email(email):
        raise ValidationError('Invalid email format')

    if user_repo.email_exists_in_any_table(email):
        _dummy_verify(data['password'])
        return success_response(
            message='If registration can proceed, further instructions will be provided.',
            status_code=200,
        )

    caregiver_obj = user_repo.create_caregiver(
        care_giver_id=data.get('care_giver_id') or str(uuid4()),
        name=data['name'],
        email=email,
        relation=data.get('relation'),
        phone=data.get('phone'),
        city=data.get('city'),
        address=data.get('address'),
    )
    caregiver_obj.set_password(data['password'])
    user_repo.commit()

    if log_event:
        record_system_log(
            event_type='caregiver_created',
            message='Caregiver registered',
            target_role='caregiver',
            target_id=caregiver_obj.care_giver_id,
            target_email=caregiver_obj.email,
            details={'name': caregiver_obj.name},
        )
        user_repo.commit()

    return success_response(
        message='If registration can proceed, further instructions will be provided.',
        status_code=200,
    )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def login_user(data: dict):
    role = (data.get('role') or '').strip().lower()
    identifier = (data.get('email') or data.get('username') or data.get('name') or '').strip()
    password = data.get('password')
    if not identifier or not password:
        raise ValidationError('email/username and password are required')

    ident_lower = identifier.lower()

    user_obj = None
    user_role = None

    def _match_patient():
        return user_repo.find_patient_by_identifier(ident_lower, identifier)

    def _match_doctor():
        return user_repo.find_doctor_by_identifier(ident_lower, identifier)

    def _match_caregiver():
        return user_repo.find_caregiver_by_identifier(ident_lower, identifier)

    def _match_admin():
        return user_repo.find_admin_by_identifier(ident_lower, identifier)

    if role == 'patient':
        candidate = _match_patient()
        if candidate:
            if candidate.verify_password(password):
                user_obj, user_role = candidate, 'patient'
        else:
            _dummy_verify(password)
    elif role == 'doctor':
        candidate = _match_doctor()
        if candidate:
            if candidate.verify_password(password):
                user_obj, user_role = candidate, 'doctor'
        else:
            _dummy_verify(password)
    elif role == 'caregiver':
        candidate = _match_caregiver()
        if candidate:
            if candidate.verify_password(password):
                user_obj, user_role = candidate, 'caregiver'
        else:
            _dummy_verify(password)
    elif role == 'admin':
        candidate = _match_admin()
        if candidate:
            if candidate.verify_password(password):
                user_obj, user_role = candidate, 'admin'
        else:
            _dummy_verify(password)
    else:
        p = _match_patient()
        d = _match_doctor() if not p else None
        c = _match_caregiver() if not p and not d else None
        a = _match_admin() if not p and not d and not c else None

        found_any = False
        if p:
            found_any = True
            if p.verify_password(password):
                user_obj, user_role = p, 'patient'
        elif d:
            found_any = True
            if d.verify_password(password):
                user_obj, user_role = d, 'doctor'
        elif c:
            found_any = True
            if c.verify_password(password):
                user_obj, user_role = c, 'caregiver'
        elif a:
            found_any = True
            if a.verify_password(password):
                user_obj, user_role = a, 'admin'

        if not found_any:
            _dummy_verify(password)

    if not user_obj:
        raise AuthError('invalid credentials')

    if hasattr(user_obj, 'active') and not user_obj.active:
        raise AuthError('Account is deactivated')

    if user_role == 'patient':
        token = _issue_token(str(user_obj.patient_id), user_role, user_obj.password)
        record_system_log(
            event_type='patient_login',
            message='Patient logged in',
            target_role='patient',
            target_id=user_obj.patient_id,
            target_email=user_obj.email,
        )
        user_repo.commit()
        return success_response(
            data={'token': token, 'role': user_role, 'patient': patient_to_dict(user_obj)},
            message='Login successful',
            status_code=200,
        )
    if user_role == 'doctor':
        token = _issue_token(str(user_obj.doctor_id), user_role, user_obj.password)
        record_system_log(
            event_type='doctor_login',
            message='Doctor logged in',
            target_role='doctor',
            target_id=user_obj.doctor_id,
            target_email=user_obj.email,
        )
        user_repo.commit()
        return success_response(
            data={'token': token, 'role': user_role, 'doctor': doctor_to_dict(user_obj)},
            message='Login successful',
            status_code=200,
        )

    if user_role == 'admin':
        token = _issue_token(str(user_obj.admin_id), user_role, user_obj.password)
        record_system_log(
            event_type='admin_login',
            message='Admin logged in',
            target_role='admin',
            target_id=user_obj.admin_id,
            target_email=user_obj.email,
        )
        user_repo.commit()
        return success_response(
            data={'token': token, 'role': user_role, 'admin': admin_to_dict(user_obj)},
            message='Login successful',
            status_code=200,
        )

    token = _issue_token(str(user_obj.care_giver_id), user_role, user_obj.password)
    record_system_log(
        event_type='caregiver_login',
        message='Caregiver logged in',
        target_role='caregiver',
        target_id=user_obj.care_giver_id,
        target_email=user_obj.email,
    )
    user_repo.commit()
    return success_response(
        data={'token': token, 'role': user_role, 'caregiver': caregiver_to_dict(user_obj)},
        message='Login successful',
        status_code=200,
    )


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def logout_user(token: str):
    if not token:
        raise AuthError('Missing Bearer token')
    try:
        decode_token(token)
    except JWTError as e:
        raise AuthError(str(e)) from e

    revoke_token(token)
    return success_response(message='Logged out', status_code=200)


# ---------------------------------------------------------------------------
# Forgot password
# ---------------------------------------------------------------------------

def forget_password_flow(data: dict, request_host_url: str = ''):
    email_raw = data.get('email')
    role = (data.get('role') or '').strip().lower() or None
    if not email_raw:
        raise ValidationError('email is required')

    email = _normalize_email(email_raw)
    if not _validate_email(email):
        raise ValidationError('Invalid email format')

    try:
        user_obj, _resolved_role = user_repo.resolve_user_by_email(email, role)
    except ValueError as e:
        if 'Email exists in multiple accounts' in str(e):
            user_obj = None
        else:
            raise ValidationError(str(e))

    if not user_obj:
        _generate_reset_token_pair()  # Dummy operation to align timing slightly
        return success_response(
            message='If your account exists, you will receive an email.',
            status_code=200,
        )

    raw_token, hashed_token = _generate_reset_token_pair()
    user_obj.password_reset_token = hashed_token
    user_obj.password_reset_expires = datetime.utcnow() + timedelta(minutes=10)
    user_repo.commit()

    reset_url = _build_reset_url(raw_token, request_host_url)
    click_url = _build_reset_click_url(raw_token, request_host_url)
    send_password_reset_email(to_email=email, reset_url=reset_url, click_url=click_url)

    return success_response(
        message='If your account exists, you will receive an email.',
        status_code=200,
    )


# ---------------------------------------------------------------------------
# Reset password
# ---------------------------------------------------------------------------

def reset_password_flow(data: dict, query_token: str | None = None):
    raw_token = (data.get('token') or query_token or '').strip()
    new_password = data.get('password')

    if not raw_token:
        raise ValidationError('token is required')
    if not new_password:
        raise ValidationError('password is required')

    hashed_token = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    now_utc = datetime.utcnow()

    user_obj, resolved_role = user_repo.find_user_by_reset_token(hashed_token, now_utc)

    if not user_obj:
        raise ValidationError('Token is invalid or has expired')

    user_obj.set_password(new_password)
    user_obj.password_reset_token = None
    user_obj.password_reset_expires = None
    user_repo.commit()

    token = _issue_token(_subject_for_user(user_obj, resolved_role), resolved_role, user_obj.password)
    response_data = {'token': token, 'role': resolved_role}
    response_data.update(public_user_payload(user_obj, resolved_role))

    return success_response(
        message='Password reset successful',
        data=response_data,
        status_code=200,
    )


# ---------------------------------------------------------------------------
# Open reset password link
# ---------------------------------------------------------------------------

def build_reset_redirect_url(raw_token: str):
    if not raw_token:
        raise ValidationError('token is required')
    return _build_reset_url(raw_token)


# ---------------------------------------------------------------------------
# Update my password
# ---------------------------------------------------------------------------

def update_my_password_flow(data: dict, token: str):
    current_password = data.get('password_current') or data.get('current_password')
    new_password = data.get('password') or data.get('new_password')
    confirm_password = data.get('confirm_password')

    if not current_password:
        raise ValidationError('current_password is required')
    if not new_password or not confirm_password:
        raise ValidationError('password and confirm_password are required')
    if new_password != confirm_password:
        raise ValidationError('Password and confirm_password do not match')

    if not token:
        raise AuthError('Missing Bearer token')

    try:
        payload = decode_token(token)
    except JWTError as e:
        raise AuthError(str(e)) from e

    role = payload.get('role')
    sub = payload.get('sub')
    if role not in ('patient', 'doctor', 'caregiver', 'admin'):
        raise AuthError('Invalid token role')

    user_obj = user_repo.find_user_by_role_and_subject(role, sub)

    if not user_obj:
        not_found_messages = {
            'patient': 'Patient not found',
            'doctor': 'Doctor not found',
            'admin': 'Admin not found',
        }
        raise NotFoundError(not_found_messages.get(role, 'CareGiver not found'))

    if not user_obj.verify_password(current_password):
        raise AuthError('Your current password is wrong.')

    user_obj.set_password(new_password)
    user_repo.commit()

    new_token = _issue_token(_subject_for_user(user_obj, role), role, user_obj.password)
    response_data = {'token': new_token, 'role': role}
    response_data.update(public_user_payload(user_obj, role))

    return success_response(
        message='Password updated successfully',
        data=response_data,
        status_code=200,
    )
