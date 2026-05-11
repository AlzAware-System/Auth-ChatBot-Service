import os
import random
from uuid import uuid4

from flask import request, current_app
from werkzeug.utils import secure_filename

from app import db
from app.models.patient import Patient
from app.models.caregiver import CareGiver
from app.models.doctor import Doctor
from app.models.matching_item import MatchingItem
from app.models.matching_game_result import MatchingGameResult
from app.utils.error_handler import (
    handle_errors,
    AuthError,
    ValidationError,
    NotFoundError,
)
from app.utils.response import success_response
from app.utils.validation import validate_payload, SubmitMatchingAnswersPayload
from app.utils.jwt import decode_token, JWTError

ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
UPLOAD_SUBDIR = os.path.join('static', 'uploads', 'matching_game')


def _get_token_from_header():
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header.split(' ', 1)[1]
    return None


def _resolve_token_identity():
    token = _get_token_from_header()
    if not token:
        raise AuthError('Missing Bearer token')
    try:
        payload = decode_token(token)
    except JWTError as e:
        raise AuthError(str(e)) from e

    role = payload.get('role')
    subject = payload.get('sub')
    if not role or not subject:
        raise AuthError('Invalid token payload')
    return role, subject


def _caregiver_patient_guard(caregiver_id: str, patient_id: str) -> Patient:
    caregiver = CareGiver.query.filter_by(care_giver_id=caregiver_id).first()
    if not caregiver or not caregiver.active:
        raise AuthError('Caregiver account issues')

    patient = Patient.query.filter_by(patient_id=patient_id).first()
    if not patient or not patient.active:
        raise NotFoundError('Patient not found or inactive')

    if patient.care_giver_id != caregiver_id:
        raise AuthError('You are not authorized for this patient')

    return patient


def _doctor_patient_guard(doctor_id: str, patient_id: str) -> Patient:
    doctor = Doctor.query.filter_by(doctor_id=doctor_id).first()
    if not doctor or not doctor.active:
        raise AuthError('Doctor account issues')

    patient = Patient.query.filter_by(patient_id=patient_id).first()
    if not patient or not patient.active:
        raise NotFoundError('Patient not found or inactive')

    if patient.doctor_id != doctor_id:
        raise AuthError('You are not authorized for this patient')

    return patient


def _get_upload_dir() -> str:
    base = current_app.root_path
    upload_dir = os.path.join(base, UPLOAD_SUBDIR)
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def _matching_item_to_dict(item: MatchingItem, include_name: bool = True) -> dict:
    result = {
        'item_id': item.item_id,
        'patient_id': item.patient_id,
        'image_url': f'/{UPLOAD_SUBDIR}/{item.image_filename}'.replace('\\', '/'),
        'created_at': item.created_at.isoformat() if item.created_at else None,
    }
    if include_name:
        result['person_name'] = item.person_name
        result['caregiver_id'] = item.caregiver_id
    return result


def _game_result_to_dict(result: MatchingGameResult) -> dict:
    return {
        'result_id': result.result_id,
        'patient_id': result.patient_id,
        'total_items': result.total_items,
        'correct_count': result.correct_count,
        'wrong_count': result.wrong_count,
        'score': result.score,
        'played_at': result.played_at.isoformat() if result.played_at else None,
    }


@handle_errors('Upload matching item failed')
def upload_matching_item():
    role, subject = _resolve_token_identity()
    if role != 'caregiver':
        raise AuthError('Only caregivers can upload matching items')

    person_name = (request.form.get('name') or '').strip()
    if not person_name:
        raise ValidationError('name is required')

    patient_id = (request.form.get('patient_id') or '').strip()
    if not patient_id:
        raise ValidationError('patient_id is required')

    patient = _caregiver_patient_guard(subject, patient_id)

    if 'image' not in request.files:
        raise ValidationError('No image file provided. Use form-data with key "image".')

    image_file = request.files['image']
    if not image_file or not image_file.filename:
        raise ValidationError('Empty image file')

    if not _allowed_file(image_file.filename):
        raise ValidationError(
            f'Invalid image type. Allowed: {", ".join(ALLOWED_IMAGE_EXTENSIONS)}'
        )

    image_file.seek(0, os.SEEK_END)
    file_size = image_file.tell()
    image_file.seek(0)
    if file_size > MAX_IMAGE_SIZE_BYTES:
        raise ValidationError(f'Image too large. Maximum size is {MAX_IMAGE_SIZE_BYTES // (1024*1024)}MB')

    ext = image_file.filename.rsplit('.', 1)[1].lower()
    unique_filename = f'{uuid4().hex}.{ext}'
    upload_dir = _get_upload_dir()
    save_path = os.path.join(upload_dir, unique_filename)
    image_file.save(save_path)

    item = MatchingItem(
        item_id=str(uuid4()),
        patient_id=patient.patient_id,
        caregiver_id=subject,
        person_name=person_name,
        image_filename=unique_filename,
    )
    db.session.add(item)
    db.session.commit()

    return success_response(
        message='Matching item uploaded successfully',
        data=_matching_item_to_dict(item),
        status_code=201,
    )


