import os
import requests
from flask import Flask, session, has_request_context, render_template
from typing import Dict, Optional
from translations import trans

def send_email(
    app: Flask,
    logger: logging.LoggerAdapter,
    to_email: str,
    subject: str,
    template_name: str,
    data: Dict,
    lang: Optional[str] = None
) -> None:
    """
    Send an email using MailerSend API with a rendered template.

    Args:
        app: Flask application instance for context.
        logger: Logger instance with SessionAdapter for session-aware logging.
        to_email: Recipient's email address.
        subject: Email subject.
        template_name: Name of the email template (e.g., 'budget/email.html').
        data: Data to pass to the template for rendering.
        lang: Language code ('en' or 'ha'). Defaults to session['language'] or 'en'.

    Raises:
        ValueError: If API token, from email, or template name is invalid.
        RuntimeError: If template rendering or API request fails.

    Notes:
        - Requires environment variables: MAILERSEND_API_TOKEN, MAILERSEND_FROM_EMAIL.
        - Uses Flask's context processor for 'trans' in templates.
        - Logs errors with session ID for debugging.
    """
    # Default language from session
    if lang is None:
        lang = session.get('language', 'en') if has_request_context() else 'en'
    if lang not in ['en', 'ha']:
        logger.warning(f"Invalid language '{lang}', falling back to 'en'")
        lang = 'en'

    session_id = session.get('sid', 'no-session-id') if has_request_context() else 'no-session-id'

    # Validate environment variables
    api_token = os.environ.get('MAILERSEND_API_TOKEN')
    from_email = os.environ.get('MAILERSEND_FROM_EMAIL')
    if not api_token:
        logger.error("MailerSend API token not set", extra={'session_id': session_id})
        raise ValueError("MAILERSEND_API_TOKEN environment variable is required")
    if not from_email:
        logger.error("MailerSend from email not set", extra={'session_id': session_id})
        raise ValueError("MAILERSEND_FROM_EMAIL environment variable is required")

    # Validate template name
    if not template_name.endswith('.html'):
        template_name += '.html'
    template_path = os.path.join(app.template_folder, template_name)
    if not os.path.exists(template_path):
        logger.error(f"Template {template_name} not found at {template_path}", extra={'session_id': session_id})
        raise ValueError(f"Email template {template_name} does not exist")

    # Render email template
    with app.app_context():
        try:
            html_content = render_template(template_name, **data, lang=lang)
        except Exception as e:
            logger.error(f"Failed to render email template {template_name}: {str(e)}", extra={'session_id': session_id})
            raise RuntimeError(f"Cannot render email template {template_name}: {str(e)}")

    # Configure MailerSend API request
    url = "https://api.mailersend.com/v1/email"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "from": {
            "email": from_email,
            "name": "FiCore Africa"
        },
        "to": [
            {
                "email": to_email
            }
        ],
        "subject": subject,
        "html": html_content
    }

    # Send email
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if 200 <= response.status_code < 300:
            logger.info(f"Email sent successfully to {to_email}", extra={'session_id': session_id})
        else:
            logger.error(
                f"Failed to send email to {to_email}: {response.status_code} {response.text}",
                extra={'session_id': session_id}
            )
            raise RuntimeError(f"MailerSend API error: {response.text}")
    except requests.RequestException as e:
        logger.error(f"Network error sending email to {to_email}: {str(e)}", extra={'session_id': session_id})
        raise RuntimeError(f"Cannot send email to {to_email}: {str(e)}")
