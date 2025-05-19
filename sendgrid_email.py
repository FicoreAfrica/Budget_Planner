import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from jinja2 import Environment, FileSystemLoader
from translations import t

SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
SENDER_EMAIL = 'no-reply@ficoreafrica.com'

def send_email(to_email: str, subject: str, template_name: str, data: dict, lang: str = 'en'):
    """Send an email using SendGrid with a rendered template."""
    if not SENDGRID_API_KEY:
        print("SendGrid API key not configured.")
        return False

    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template(template_name)
    html_content = template.render(data=data, t=lambda key: t(key, lang))

    message = Mail(
        from_email=SENDER_EMAIL,
        to_emails=to_email,
        subject=t(subject, lang),
        html_content=html_content
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        print(f"Email sent to {to_email}, status: {response.status_code}")
        return True
    except Exception as e:
        print(f"Failed to send email to {to_email}: {str(e)}")
        return False