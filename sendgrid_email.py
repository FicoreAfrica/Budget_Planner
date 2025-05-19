import os
import requests
from flask import current_app

def send_email(to_email, subject, html_content):
    api_token = os.environ.get('MAILERSEND_API_TOKEN')
    if not api_token:
        current_app.logger.error("MailerSend API token not set")
        return False

    url = "https://api.mailersend.com/v1/email"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "from": {
            "email": "ficoreafrica@gmail.com",  # Replace with your verified domain
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

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 202:
            current_app.logger.info(f"Email sent to {to_email}")
            return True
        else:
            current_app.logger.error(f"Failed to send email: {response.text}")
            return False
    except Exception as e:
        current_app.logger.error(f"Error sending email: {e}")
        return False
