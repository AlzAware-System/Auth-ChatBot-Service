"""User Controller — Thin HTTP layer that delegates to user_service."""

from flask import request

from app.utils.error_handler import handle_errors
from app.utils.validation import (
    validate_payload,
    UpdateMePayload,
    AddPrescriptionPayload,
    AddGameScorePayload,
    RegisterDeviceTokenPayload,
    AddTodoPayload,
    UpdateTodoPayload,
)
from app.services import user_service


def _get_token_from_header():
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header.split(' ', 1)[1]
    data = request.get_json(silent=True) or {}
    body_token = data.get('token') or data.get('access_token') or data.get('bearer_token')
    if body_token:
        token_str = str(body_token).strip()
        if token_str.startswith('Bearer '):
            return token_str.split(' ', 1)[1]
        return token_str
    return None


@handle_errors('Fetch profile failed')
def me():
    token = _get_token_from_header()
    return user_service.get_profile(token)


@handle_errors('Update profile failed')
def updateme():
    data = validate_payload(UpdateMePayload, request.get_json(silent=True) or {})
    token = _get_token_from_header()
    return user_service.update_profile(data, token)


@handle_errors('Delete profile failed')
def deleteme():
    token = _get_token_from_header()
    return user_service.delete_profile(token)


@handle_errors('Add prescription failed')
def add_prescription():
    payload = validate_payload(AddPrescriptionPayload, request.get_json(silent=True) or {})
    token = _get_token_from_header()
    return user_service.add_prescription(payload, token)


@handle_errors('Fetch prescriptions failed')
def my_prescriptions():
    token = _get_token_from_header()
    return user_service.get_my_prescriptions(token)


@handle_errors('Fetch patient prescriptions failed')
def get_patient_prescriptions(patient_id: str):
    token = _get_token_from_header()
    return user_service.get_patient_prescriptions(patient_id, token)


@handle_errors('Fetch doctor patients failed')
def my_patients():
    token = _get_token_from_header()
    return user_service.get_my_patients(token)


@handle_errors('Add game score failed')
def add_game_score():
    payload = validate_payload(AddGameScorePayload, request.get_json(silent=True) or {})
    token = _get_token_from_header()
    return user_service.add_game_score(payload, token)


@handle_errors('Fetch patient game scores failed')
def get_patient_game_scores(patient_id: str):
    token = _get_token_from_header()
    return user_service.get_patient_game_scores(patient_id, token)


@handle_errors('Register device token failed')
def register_device_token():
    payload = validate_payload(RegisterDeviceTokenPayload, request.get_json(silent=True) or {})
    token = _get_token_from_header()
    return user_service.register_device_token(payload, token)


@handle_errors('Add todo failed')
def add_todo():
    payload = validate_payload(AddTodoPayload, request.get_json(silent=True) or {})
    token = _get_token_from_header()
    return user_service.add_todo(payload, token)


@handle_errors('Fetch patient todos failed')
def get_patient_todos(patient_id: str):
    token = _get_token_from_header()
    return user_service.get_patient_todos(patient_id, token)


@handle_errors('Update todo failed')
def update_todo(todo_id: str):
    payload = validate_payload(UpdateTodoPayload, request.get_json(silent=True) or {})
    token = _get_token_from_header()
    return user_service.update_todo(todo_id, payload, token)


@handle_errors('Delete todo failed')
def delete_todo(todo_id: str):
    token = _get_token_from_header()
    return user_service.delete_todo(todo_id, token)
