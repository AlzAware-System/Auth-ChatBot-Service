"""Auth Controller — Thin HTTP layer that delegates to auth_service."""

from flask import request, redirect

from app.utils.error_handler import handle_errors
from app.utils.validation import (
    validate_payload,
    RegisterPatientPayload,
    RegisterDoctorPayload,
    RegisterCaregiverPayload,
    LoginPayload,
    ForgetPasswordPayload,
    ResetPasswordPayload,
    UpdateMyPasswordPayload,
)
from app.services import auth_service


def _get_token_from_header():
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header.split(' ', 1)[1]
    data = request.get_json(silent=True) or {}
    body_token = data.get('token') or data.get('access_token') or data.get('bearer_token')
    if body_token:
        token_str = str(body_token).strip()
        if token_str.startswith('Bearer '):
            return token_str.split(' ', 1)[1]
        return token_str
    return None


@handle_errors('Register failed')
def register():
    data = validate_payload(RegisterPatientPayload, request.get_json(silent=True) or {})
    return auth_service.register_patient(data)


@handle_errors('Register patient failed')
def register_patient():
    data = validate_payload(RegisterPatientPayload, request.get_json(silent=True) or {})
    return auth_service.register_patient(data)


@handle_errors('Register doctor failed')
def register_doctor():
    data = validate_payload(RegisterDoctorPayload, request.get_json(silent=True) or {})
    return auth_service.register_doctor(data)


@handle_errors('Register caregiver failed')
def register_caregiver():
    data = validate_payload(RegisterCaregiverPayload, request.get_json(silent=True) or {})
    return auth_service.register_caregiver(data)


@handle_errors('Login failed')
def login():
    data = validate_payload(LoginPayload, request.get_json(silent=True) or {})
    return auth_service.login_user(data)


@handle_errors('Logout failed')
def logout():
    token = _get_token_from_header()
    return auth_service.logout_user(token)


@handle_errors('Forgot password failed')
def forget_password():
    data = validate_payload(ForgetPasswordPayload, request.get_json(silent=True) or {})
    return auth_service.forget_password_flow(data, request_host_url=request.host_url or '')


@handle_errors('Reset password failed')
def reset_password():
    data = validate_payload(ResetPasswordPayload, request.get_json(silent=True) or {})
    return auth_service.reset_password_flow(data, query_token=request.args.get('token'))


@handle_errors('Open reset password link failed')
def open_reset_password_link():
    raw_token = (request.args.get('token') or '').strip()
    url = auth_service.build_reset_redirect_url(raw_token)
    return redirect(url, code=302)


@handle_errors('Update password failed')
def update_my_password():
    data = validate_payload(UpdateMyPasswordPayload, request.get_json(silent=True) or {})
    token = _get_token_from_header()
    return auth_service.update_my_password_flow(data, token)
