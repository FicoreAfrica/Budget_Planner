from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from json_store import JsonStorageManager
from mailersend_email import send_email

emergency_fund_bp = Blueprint('emergency_fund', __name__)
emergency_fund_storage = JsonStorageManager('data/emergency_fund.json')

@emergency_fund_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    if request.method == 'POST':
        session['emergency_fund_step1'] = request.form.to_dict()
        return redirect(url_for('emergency_fund.step2'))
    return render_template('emergency_fund_step1.html')

@emergency_fund_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    if request.method == 'POST':
        try:
            data = request.form.to_dict()
            amounts = ['income', 'expenses', 'current_savings']
            for field in amounts:
                value = float(data.get(field, 0))
                if value > 10000000000:
                    flash(f"{field.replace('_', ' ').title()} cannot exceed ₦10 billion.")
                    return redirect(url_for('emergency_fund.step2'))
                data[field] = value
            recommended_fund = data['expenses'] * 6  # 6 months of expenses
            savings_gap = max(0, recommended_fund - data['current_savings'])
            record = {
                "data": {
                    "first_name": session.get('emergency_fund_step1', {}).get('first_name', ''),
                    **data,
                    "recommended_fund": recommended_fund,
                    "savings_gap": savings_gap
                }
            }
            email = session.get('emergency_fund_step1', {}).get('email')
            send_email_flag = session.get('emergency_fund_step1', {}).get('send_email') == 'on'
            emergency_fund_storage.append(record, user_email=email, session_id=session.sid)
            if send_email_flag and email:
                send_email(
                    to_email=email,
                    subject="Emergency Fund Report",
                    template_name="emergency_fund_email.html",
                    data=record["data"],
                    lang=session.get('lang', 'en')
                )
            session.pop('emergency_fund_step1', None)
            return redirect(url_for('emergency_fund.dashboard'))
        except ValueError:
            flash("Invalid numeric input.")
            return redirect(url_for('emergency_fund.step2'))
    return render_template('emergency_fund_step2.html')

@emergency_fund_bp.route('/dashboard')
def dashboard():
    user_data = emergency_fund_storage.filter_by_session(session.sid)
    return render_template('emergency_fund_dashboard.html', data=user_data[-1]["data"] if user_data else {})
