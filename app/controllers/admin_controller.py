"""Admin Controller — Thin HTTP layer that delegates to admin_service."""

from flask import request

from app.utils.error_handler import handle_errors
from app.services import admin_service


def _get_bearer_token():
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header.split(' ', 1)[1]
    data = request.get_json(silent=True) or {}
    token = data.get('token') or data.get('access_token') or data.get('bearer_token')
    if token:
        token_str = str(token).strip()
        if token_str.startswith('Bearer '):
            return token_str.split(' ', 1)[1]
        return token_str
    return None


@handle_errors('Fetch admin overview failed')
def overview():
    token = _get_bearer_token()
    return admin_service.get_overview(token)


@handle_errors('Fetch users failed')
def list_users(role: str | None = None):
    token = _get_bearer_token()
    return admin_service.list_users(token, role)


@handle_errors('Create user failed')
def create_user(role: str):
    token = _get_bearer_token()
    payload = request.get_json(silent=True) or {}
    return admin_service.create_user(token, role, payload)


@handle_errors('Update user email failed')
def update_user_email(role: str, user_id: str):
    token = _get_bearer_token()
    payload = request.get_json(silent=True) or {}
    return admin_service.update_user_email(token, role, user_id, payload)


@handle_errors('Manage user account failed')
def manage_user_account(role: str, user_id: str):
    token = _get_bearer_token()
    payload = request.get_json(silent=True) or {}
    return admin_service.manage_user_account(token, role, user_id, payload)


@handle_errors('Fetch logs failed')
def list_logs():
    token = _get_bearer_token()
    event_type = (request.args.get('event_type') or '').strip().lower() or None
    return admin_service.get_logs(token, event_type)


@handle_errors('Fetch patient login logs failed')
def patient_login_logs():
    token = _get_bearer_token()
    return admin_service.get_patient_login_logs(token)


@handle_errors('Fetch new patient logs failed')
def new_patient_logs():
    token = _get_bearer_token()
    return admin_service.get_new_patient_logs(token)