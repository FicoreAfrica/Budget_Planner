from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from json_store import JsonStorageManager
from sendgrid_email import send_email

financial_health_bp = Blueprint('financial_health', __name__, template_folder='templates/financial_health')
financial_health_storage = JsonStorageManager('data/financial_health.json')

@financial_health_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    if request.method == 'POST':
        try:
            data = request.form.to_dict()
            amounts = ['income', 'expenses', 'savings_rate', 'debt_to_income']
            for field in amounts:
                value = float(data.get(field, 0))
                if field in ['income', 'expenses'] and value > 10000000000:
                    flash(f"{field.replace('_', ' ').title()} cannot exceed ₦10 billion.")
                    return redirect(url_for('financial_health.step1'))
                data[field] = value
            score = min(100, max(0, 100 - data['debt_to_income'] + data['savings_rate']))  # Simplified scoring
            status = "Excellent" if score >= 80 else "Good" if score >= 60 else "Needs Improvement"
            record = {
                "data": {
                    **data,
                    "score": score,
                    "status": status
                }
            }
            email = data.get('email')
            send_email_flag = data.get('send_email') == 'on'
            financial_health_storage.append(record, user_email=email, session_id=session.sid)
            if send_email_flag and email:
                send_email(
                    to_email=email,
                    subject="Financial Health Report",
                    template_name="financial_health/financial_health_email.html",
                    data=record["data"],
                    lang=session.get('lang', 'en')
                )
            return redirect(url_for('financial_health.dashboard'))
        except ValueError:
            flash("Invalid numeric input.")
            return redirect(url_for('financial_health.step1'))
    return render_template('financial_health/financial_health_step1.html')