"""Matching Game Controller — Thin HTTP layer that delegates to matching_game_service."""

from flask import request

from app.utils.error_handler import handle_errors, ValidationError
from app.utils.validation import validate_payload, SubmitMatchingAnswersPayload
from app.utils.jwt import decode_token, JWTError
from app.utils.error_handler import AuthError
from app.services import matching_game_service


def _get_token_from_header():
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header.split(' ', 1)[1]
    return None


@handle_errors('Upload matching item failed')
def upload_matching_item():
    token = _get_token_from_header()

    person_name = (request.form.get('name') or '').strip()
    patient_id = (request.form.get('patient_id') or '').strip()

    if 'image' not in request.files:
        raise ValidationError('No image file provided. Use form-data with key "image".')

    image_file = request.files['image']
    return matching_game_service.upload_matching_item(token, person_name, patient_id, image_file)


@handle_errors('Start matching game failed')
def start_matching_game():
    token = _get_token_from_header()
    return matching_game_service.start_matching_game(token)


@handle_errors('Submit matching answers failed')
def submit_matching_answers():
    token = _get_token_from_header()
    payload = validate_payload(SubmitMatchingAnswersPayload, request.get_json(silent=True) or {})
    return matching_game_service.submit_matching_answers(token, payload)


@handle_errors('Fetch matching items failed')
def get_my_items():
    token = _get_token_from_header()
    patient_id_filter = request.args.get('patient_id', '').strip() or None
    return matching_game_service.get_my_items(token, patient_id_filter)


@handle_errors('Delete matching item failed')
def delete_matching_item(item_id: str):
    token = _get_token_from_header()
    return matching_game_service.delete_matching_item(token, item_id)


@handle_errors('Fetch game history failed')
def get_game_history():
    token = _get_token_from_header()
    patient_id = request.args.get('patient_id', '').strip()
    return matching_game_service.get_game_history(token, patient_id)
