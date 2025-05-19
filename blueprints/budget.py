from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from json_store import JsonStorageManager
from sendgrid_email import send_email

budget_bp = Blueprint('budget', __name__, template_folder='templates/budget')
budget_storage = JsonStorageManager('data/budget.json')

@budget_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    if request.method == 'POST':
        try:
            data = request.form.to_dict()
            amounts = ['income', 'fixed_expenses', 'variable_expenses', 'savings_goal']
            for field in amounts:
                value = float(data.get(field, 0))
                if value > 10000000000:
                    flash(f"{field.replace('_', ' ').title()} cannot exceed ₦10 billion.")
                    return redirect(url_for('budget.step1'))
                data[field] = value
            surplus_deficit = data['income'] - (data['fixed_expenses'] + data['variable_expenses'] + data['savings_goal'])
            record = {
                "data": {
                    **data,
                    "surplus_deficit": surplus_deficit
                }
            }
            email = data.get('email')
            send_email_flag = data.get('send_email') == 'on'
            budget_storage.append(record, user_email=email, session_id=session.sid)
            if send_email_flag and email:
                send_email(
                    to_email=email,
                    subject="Budget Report",
                    template_name="budget/budget_email.html",
                    data=record["data"],
                    lang=session.get('lang', 'en')
                )
            return redirect(url_for('budget.dashboard'))
        except ValueError:
            flash("Invalid numeric input.")
            return redirect(url_for('budget.step1'))
    return render_template('budget/budget_step1.html')