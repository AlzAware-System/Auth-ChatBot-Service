"""GPS Repository — Data access for Location model."""

import json
from datetime import datetime, timedelta

from app import db
from app.models.location import Location
from app.utils.redis_client import get_redis_client


def save_location(device_id: str, latitude: float, longitude: float, timestamp):
    location = Location(
        device_id=device_id,
        lat=latitude,
        lon=longitude,
        timestamp=timestamp,
    )
    db.session.add(location)
    return location


def delete_old_locations():
    cutoff = datetime.utcnow() - timedelta(days=7)
    Location.query.filter(Location.timestamp < cutoff).delete(synchronize_session=False)


def commit():
    db.session.commit()


def rollback():
    db.session.rollback()


def find_last_location(device_id: str):
    return (
        Location.query
        .filter(Location.device_id == device_id)
        .order_by(Location.timestamp.desc())
        .first()
    )


def find_location_history(device_id: str, from_dt=None, to_dt=None):
    query = Location.query.filter(Location.device_id == device_id)
    if from_dt:
        query = query.filter(Location.timestamp >= from_dt)
    if to_dt:
        query = query.filter(Location.timestamp <= to_dt)
    return query.order_by(Location.timestamp.asc()).all()


# ---------------------------------------------------------------------------
# Redis cache operations
# ---------------------------------------------------------------------------

def cache_gps_in_redis(device_id: str, latitude: float, longitude: float, timestamp_iso: str | None):
    try:
        redis_client = get_redis_client()
        if redis_client:
            redis_key = f"gps:{device_id}"
            redis_data = {
                'device': device_id,
                'lat': latitude,
                'lon': longitude,
                'timestamp': timestamp_iso,
            }
            redis_client.setex(redis_key, 86400, json.dumps(redis_data))
    except Exception:
        pass  # Fail gracefully if Redis is unavailable


def get_cached_gps(device_id: str):
    try:
        redis_client = get_redis_client()
        if redis_client:
            redis_key = f"gps:{device_id}"
            cached_data = redis_client.get(redis_key)
            if cached_data:
                return json.loads(cached_data)
    except Exception:
        pass  # Fail gracefully, fallback to DB
    return None
