import os
import requests
from flask import current_app, render_template, flash
from translations import trans  # Import trans directly

def send_email(to_email, subject, template_name, data, lang='en'):
    """
    Send an email using MailerSend API with a rendered template.
    
    Args:
        to_email (str): Recipient's email address.
        subject (str): Email subject.
        template_name (str): Path to the email template (e.g., 'budget_email.html').
        data (dict): Data to pass to the template.
        lang (str): Language code ('en' or 'ha') for translations.
    
    Returns:
        bool: True if email sent successfully, False otherwise.
    """
    # Retrieve environment variables
    api_token = os.environ.get('MAILERSEND_API_TOKEN')
    from_email = os.environ.get('MAILERSEND_FROM_EMAIL', 'ficoreafrica@gmail.com')
    
    if not api_token:
        current_app.logger.error("MailerSend API token not set")
        flash(trans("email_api_token_missing", lang=lang), "danger")
        return False

    # Render email template with translations
    try:
        html_content = render_template(
            template_name,
            trans=trans,  # Explicitly pass trans for clarity, though context processor makes it available
            **data,
            lang=lang
        )
    except Exception as e:
        current_app.logger.error(f"Failed to render email template {template_name}: {e}")
        flash(trans("email_template_render_error", lang=lang), "danger")
        return False

    # Configure MailerSend API request
    url = "https://api.mailersend.com/v1/email"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "from": {
            "email": from_email,
            "name": "Ficore Africa"
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
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 202:
            current_app.logger.info(f"Email sent successfully to {to_email}")
            return True
        else:
            current_app.logger.error(f"Failed to send email to {to_email}: {response.text}")
            flash(trans("email_api_error", lang=lang), "danger")
            return False
    except Exception as e:
        current_app.logger.error(f"Error sending email to {to_email}: {e}")
        flash(trans("email_network_error", lang=lang), "danger")
        return False
