import os
import smtplib
from email.message import EmailMessage
import threading

from app.utils.error_handler import AppError


def send_password_reset_email(to_email: str, reset_url: str, click_url: str | None = None) -> None:
    smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')
    from_email = os.getenv('EMAIL_FROM') or smtp_user

    if not smtp_user or not smtp_password:
        raise AppError(
            'Email service not configured. Set SMTP_USER and SMTP_PASSWORD in environment.',
            status_code=500,
            code='EMAIL_CONFIG_ERROR',
        )

    msg = EmailMessage()
    msg['Subject'] = 'Your password reset token (valid for 10 min)'
    msg['From'] = from_email
    msg['To'] = to_email
    button_url = click_url or reset_url

    msg.set_content(
        'Forgot your password?\n\n'
      f'Open this link to reset your password: {button_url}\n\n'
      "If you didn't forget your password, please ignore this email.\n\n"
      'AlzWare Team'
    )

    msg.add_alternative(
        f"""
        <html>
          <body>
            <p>Forgot your password?</p>
            <p>
              <a href=\"{button_url}\" style=\"display:inline-block;padding:10px 16px;background:#1a73e8;color:#ffffff;text-decoration:none;border-radius:6px;\">Reset Password</a>
            </p>
            <p>If you didn't forget your password, please ignore this email.</p>
            <p>AlzWare Team</p>
          </body>
        </html>
        """,
        subtype='html',
    )

    def _send():
        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        except Exception:
            pass

    threading.Thread(target=_send).start()

def send_email_change_verification(to_email: str, verify_url: str) -> None:
    smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')
    from_email = os.getenv('EMAIL_FROM') or smtp_user

    if not smtp_user or not smtp_password:
        raise AppError('Email service not configured.', status_code=500)

    msg = EmailMessage()
    msg['Subject'] = 'Verify your new email address (valid for 15 min)'
    msg['From'] = from_email
    msg['To'] = to_email

    msg.set_content(
        'You requested to change your account email.\n\n'
      f'Open this link to verify your new email: {verify_url}\n\n'
      "If you didn't request this, please ignore this email.\n\n"
      'AlzWare Team'
    )

    msg.add_alternative(
        f"""
        <html>
          <body>
            <p>You requested to change your account email.</p>
            <p>
              <a href="{verify_url}" style="display:inline-block;padding:10px 16px;background:#1a73e8;color:#ffffff;text-decoration:none;border-radius:6px;">Verify Email</a>
            </p>
            <p>If you didn't request this, please ignore this email.</p>
            <p>AlzWare Team</p>
          </body>
        </html>
        """,
        subtype='html',
    )

    def _send():
        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        except Exception:
            pass

    threading.Thread(target=_send).start()


def send_security_alert_email(to_email: str, message: str) -> None:
    smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')
    from_email = os.getenv('EMAIL_FROM') or smtp_user

    if not smtp_user or not smtp_password:
        return

    msg = EmailMessage()
    msg['Subject'] = 'Security Alert: Account Changes Detected'
    msg['From'] = from_email
    msg['To'] = to_email

    msg.set_content(
        'Security Alert\n\n'
      f'{message}\n\n'
      "If you didn't authorize this, please reset your password immediately and contact support.\n\n"
      'AlzWare Security Team'
    )

    def _send():
        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        except Exception:
            pass

    threading.Thread(target=_send).start()


