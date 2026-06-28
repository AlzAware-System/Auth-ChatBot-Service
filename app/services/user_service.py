"""User Service — Business logic for user management operations."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import func

from app.utils.jwt import decode_token, JWTError, revoke_token
from app.utils.error_handler import AppError, AuthError, ValidationError, NotFoundError
from app.utils.response import success_response
from app.utils.email import send_security_alert_email
from app.utils.sns_helper import register_device_to_sns, send_push_notification
from app.services.auth_service import patient_to_dict, caregiver_to_dict, doctor_to_dict, public_user_payload
from app.repositories import user_repository as user_repo
from app.repositories import prescription_repository as presc_repo
from app.repositories import game_score_repository as gs_repo
from app.repositories import todo_repository as todo_repo
from app.models.admin import Admin
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.caregiver import CareGiver


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _todo_to_dict(todo):
    return {
        'todo_id': todo.todo_id,
        'patient_id': todo.patient_id,
        'title': todo.title,
        'description': todo.description,
        'due_date': todo.due_date.isoformat() if todo.due_date else None,
        'is_done': todo.is_done,
        'created_by_role': todo.created_by_role,
        'created_by_id': todo.created_by_id,
        'created_at': todo.created_at.isoformat() if todo.created_at else None,
        'updated_at': todo.updated_at.isoformat() if todo.updated_at else None,
    }


def _game_score_to_dict(game_score):
    return {
        'game_score_id': game_score.game_score_id,
        'doctor_id': game_score.doctor_id,
        'patient_id': game_score.patient_id,
        'score': game_score.score,
        'created_at': game_score.created_at.isoformat() if game_score.created_at else None,
    }


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_schedule_time(schedule_time_value: str):
    value = str(schedule_time_value or '').strip()
    if not value:
        raise ValidationError('schedule_time is required in HH:MM or HH:MM:SS format')
    for fmt in ('%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    raise ValidationError('Invalid schedule_time format. Use HH:MM or HH:MM:SS')


def _parse_due_date(due_date_value):
    if due_date_value is None:
        return None
    value = str(due_date_value).strip()
    if not value:
        return None
    try:
        normalized = value.replace('Z', '+00:00')
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)
        return parsed
    except ValueError as exc:
        raise ValidationError('Invalid due_date format. Use ISO-8601 datetime') from exc


# ---------------------------------------------------------------------------
# Guard helpers
# ---------------------------------------------------------------------------

def _doctor_patient_guard(doctor_id: str, patient_id: str):
    doctor = user_repo.find_doctor_by_id(doctor_id)
    if not doctor or not doctor.active:
        raise AuthError('Doctor account issues')

    patient = user_repo.find_patient_by_id(patient_id)
    if not patient or not patient.active:
        raise NotFoundError('Patient not found/active')

    if patient.doctor_id != doctor_id:
        raise AuthError('Unauthorized for this patient')

    return patient


def _caregiver_patient_guard(caregiver_id: str, patient_id: str):
    caregiver = user_repo.find_caregiver_by_id(caregiver_id)
    if not caregiver or not caregiver.active:
        raise AuthError('Caregiver account issues')

    patient = user_repo.find_patient_by_id(patient_id)
    if not patient or not patient.active:
        raise NotFoundError('Patient not found/active')

    if patient.care_giver_id != caregiver_id:
        raise AuthError('Unauthorized for this patient')

    return patient


# ---------------------------------------------------------------------------
# Token identity resolution
# ---------------------------------------------------------------------------

def resolve_token_identity(token: str):
    if not token:
        raise AuthError('Missing Bearer token')
    try:
        payload = decode_token(token)
    except JWTError as e:
        raise AuthError(str(e)) from e

    role = payload.get('role')
    subject = payload.get('sub')
    if role not in ['patient', 'doctor', 'caregiver'] or not subject:
        raise AuthError('Invalid token payload')
    return role, subject


def resolve_token_payload(token: str):
    """Returns the full payload dict from a token."""
    if not token:
        raise AuthError('Missing Bearer token')
    try:
        payload = decode_token(token)
    except JWTError as e:
        raise AuthError(str(e)) from e
    return payload


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

def get_profile(token: str):
    payload = resolve_token_payload(token)
    role, sub = payload.get('role'), payload.get('sub')
    if role == 'doctor':
        user = user_repo.find_doctor_by_id(sub)
        if not user:
            raise NotFoundError('Doctor not found')
        return success_response(data=doctor_to_dict(user))
    if role == 'caregiver':
        user = user_repo.find_caregiver_by_id(sub)
        if not user:
            raise NotFoundError('CareGiver not found')
        return success_response(data=caregiver_to_dict(user))
    if role == 'admin':
        user = user_repo.find_admin_by_id(sub)
        if not user:
            raise NotFoundError('Admin not found')
        return success_response(data={'admin': {'admin_id': user.admin_id, 'name': user.name, 'email': user.email, 'active': user.active}})
    user = user_repo.find_patient_by_id(sub)
    if not user:
        raise NotFoundError('Patient not found')
    return success_response(data=patient_to_dict(user))


def update_profile(data: dict, token: str):
    if data.get('password'):
        raise ValidationError('Use /auth/updatemypassword for password updates.')
    payload = resolve_token_payload(token)
    role, sub = payload.get('role'), payload.get('sub')

    if role == 'patient':
        allowed = ['name', 'email', 'age', 'gender', 'phone', 'chronic_disease', 'city', 'address', 'hospital_address']
        user = user_repo.find_patient_by_id(sub)
    elif role == 'doctor':
        allowed = ['name', 'email', 'age', 'gender', 'phone', 'city', 'specialization', 'clinic_address']
        user = user_repo.find_doctor_by_id(sub)
    else:
        allowed = ['name', 'email', 'phone', 'city', 'address', 'relation']
        user = user_repo.find_caregiver_by_id(sub)

    if not user:
        raise NotFoundError('User not found')

    # Email Global Uniqueness Check
    new_email_raw = data.get('email')
    if new_email_raw:
        new_email = str(new_email_raw).strip().lower()
        if new_email and new_email != user.email:
            if user_repo.email_exists_in_any_table(new_email):
                raise AppError('Email already registered', status_code=409)

            send_security_alert_email(
                to_email=user.email,
                message=f'Your account email has been successfully changed to {new_email}.'
            )

            user.password_changed_at = datetime.utcnow()

    for k, v in data.items():
        if k in allowed and v is not None:
            setattr(user, k, v)
    user_repo.commit()

    return success_response(data=public_user_payload(user, role))


def delete_profile(token: str):
    payload = resolve_token_payload(token)
    role, sub = payload.get('role'), payload.get('sub')
    if role == 'patient':
        user = user_repo.find_patient_by_id(sub)
    elif role == 'doctor':
        user = user_repo.find_doctor_by_id(sub)
    else:
        user = user_repo.find_caregiver_by_id(sub)
    if not user:
        raise NotFoundError('User not found')
    user.active = False
    user_repo.commit()
    revoke_token(token)
    return success_response(message='Account deactivated')


# ---------------------------------------------------------------------------
# Prescriptions
# ---------------------------------------------------------------------------

def add_prescription(payload: dict, token: str):
    token_payload = resolve_token_payload(token)
    role, doctor_id = token_payload.get('role'), token_payload.get('sub')
    if role != 'doctor':
        raise AuthError('Only doctors can add prescriptions')
    doctor = user_repo.find_doctor_by_id(doctor_id)
    if not doctor or not doctor.active:
        raise AuthError('Doctor account issues')
    patient = user_repo.find_patient_by_id(payload['patient_id'])
    if not patient or not patient.active:
        raise NotFoundError('Patient not found/active')
    if patient.doctor_id != doctor_id:
        raise AuthError('Unauthorized for this patient')
    medicine = presc_repo.find_medicine_by_id(payload['medicine_id'])
    if not medicine:
        raise NotFoundError('Medicine not found')
    schedule_time = _parse_schedule_time(payload['schedule_time'])
    existing = presc_repo.find_prescription(payload['patient_id'], payload['medicine_id'])
    if existing:
        existing.medicine_name, existing.schedule_time = medicine.name, schedule_time
        existing.alzhiemer_level, existing.notes = payload.get('alzhiemer_level'), payload.get('notes')
        msg, prescription_obj = 'Prescription updated successfully', existing
    else:
        prescription_obj = presc_repo.create_prescription(
            patient_id=payload['patient_id'], medicine_id=payload['medicine_id'],
            medicine_name=medicine.name, schedule_time=schedule_time,
            alzhiemer_level=payload.get('alzhiemer_level'), notes=payload.get('notes')
        )
        msg = 'Prescription added successfully'
    presc_repo.commit()

    # Send push notification
    if patient.sns_endpoint_arn:
        title = "وصفة طبية جديدة 💊"
        body = f"أضاف طبيبك دواء ({medicine.name}) بموعد {schedule_time.strftime('%H:%M')}. ملاحظات: {payload.get('notes', 'لا يوجد')}"
        send_push_notification(patient.sns_endpoint_arn, title, body)

    return success_response(
        message=msg,
        data={
            'patient_id': prescription_obj.patient_id,
            'medicine_id': prescription_obj.medicine_id,
            'medicine_name': prescription_obj.medicine_name,
            'schedule_time': prescription_obj.schedule_time.strftime('%H:%M:%S'),
            'notes': prescription_obj.notes
        },
        status_code=201 if msg == 'Prescription added successfully' else 200
    )


def get_my_prescriptions(token: str):
    payload = resolve_token_payload(token)
    if payload.get('role') != 'patient':
        raise AuthError('Access denied')
    patient = user_repo.find_patient_by_id(payload.get('sub'))
    if not patient:
        raise NotFoundError('Patient not found')
    prescs = [{'medicine_name': p.medicine_name, 'schedule_time': p.schedule_time.strftime('%H:%M:%S'), 'notes': p.notes} for p in patient.prescriptions]
    return success_response(data={'prescriptions': prescs})


def get_patient_prescriptions(patient_id: str, token: str):
    payload = resolve_token_payload(token)
    if payload.get('role') != 'doctor':
        raise AuthError('Only doctors can view patient prescriptions')
    doctor_id = payload.get('sub')
    patient = _doctor_patient_guard(doctor_id, patient_id)
    prescs = [{'medicine_name': p.medicine_name, 'medicine_id': p.medicine_id, 'schedule_time': p.schedule_time.strftime('%H:%M:%S'), 'alzhiemer_level': p.alzhiemer_level, 'notes': p.notes} for p in patient.prescriptions]
    return success_response(data={'patient_id': patient.patient_id, 'patient_name': patient.name, 'prescriptions': prescs})


# ---------------------------------------------------------------------------
# My patients
# ---------------------------------------------------------------------------

def get_my_patients(token: str):
    payload = resolve_token_payload(token)
    if payload.get('role') != 'doctor':
        raise AuthError('Access denied')
    doctor = user_repo.find_doctor_by_id(payload.get('sub'))
    patients = [{'patient_id': p.patient_id, 'name': p.name, 'email': p.email} for p in doctor.patients if p.active]
    return success_response(data={'patients': patients})


# ---------------------------------------------------------------------------
# Game Scores
# ---------------------------------------------------------------------------

def add_game_score(payload: dict, token: str):
    token_payload = resolve_token_payload(token)
    role = token_payload.get('role')
    doctor_id_from_token = token_payload.get('sub')
    if role != 'doctor' or not doctor_id_from_token:
        raise AuthError('Only doctors can add game scores')
    if doctor_id_from_token != payload['doctor_id']:
        raise AuthError('doctor_id does not match authenticated doctor')

    patient = _doctor_patient_guard(payload['doctor_id'], payload['patient_id'])

    game_score = gs_repo.create_game_score(
        game_score_id=str(uuid4()),
        doctor_id=payload['doctor_id'],
        patient_id=patient.patient_id,
        score=payload['score'],
    )
    gs_repo.commit()

    return success_response(
        message='Game score added successfully',
        data=_game_score_to_dict(game_score),
        status_code=201,
    )


def get_patient_game_scores(patient_id: str, token: str):
    role, subject = resolve_token_identity(token)

    if role == 'patient':
        if subject != patient_id:
            raise AuthError('Patient can only view own game scores')
        patient = user_repo.find_patient_by_id(patient_id)
        if not patient or not patient.active:
            raise NotFoundError('Patient not found/active')
    elif role == 'doctor':
        patient = _doctor_patient_guard(subject, patient_id)
    elif role == 'caregiver':
        patient = _caregiver_patient_guard(subject, patient_id)
    else:
        raise AuthError('Access denied')

    scores = gs_repo.find_scores_by_patient(patient.patient_id)

    return success_response(
        data={
            'patient_id': patient.patient_id,
            'scores': [_game_score_to_dict(score) for score in scores],
        }
    )


# ---------------------------------------------------------------------------
# Device Token
# ---------------------------------------------------------------------------

def register_device_token(payload: dict, token: str):
    tp = resolve_token_payload(token)
    if tp.get('role') != 'patient':
        raise AuthError('Only patients can register tokens')
    patient = user_repo.find_patient_by_id(tp.get('sub'))
    if not patient:
        raise NotFoundError('Patient not found')

    arn = register_device_to_sns(payload['fcm_token'])
    if arn:
        patient.fcm_token = payload['fcm_token']
        patient.sns_endpoint_arn = arn
        user_repo.commit()
        return success_response(message='Device registered for notifications')
    raise AppError('Failed to register device with AWS', status_code=500)


# ---------------------------------------------------------------------------
# Todos
# ---------------------------------------------------------------------------

def add_todo(payload: dict, token: str):
    role, subject = resolve_token_identity(token)

    if role not in ['patient', 'caregiver']:
        raise AuthError('Only patient or caregiver can add todo')

    title = (payload.get('title') or '').strip()
    if not title:
        raise ValidationError('title is required')

    if role == 'patient':
        patient_id = subject
        requested_patient_id = payload.get('patient_id')
        if requested_patient_id and requested_patient_id != patient_id:
            raise AuthError('Patient can only add todo for self')
        patient = user_repo.find_patient_by_id(patient_id)
        if not patient or not patient.active:
            raise NotFoundError('Patient not found/active')
    else:
        patient_id = payload.get('patient_id')
        if not patient_id:
            raise ValidationError('patient_id is required for caregiver')
        patient = _caregiver_patient_guard(subject, patient_id)

    todo = todo_repo.create_todo(
        todo_id=str(uuid4()),
        patient_id=patient.patient_id,
        title=title,
        description=payload.get('description'),
        due_date=_parse_due_date(payload.get('due_date')),
        is_done=False,
        created_by_role=role,
        created_by_id=subject,
    )
    todo_repo.commit()

    return success_response(
        message='Todo added successfully',
        data=_todo_to_dict(todo),
        status_code=201,
    )


def get_patient_todos(patient_id: str, token: str):
    role, subject = resolve_token_identity(token)
    if role == 'patient':
        if subject != patient_id:
            raise AuthError('Patient can only view own todos')
        patient = user_repo.find_patient_by_id(patient_id)
        if not patient or not patient.active:
            raise NotFoundError('Patient not found/active')
    elif role == 'caregiver':
        patient = _caregiver_patient_guard(subject, patient_id)
    else:
        raise AuthError('Only patient or caregiver can view todos')

    todos = todo_repo.find_todos_by_patient(patient.patient_id)

    return success_response(
        data={
            'patient_id': patient.patient_id,
            'todos': [_todo_to_dict(todo) for todo in todos],
        }
    )


def update_todo(todo_id: str, payload: dict, token: str):
    role, subject = resolve_token_identity(token)
    if role not in ['patient', 'caregiver']:
        raise AuthError('Only patient or caregiver can update todo')

    todo = todo_repo.find_todo_by_id(todo_id)
    if not todo:
        raise NotFoundError('Todo not found')

    if role == 'patient':
        if todo.patient_id != subject:
            raise AuthError('Patient can only update own todos')
    else:
        _caregiver_patient_guard(subject, todo.patient_id)

    if all(value is None for value in payload.values()):
        raise ValidationError('At least one field is required to update')

    if payload.get('title') is not None:
        title = str(payload.get('title')).strip()
        if not title:
            raise ValidationError('title cannot be empty')
        todo.title = title

    if payload.get('description') is not None:
        todo.description = payload.get('description')

    if payload.get('due_date') is not None:
        todo.due_date = _parse_due_date(payload.get('due_date'))

    if payload.get('is_done') is not None:
        todo.is_done = bool(payload.get('is_done'))

    todo_repo.commit()
    return success_response(message='Todo updated successfully', data=_todo_to_dict(todo))


def delete_todo(todo_id: str, token: str):
    role, subject = resolve_token_identity(token)
    if role not in ['patient', 'caregiver']:
        raise AuthError('Access denied')

    todo = todo_repo.find_todo_by_id(todo_id)
    if not todo:
        raise NotFoundError('Todo not found')

    if role == 'patient':
        if todo.patient_id != subject:
            raise AuthError('Unauthorized to delete this todo')
    else:
        _caregiver_patient_guard(subject, todo.patient_id)

    todo_repo.delete_todo(todo)
    todo_repo.commit()
    return success_response(message='Todo deleted successfully')