@handle_errors('Start matching game failed')
def start_matching_game():
    role, subject = _resolve_token_identity()
    if role != 'patient':
        raise AuthError('Only patients can play the matching game')

    patient = Patient.query.filter_by(patient_id=subject).first()
    if not patient or not patient.active:
        raise NotFoundError('Patient not found or inactive')

    items = MatchingItem.query.filter_by(patient_id=subject).all()
    if not items or len(items) < 2:
        raise ValidationError(
            'Not enough matching items to start a game. '
            'Ask your caregiver to upload at least 2 items.'
        )

    image_list = [{'id': item.item_id, 'imageUrl': f'/{UPLOAD_SUBDIR}/{item.image_filename}'.replace('\\', '/')} for item in items]
    name_list = [{'id': item.item_id, 'name': item.person_name} for item in items]

    random.shuffle(image_list)
    random.shuffle(name_list)

    return success_response(
        data={
            'total_items': len(items),
            'images': image_list,
            'names': name_list,
        }
    )


@handle_errors('Submit matching answers failed')
def submit_matching_answers():
    role, subject = _resolve_token_identity()
    if role != 'patient':
        raise AuthError('Only patients can submit game answers')

    payload = validate_payload(SubmitMatchingAnswersPayload, request.get_json(silent=True) or {})
    answers = payload.get('answers', [])
    if not answers:
        raise ValidationError('answers list cannot be empty')

    items = MatchingItem.query.filter_by(patient_id=subject).all()
    if not items:
        raise ValidationError('No matching items found for this patient')

    valid_ids = {item.item_id for item in items}

    for answer in answers:
        if answer['imageId'] not in valid_ids:
            raise ValidationError(f'Invalid imageId: {answer["imageId"]}')
        if answer['nameId'] not in valid_ids:
            raise ValidationError(f'Invalid nameId: {answer["nameId"]}')

    correct_count = 0
    for answer in answers:
        if answer['imageId'] == answer['nameId']:
            correct_count += 1

    total_items = len(answers)
    wrong_count = total_items - correct_count
    score = round((correct_count / total_items) * 100) if total_items > 0 else 0

    game_result = MatchingGameResult(
        result_id=str(uuid4()),
        patient_id=subject,
        total_items=total_items,
        correct_count=correct_count,
        wrong_count=wrong_count,
        score=score,
    )
    db.session.add(game_result)
    db.session.commit()

    return success_response(
        message='Game completed',
        data=_game_result_to_dict(game_result),
    )


@handle_errors('Fetch matching items failed')
def get_my_items():
    role, subject = _resolve_token_identity()
    if role != 'caregiver':
        raise AuthError('Only caregivers can view uploaded items')

    patient_id = request.args.get('patient_id', '').strip()

    query = MatchingItem.query.filter_by(caregiver_id=subject)
    if patient_id:
        query = query.filter_by(patient_id=patient_id)

    items = query.order_by(MatchingItem.created_at.desc()).all()

    return success_response(
        data={
            'items': [_matching_item_to_dict(item) for item in items],
            'total': len(items),
        }
    )


@handle_errors('Delete matching item failed')
def delete_matching_item(item_id: str):
    role, subject = _resolve_token_identity()
    if role != 'caregiver':
        raise AuthError('Only caregivers can delete matching items')

    item = MatchingItem.query.filter_by(item_id=item_id).first()
    if not item:
        raise NotFoundError('Matching item not found')

    if item.caregiver_id != subject:
        raise AuthError('You can only delete your own uploaded items')

    try:
        upload_dir = _get_upload_dir()
        file_path = os.path.join(upload_dir, item.image_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass

    db.session.delete(item)
    db.session.commit()

    return success_response(message='Matching item deleted successfully')


@handle_errors('Fetch game history failed')
def get_game_history():
    role, subject = _resolve_token_identity()

    patient_id = request.args.get('patient_id', '').strip()
    if not patient_id:
        raise ValidationError('patient_id query parameter is required')

    if role == 'caregiver':
        _caregiver_patient_guard(subject, patient_id)
    elif role == 'doctor':
        _doctor_patient_guard(subject, patient_id)
    else:
        raise AuthError('Only caregivers and doctors can view game history')

    results = (
        MatchingGameResult.query
        .filter_by(patient_id=patient_id)
        .order_by(MatchingGameResult.played_at.desc())
        .all()
    )

    return success_response(
        data={
            'patient_id': patient_id,
            'results': [_game_result_to_dict(r) for r in results],
            'total': len(results),
        }
    )
