from flask import Blueprint
from app.controllers.scan_controller import analyze_mri_scan

scan_bp = Blueprint('scan', __name__)

@scan_bp.route('/mri', methods=['POST'])
def analyze_mri_route():
    return analyze_mri_scan()
