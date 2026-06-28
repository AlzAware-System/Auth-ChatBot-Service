"""Chat Controller — Thin HTTP layer that delegates to chat_service."""

from flask import request

from app.utils.error_handler import handle_errors, AppError
from app.utils.validation import validate_payload, ChatAskPayload
from app.services import chat_service


@handle_errors('AI Error')
def ask_text():
    payload = getattr(request, 'current_user_payload', None)
    if not payload or payload.get('role') != 'patient':
        raise AppError('Access denied.', status_code=403)

    patient_id = payload.get('sub')
    data = validate_payload(ChatAskPayload, request.get_json(silent=True) or {})

    return chat_service.ask_text(patient_id, data)


@handle_errors('Voice processing failed')
def ask_voice():
    payload = getattr(request, 'current_user_payload', None)
    if not payload or payload.get('role') != 'patient':
        raise AppError('Access denied.', status_code=403)
    patient_id = payload.get('sub')

    from app.utils.error_handler import ValidationError
    if 'audio' not in request.files:
        raise ValidationError('No audio')

    audio_file = request.files['audio']
    return chat_service.ask_voice(patient_id, audio_file)
