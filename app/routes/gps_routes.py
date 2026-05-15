from flask import Blueprint

from app.controllers.gps_controller import receive_gps, get_last_location, get_history
from app.utils.jwt import jwt_required


gps_bp = Blueprint('gps', __name__)


@gps_bp.route('/gps', methods=['POST'])
@jwt_required()
def receive_gps_route():
    return receive_gps()


@gps_bp.route('/gps/last', methods=['GET'])
@jwt_required()
def get_last_location_route():
    return get_last_location()


@gps_bp.route('/gps/history', methods=['GET'])
@jwt_required()
def get_history_route():
    return get_history()
