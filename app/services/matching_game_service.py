"""Matching Game Service — Business logic for matching game operations."""

import os
import random
from uuid import uuid4

from flask import current_app

from app.utils.error_handler import AuthError, ValidationError, NotFoundError
from app.utils.response import success_response
from app.utils.jwt import decode_token, JWTError
from app.repositories import user_repository as user_repo
from app.repositories import matching_game_repository as mg_repo

ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
UPLOAD_SUBDIR = os.path.join('static', 'uploads', 'matching_game')


# ---------------------------------------------------------------------------
# Token identity
# ---------------------------------------------------------------------------

def _resolve_token_identity(token: str):
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


# ---------------------------------------------------------------------------
# Guard helpers
# ---------------------------------------------------------------------------

def _caregiver_patient_guard(caregiver_id: str, patient_id: str):
    caregiver = user_repo.find_caregiver_by_id(caregiver_id)
    if not caregiver or not caregiver.active:
        raise AuthError('Caregiver account issues')

    patient = user_repo.find_patient_by_id(patient_id)
    if not patient or not patient.active:
        raise NotFoundError('Patient not found or inactive')

    if patient.care_giver_id != caregiver_id:
        raise AuthError('You are not authorized for this patient')

    return patient


def _doctor_patient_guard(doctor_id: str, patient_id: str):
    doctor = user_repo.find_doctor_by_id(doctor_id)
    if not doctor or not doctor.active:
        raise AuthError('Doctor account issues')

    patient = user_repo.find_patient_by_id(patient_id)
    if not patient or not patient.active:
        raise NotFoundError('Patient not found or inactive')

    if patient.doctor_id != doctor_id:
        raise AuthError('You are not authorized for this patient')

    return patient


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _get_upload_dir() -> str:
    base = current_app.root_path
    upload_dir = os.path.join(base, UPLOAD_SUBDIR)
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def _matching_item_to_dict(item, include_name: bool = True) -> dict:
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


def _game_result_to_dict(result) -> dict:
    return {
        'result_id': result.result_id,
        'patient_id': result.patient_id,
        'total_items': result.total_items,
        'correct_count': result.correct_count,
        'wrong_count': result.wrong_count,
        'score': result.score,
        'played_at': result.played_at.isoformat() if result.played_at else None,
    }


# ---------------------------------------------------------------------------
# Service methods
# ---------------------------------------------------------------------------

def upload_matching_item(token: str, person_name: str, patient_id: str, image_file):
    role, subject = _resolve_token_identity(token)
    if role != 'caregiver':
        raise AuthError('Only caregivers can upload matching items')

    if not person_name:
        raise ValidationError('name is required')
    if not patient_id:
        raise ValidationError('patient_id is required')

    patient = _caregiver_patient_guard(subject, patient_id)

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

    item = mg_repo.create_matching_item(
        item_id=str(uuid4()),
        patient_id=patient.patient_id,
        caregiver_id=subject,
        person_name=person_name,
        image_filename=unique_filename,
    )
    mg_repo.commit()

    return success_response(
        message='Matching item uploaded successfully',
        data=_matching_item_to_dict(item),
        status_code=201,
    )


def start_matching_game(token: str):
    role, subject = _resolve_token_identity(token)
    if role != 'patient':
        raise AuthError('Only patients can play the matching game')

    patient = user_repo.find_patient_by_id(subject)
    if not patient or not patient.active:
        raise NotFoundError('Patient not found or inactive')

    items = mg_repo.find_items_by_patient(subject)
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


def submit_matching_answers(token: str, payload: dict):
    role, subject = _resolve_token_identity(token)
    if role != 'patient':
        raise AuthError('Only patients can submit game answers')

    answers = payload.get('answers', [])
    if not answers:
        raise ValidationError('answers list cannot be empty')

    items = mg_repo.find_items_by_patient(subject)
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

    game_result = mg_repo.create_game_result(
        result_id=str(uuid4()),
        patient_id=subject,
        total_items=total_items,
        correct_count=correct_count,
        wrong_count=wrong_count,
        score=score,
    )
    mg_repo.commit()

    return success_response(
        message='Game completed',
        data=_game_result_to_dict(game_result),
    )


def get_my_items(token: str, patient_id_filter: str | None = None):
    role, subject = _resolve_token_identity(token)
    if role != 'caregiver':
        raise AuthError('Only caregivers can view uploaded items')

    items = mg_repo.find_items_by_caregiver(subject, patient_id=patient_id_filter)

    return success_response(
        data={
            'items': [_matching_item_to_dict(item) for item in items],
            'total': len(items),
        }
    )


def delete_matching_item(token: str, item_id: str):
    role, subject = _resolve_token_identity(token)
    if role != 'caregiver':
        raise AuthError('Only caregivers can delete matching items')

    item = mg_repo.find_matching_item_by_id(item_id)
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

    mg_repo.delete_matching_item(item)
    mg_repo.commit()

    return success_response(message='Matching item deleted successfully')


def get_game_history(token: str, patient_id: str):
    role, subject = _resolve_token_identity(token)

    if not patient_id:
        raise ValidationError('patient_id query parameter is required')

    if role == 'caregiver':
        _caregiver_patient_guard(subject, patient_id)
    elif role == 'doctor':
        _doctor_patient_guard(subject, patient_id)
    else:
        raise AuthError('Only caregivers and doctors can view game history')

    results = mg_repo.find_game_results_by_patient(patient_id)

    return success_response(
        data={
            'patient_id': patient_id,
            'results': [_game_result_to_dict(r) for r in results],
            'total': len(results),
        }
    )
