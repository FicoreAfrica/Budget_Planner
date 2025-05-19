from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from json_store import JsonStorageManager
from sendgrid_email import send_email

net_worth_bp = Blueprint('net_worth', __name__)
net_worth_storage = JsonStorageManager('data/networth.json')

@net_worth_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    if request.method == 'POST':
        session['net_worth_step1'] = request.form.to_dict()
        return redirect(url_for('net_worth.step2'))
    return render_template('net_worth_step1.html')

@net_worth_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    if request.method == 'POST':
        try:
            data = request.form.to_dict()
            amounts = ['cash_savings', 'investments', 'property', 'other_assets', 'loans', 'other_liabilities']
            for field in amounts:
                value = float(data.get(field, 0))
                if value > 10000000000:
                    flash(f"{field.replace('_', ' ').title()} cannot exceed ₦10 billion.")
                    return redirect(url_for('net_worth.step2'))
                data[field] = value
            total_assets = sum(data.get(field, 0) for field in ['cash_savings', 'investments', 'property', 'other_assets'])
            total_liabilities = sum(data.get(field, 0) for field in ['loans', 'other_liabilities'])
            net_worth = total_assets - total_liabilities
            record = {
                "data": {
                    "first_name": session.get('net_worth_step1', {}).get('first_name', ''),
                    **data,
                    "total_assets": total_assets,
                    "total_liabilities": total_liabilities,
                    "net_worth": net_worth
                }
            }
            email = session.get('net_worth_step1', {}).get('email')
            send_email_flag = session.get('net_worth_step1', {}).get('send_email') == 'on'
            net_worth_storage.append(record, user_email=email, session_id=session.sid)
            if send_email_flag and email:
                send_email(
                    to_email=email,
                    subject="Net Worth Report",
                    template_name="net_worth_email.html",
                    data=record["data"],
                    lang=session.get('lang', 'en')
                )
            session.pop('net_worth_step1', None)
            return redirect(url_for('net_worth.dashboard'))
        except ValueError:
            flash("Invalid numeric input.")
            return redirect(url_for('net_worth.step2'))
    return render_template('net_worth_step2.html')

@net_worth_bp.route('/dashboard')
def dashboard():
    user_data = net_worth_storage.filter_by_session(session.sid)
    return render_template('net_worth_dashboard.html', data=user_data[-1]["data"] if user_data else {})
