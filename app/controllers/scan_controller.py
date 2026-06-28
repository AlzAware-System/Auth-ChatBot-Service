"""Scan Controller — Thin HTTP layer that delegates to scan_service."""

from flask import request

from app.utils.error_handler import handle_errors, ValidationError
from app.services import scan_service


def _get_token_from_header():
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header.split(' ', 1)[1]
    return None


@handle_errors('Scan analysis failed')
def analyze_mri_scan():
    token = _get_token_from_header()

    if 'image' not in request.files:
        raise ValidationError('No image file provided. Use form-data with key "image".')

    img_file = request.files['image']
    lang = request.form.get('lang', 'ar').lower().strip()

    return scan_service.analyze_mri(token, img_file, lang)
