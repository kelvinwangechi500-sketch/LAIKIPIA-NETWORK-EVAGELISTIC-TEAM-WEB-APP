"""
Email Service — verification emails via SMTP (or console fallback in dev)
"""
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, url_for
from datetime import datetime, timedelta
import secrets


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def send_email(to_email: str, subject: str, html_body: str, text_body: str = "") -> bool:
    """
    Send an email. Uses SMTP if configured; otherwise logs the message
    (useful for local development).
    Returns True on success.
    """
    cfg = current_app.config
    mail_server = cfg.get("MAIL_SERVER", "")
    mail_port = int(cfg.get("MAIL_PORT", 587))
    mail_user = cfg.get("MAIL_USERNAME", "")
    mail_pass = cfg.get("MAIL_PASSWORD", "")
    mail_from = cfg.get("MAIL_DEFAULT_SENDER") or mail_user or "noreply@net-platform.local"
    use_tls = cfg.get("MAIL_USE_TLS", True)

    if not text_body:
        # crude strip of tags for plain-text fallback
        import re
        text_body = re.sub(r"<[^>]+>", "", html_body)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    if not mail_server or not mail_user:
        # Dev fallback — print to console / log
        current_app.logger.warning(
            "SMTP not configured. Email to %s:\nSubject: %s\n%s",
            to_email, subject, text_body
        )
        print("\n" + "=" * 60)
        print(f"[DEV EMAIL] To: {to_email}")
        print(f"Subject: {subject}")
        print(text_body)
        print("=" * 60 + "\n")
        return True

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(mail_server, mail_port, timeout=30) as server:
            if use_tls:
                server.starttls(context=context)
            server.login(mail_user, mail_pass)
            server.sendmail(mail_from, [to_email], msg.as_string())
        return True
    except Exception as e:
        current_app.logger.error("Failed to send email to %s: %s", to_email, e)
        return False


def send_verification_email(user) -> bool:
    """Generate a fresh token, save it, and email a verification link."""
    from extensions import db

    token = generate_token()
    user.verification_token = token
    user.verification_sent_at = datetime.utcnow()
    db.session.commit()

    verify_url = url_for("auth.verify_email", token=token, _external=True)

    subject = "Verify your NET Platform account"
    html = f"""
    <div style="font-family:sans-serif;max-width:520px;margin:0 auto;padding:24px">
      <h2 style="color:#B91C1C">Network Evangelistic Team</h2>
      <p>Hi {user.full_name.split()[0]},</p>
      <p>Thanks for registering. Please verify your email address by clicking the button below:</p>
      <p style="margin:28px 0">
        <a href="{verify_url}"
           style="background:#B91C1C;color:#fff;padding:12px 24px;border-radius:8px;
                  text-decoration:none;font-weight:600">
          Verify Email
        </a>
      </p>
      <p style="color:#6B7280;font-size:13px">
        Or copy this link into your browser:<br>
        <a href="{verify_url}">{verify_url}</a>
      </p>
      <p style="color:#9CA3AF;font-size:12px;margin-top:32px">
        This link expires in 24 hours. If you did not create an account, you can ignore this email.
      </p>
    </div>
    """
    text = (
        f"Hi {user.full_name.split()[0]},\n\n"
        f"Verify your NET Platform account:\n{verify_url}\n\n"
        "This link expires in 24 hours."
    )
    return send_email(user.email, subject, html, text)


def token_is_valid(user) -> bool:
    """Token must exist and have been sent within the last 24 hours."""
    if not user.verification_token or not user.verification_sent_at:
        return False
    return datetime.utcnow() - user.verification_sent_at < timedelta(hours=24)
