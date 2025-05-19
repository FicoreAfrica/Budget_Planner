from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from json_store import JsonStorageManager
from mailersend_email import send_email

financial_health_bp = Blueprint('financial_health', __name__)
financial_health_storage = JsonStorageManager('data/financial_health.json')

@financial_health_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    if request.method == 'POST':
        data = request.form.to_dict()
        session['health_step1'] = {
            'first_name': data.get('first_name', ''),
            'email': data.get('email', ''),
            'business_name': data.get('business_name', ''),
            'user_type': data.get('user_type', ''),
            'send_email': data.get('send_email', 'off')
        }
        return redirect(url_for('financial_health.step2'))
    return render_template('health_score_step1.html')

@financial_health_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    if request.method == 'POST':
        try:
            data = request.form.to_dict()
            amounts = ['income', 'expenses']
            for field in amounts:
                value = float(data.get(field, 0))
                if value > 10000000000:
                    flash(f"{field.capitalize()} cannot exceed ₦10 billion.")
                    return redirect(url_for('financial_health.step2'))
                data[field] = value
            session['health_step2'] = data
            return redirect(url_for('financial_health.step3'))
        except ValueError:
            flash("Invalid numeric input for income or expenses.")
            return redirect(url_for('financial_health.step2'))
    return render_template('health_score_step2.html')

@financial_health_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    if request.method == 'POST':
        try:
            data = request.form.to_dict()
            debt = float(data.get('debt', 0))
            interest_rate = float(data.get('interest_rate', 0))
            if debt > 10000000000:
                flash("Debt cannot exceed ₦10 billion.")
                return redirect(url_for('financial_health.step3'))
            step1_data = session.get('health_step1', {})
            step2_data = session.get('health_step2', {})
            income = step2_data.get('income', 0)
            expenses = step2_data.get('expenses', 0)
            debt_to_income = (debt / income * 100) if income > 0 else 0
            savings_rate = ((income - expenses) / income * 100) if income > 0 else 0
            score = min(100, max(0, 100 - debt_to_income - interest_rate + savings_rate))  # Simplified scoring
            status = "Excellent" if score >= 80 else "Good" if score >= 60 else "Needs Improvement"
            record = {
                "data": {
                    "first_name": step1_data.get('first_name', ''),
                    "email": step1_data.get('email', ''),
                    "business_name": step1_data.get('business_name', ''),
                    "user_type": step1_data.get('user_type', ''),
                    "income": income,
                    "expenses": expenses,
                    "debt": debt,
                    "interest_rate": interest_rate,
                    "debt_to_income": debt_to_income,
                    "savings_rate": savings_rate,
                    "score": score,
                    "status": status
                }
            }
            email = step1_data.get('email')
            send_email_flag = step1_data.get('send_email') == 'on'
            financial_health_storage.append(record, user_email=email, session_id=session.sid)
            if send_email_flag and email:
                send_email(
                    to_email=email,
                    subject="Financial Health Report",
                    template_name="health_score_email.html",
                    data=record["data"],
                    lang=session.get('lang', 'en')
                )
            session.pop('health_step1', None)
            session.pop('health_step2', None)
            return redirect(url_for('financial_health.dashboard'))
        except ValueError:
            flash("Invalid numeric input for debt or interest rate.")
            return redirect(url_for('financial_health.step3'))
    return render_template('health_score_step3.html')

@financial_health_bp.route('/dashboard')
def dashboard():
    user_data = financial_health_storage.filter_by_session(session.sid)
    return render_template('health_score_dashboard.html', data=user_data[-1]["data"] if user_data else {})
