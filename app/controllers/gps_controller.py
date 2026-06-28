"""GPS Controller — Thin HTTP layer that delegates to gps_service."""

from flask import jsonify, request

from app import db
from app.utils.jwt import jwt_required
from app.services import gps_service


@jwt_required()
def receive_gps():
    try:
        data = request.get_json(force=True)
        user_payload = getattr(request, 'current_user_payload', None)
        return gps_service.receive_gps(data, user_payload)

    except Exception as exc:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(exc)}), 400


@jwt_required()
def get_last_location():
    try:
        device_id = (request.args.get('device_id') or '').strip()
        user_payload = getattr(request, 'current_user_payload', None)
        return gps_service.get_last_location(device_id, user_payload)

    except Exception as exc:
        return jsonify({'error': 'internal server error', 'message': str(exc)}), 500


@jwt_required()
def get_history():
    try:
        device_id = (request.args.get('device_id') or '').strip()
        from_value = (request.args.get('from') or '').strip()
        to_value = (request.args.get('to') or '').strip()
        user_payload = getattr(request, 'current_user_payload', None)
        return gps_service.get_history(device_id, from_value, to_value, user_payload)

    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'error': 'internal server error', 'message': str(exc)}), 500
