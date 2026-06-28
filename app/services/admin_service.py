"""Admin Service — Business logic for admin operations."""

from sqlalchemy.exc import IntegrityError

from app import db
from app.utils.jwt import decode_token, JWTError
from app.utils.error_handler import AppError, AuthError, ValidationError, NotFoundError
from app.utils.response import success_response
from app.utils.audit import record_system_log
from app.services.auth_service import (
    patient_to_dict,
    doctor_to_dict,
    caregiver_to_dict,
    register_patient,
    register_doctor,
    register_caregiver,
    _normalize_email,
    _validate_email,
)
from app.repositories import user_repository as user_repo
from app.repositories import system_log_repository as log_repo


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _admin_to_dict(admin):
    return {
        'admin_id': admin.admin_id,
        'name': admin.name,
        'email': admin.email,
        'active': admin.active,
    }


# ---------------------------------------------------------------------------
# Admin guard
# ---------------------------------------------------------------------------

def _require_admin(token: str):
    if not token:
        raise AuthError('Missing Bearer token')
    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise AuthError(str(exc)) from exc
    if payload.get('role') != 'admin' or not payload.get('sub'):
        raise AuthError('Admin access only')
    admin = user_repo.find_admin_by_id(payload['sub'])
    if not admin or not admin.active:
        raise NotFoundError('Admin not found')
    return admin


# ---------------------------------------------------------------------------
# List helpers
# ---------------------------------------------------------------------------

def _list_users_for_role(role: str):
    model = user_repo.model_for_role(role)
    if not model:
        raise ValidationError('role must be one of patient, doctor, caregiver')
    if role == 'patient':
        return [patient_to_dict(user) for user in user_repo.find_all_active_patients()]
    if role == 'doctor':
        return [doctor_to_dict(user) for user in user_repo.find_all_active_doctors()]
    return [caregiver_to_dict(user) for user in user_repo.find_all_active_caregivers()]


# ---------------------------------------------------------------------------
# Service methods
# ---------------------------------------------------------------------------

def get_overview(token: str):
    _require_admin(token)
    return success_response(
        data={
            'patients_count': user_repo.count_active_patients(),
            'doctors_count': user_repo.count_active_doctors(),
            'caregivers_count': user_repo.count_active_caregivers(),
            'admins_count': user_repo.count_active_admins(),
            'logs_count': log_repo.count_all_logs(),
        }
    )


def list_users(token: str, role: str | None = None):
    _require_admin(token)
    if role:
        return success_response(data={'role': role, 'users': _list_users_for_role(role)})
    return success_response(
        data={
            'patients': _list_users_for_role('patient'),
            'doctors': _list_users_for_role('doctor'),
            'caregivers': _list_users_for_role('caregiver'),
        }
    )


def create_user(token: str, role: str, payload: dict):
    _require_admin(token)
    role = (role or '').strip().lower()

    if role == 'patient':
        return register_patient(payload, issue_token=False, log_event=True)
    if role == 'doctor':
        return register_doctor(payload, issue_token=False, log_event=True)
    if role == 'caregiver':
        return register_caregiver(payload, issue_token=False, log_event=True)

    raise ValidationError('role must be patient, doctor, or caregiver')


def update_user_email(token: str, role: str, user_id: str, payload: dict):
    _require_admin(token)
    new_email = _normalize_email((payload.get('email') or '').strip())
    if not new_email:
        raise ValidationError('email is required')
    if not _validate_email(new_email):
        raise ValidationError('Invalid email format')

    user_obj = user_repo.fetch_user_by_role_and_id(role, user_id)
    if not user_obj:
        raise NotFoundError(f'{role.title()} not found')

    is_duplicate, error_msg = user_repo.email_exists_cross_table_for_update(new_email, role, user_id)
    if is_duplicate:
        raise ValidationError(error_msg)

    old_email = user_obj.email
    user_obj.email = new_email
    user_repo.commit()
    record_system_log(
        event_type='user_email_updated',
        message='User email updated by admin',
        actor_role='admin',
        target_role=role,
        target_id=user_id,
        target_email=new_email,
        details={'old_email': old_email, 'new_email': new_email},
    )
    user_repo.commit()

    return success_response(
        data={'role': role, 'user_id': user_id, 'email': new_email},
        message='Email updated successfully',
    )


def manage_user_account(token: str, role: str, user_id: str, payload: dict):
    _require_admin(token)
    action = (payload.get('action') or '').strip().lower()
    if action not in ('delete', 'disable', 'enable'):
        raise ValidationError('action must be one of: delete, disable, enable')

    user_obj = user_repo.fetch_user_by_role_and_id(role, user_id)
    if not user_obj:
        raise NotFoundError(f'{role.title()} not found')

    if action == 'disable':
        if not getattr(user_obj, 'active', True):
            return success_response(message=f'{role.title()} already disabled')
        user_obj.active = False
        user_repo.commit()
        record_system_log(
            event_type='user_disabled',
            message='User disabled by admin',
            actor_role='admin',
            target_role=role,
            target_id=user_id,
            target_email=getattr(user_obj, 'email', None),
        )
        user_repo.commit()
        return success_response(message=f'{role.title()} disabled successfully')

    if action == 'enable':
        if getattr(user_obj, 'active', True):
            return success_response(message=f'{role.title()} already enabled')
        user_obj.active = True
        user_repo.commit()
        record_system_log(
            event_type='user_enabled',
            message='User enabled by admin',
            actor_role='admin',
            target_role=role,
            target_id=user_id,
            target_email=getattr(user_obj, 'email', None),
        )
        user_repo.commit()
        return success_response(message=f'{role.title()} enabled successfully')

    try:
        user_repo.delete(user_obj)
        user_repo.commit()
    except IntegrityError as exc:
        user_repo.rollback()
        raise AppError(
            message='Cannot delete this user because related records exist. Use action=disable instead.',
            status_code=409,
            code='CONFLICT',
        ) from exc

    record_system_log(
        event_type='user_deleted',
        message='User permanently deleted by admin',
        actor_role='admin',
        target_role=role,
        target_id=user_id,
        target_email=getattr(user_obj, 'email', None),
    )
    user_repo.commit()
    return success_response(message=f'{role.title()} deleted permanently')


def get_logs(token: str, event_type: str | None = None):
    _require_admin(token)
    logs = log_repo.find_logs(event_type=event_type)
    return success_response(
        data={
            'logs': [
                {
                    'log_id': log.log_id,
                    'event_type': log.event_type,
                    'message': log.message,
                    'actor_role': log.actor_role,
                    'actor_id': log.actor_id,
                    'target_role': log.target_role,
                    'target_id': log.target_id,
                    'target_email': log.target_email,
                    'details': log.details,
                    'source_ip': log.source_ip,
                    'created_at': log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ]
        }
    )


def get_patient_login_logs(token: str):
    _require_admin(token)
    logs = log_repo.find_patient_login_logs()
    return success_response(
        data={
            'logs': [
                {
                    'log_id': log.log_id,
                    'patient_id': log.target_id,
                    'email': log.target_email,
                    'message': log.message,
                    'created_at': log.created_at.isoformat() if log.created_at else None,
                    'source_ip': log.source_ip,
                }
                for log in logs
            ]
        }
    )


def get_new_patient_logs(token: str):
    _require_admin(token)
    logs = log_repo.find_new_patient_logs()
    return success_response(
        data={
            'logs': [
                {
                    'log_id': log.log_id,
                    'patient_id': log.target_id,
                    'email': log.target_email,
                    'message': log.message,
                    'created_at': log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ]
        }
    )
