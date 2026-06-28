"""GPS Service — Business logic for GPS/location operations."""

from datetime import datetime, timezone

from flask import jsonify

from app.repositories import gps_repository as gps_repo
from app.repositories import user_repository as user_repo


def _parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Invalid timestamp')

    raw_value = value.strip()
    if raw_value.endswith('Z'):
        raw_value = raw_value[:-1] + '+00:00'

    parsed = datetime.fromisoformat(raw_value)

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)

    return parsed


def check_location_access(device_id: str, payload: dict):
    if not payload:
        return False, 'Unauthorized'

    role = payload.get('role')
    sub = payload.get('sub')

    if role == 'patient':
        if sub != device_id:
            return False, 'Patient can only access own location'
    elif role == 'caregiver':
        patient = user_repo.find_patient_by_id(device_id)
        if not patient or patient.care_giver_id != sub:
            return False, 'Caregiver unauthorized for this patient'
    elif role == 'doctor':
        patient = user_repo.find_patient_by_id(device_id)
        if not patient or patient.doctor_id != sub:
            return False, 'Doctor unauthorized for this patient'
    elif role == 'admin':
        pass  # Admin can see any
    else:
        return False, 'Access denied'

    return True, ''


def receive_gps(data: dict, user_payload: dict):
    coordinates = data['geometry']['coordinates']
    if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
        raise ValueError('Invalid coordinates format')

    longitude = float(coordinates[0])
    latitude = float(coordinates[1])

    device_id = str(data['properties']['device']).strip()
    if not device_id:
        raise ValueError('Device id is required')

    allowed, msg = check_location_access(device_id, user_payload)
    if not allowed:
        return jsonify({'status': 'error', 'message': msg}), 403

    timestamp_raw = data['properties']['timestamp']
    parsed_timestamp = _parse_timestamp(timestamp_raw)

    location = gps_repo.save_location(device_id, latitude, longitude, parsed_timestamp)
    gps_repo.delete_old_locations()
    gps_repo.commit()

    # Cache in Redis
    gps_repo.cache_gps_in_redis(
        device_id, latitude, longitude,
        location.timestamp.isoformat() if location.timestamp else None
    )

    return jsonify({'status': 'ok'}), 200


def get_last_location(device_id: str, user_payload: dict):
    if not device_id:
        return jsonify({'error': 'device_id is required'}), 400

    allowed, msg = check_location_access(device_id, user_payload)
    if not allowed:
        return jsonify({'error': msg}), 403

    # 1. Try to get from Redis first
    cached = gps_repo.get_cached_gps(device_id)
    if cached:
        return jsonify(cached), 200

    # 2. Fallback to Database
    location = gps_repo.find_last_location(device_id)

    if not location:
        return jsonify({'error': 'not found'}), 404

    response_data = {
        'device': device_id,
        'lat': location.lat,
        'lon': location.lon,
        'timestamp': location.timestamp.isoformat() if location.timestamp else None,
    }

    # Cache the retrieved data for future requests
    gps_repo.cache_gps_in_redis(
        device_id, location.lat, location.lon,
        location.timestamp.isoformat() if location.timestamp else None
    )

    return jsonify(response_data), 200


def get_history(device_id: str, from_value: str, to_value: str, user_payload: dict):
    if not device_id:
        return jsonify({'error': 'device_id is required'}), 400

    allowed, msg = check_location_access(device_id, user_payload)
    if not allowed:
        return jsonify({'error': msg}), 403

    from_dt = None
    to_dt = None

    if from_value:
        from_dt = _parse_timestamp(from_value)
    if to_value:
        to_dt = _parse_timestamp(to_value)

    locations = gps_repo.find_location_history(device_id, from_dt, to_dt)

    return jsonify([
        {
            'lat': item.lat,
            'lon': item.lon,
            'timestamp': item.timestamp.isoformat() if item.timestamp else None,
        }
        for item in locations
    ]), 200
