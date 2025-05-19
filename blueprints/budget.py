from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from json_store import JsonStorageManager
from mailersend_email import send_email

budget_bp = Blueprint('budget', __name__)
budget_storage = JsonStorageManager('data/budget.json')

@budget_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    if request.method == 'POST':
        data = request.form.to_dict()
        session['budget_step1'] = {
            'first_name': data.get('first_name', ''),
            'email': data.get('email', ''),
            'language': data.get('language', 'en'),
            'send_email': data.get('send_email', 'off')
        }
        return redirect(url_for('budget.step2'))
    return render_template('budget_step1.html')

@budget_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    if request.method == 'POST':
        try:
            income = float(request.form.get('income', 0))
            if income > 10000000000:
                flash("Income cannot exceed ₦10 billion.")
                return redirect(url_for('budget.step2'))
            session['budget_step2'] = {'income': income}
            return redirect(url_for('budget.step3'))
        except ValueError:
            flash("Invalid numeric input for income.")
            return redirect(url_for('budget.step2'))
    return render_template('budget_step2.html')

@budget_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    if request.method == 'POST':
        try:
            data = request.form.to_dict()
            expenses = ['housing', 'food', 'transport', 'other']
            for field in expenses:
                value = float(data.get(field, 0))
                if value > 10000000000:
                    flash(f"{field.capitalize()} expenses cannot exceed ₦10 billion.")
                    return redirect(url_for('budget.step3'))
                data[field] = value
            session['budget_step3'] = data
            return redirect(url_for('budget.step4'))
        except ValueError:
            flash("Invalid numeric input for expenses.")
            return redirect(url_for('budget.step3'))
    return render_template('budget_step3.html')

@budget_bp.route('/step4', methods=['GET', 'POST'])
def step4():
    if request.method == 'POST':
        try:
            savings_goal = float(request.form.get('savings_goal', 0))
            if savings_goal > 10000000000:
                flash("Savings goal cannot exceed ₦10 billion.")
                return redirect(url_for('budget.step4'))
            step1_data = session.get('budget_step1', {})
            step2_data = session.get('budget_step2', {})
            step3_data = session.get('budget_step3', {})
            total_expenses = sum(step3_data.get(field, 0) for field in ['housing', 'food', 'transport', 'other'])
            surplus_deficit = step2_data.get('income', 0) - (total_expenses + savings_goal)
            record = {
                "data": {
                    "first_name": step1_data.get('first_name', ''),
                    "email": step1_data.get('email', ''),
                    "language": step1_data.get('language', 'en'),
                    "income": step2_data.get('income', 0),
                    "housing": step3_data.get('housing', 0),
                    "food": step3_data.get('food', 0),
                    "transport": step3_data.get('transport', 0),
                    "other": step3_data.get('other', 0),
                    "savings_goal": savings_goal,
                    "total_expenses": total_expenses,
                    "surplus_deficit": surplus_deficit
                }
            }
            email = step1_data.get('email')
            send_email_flag = step1_data.get('send_email') == 'on'
            budget_storage.append(record, user_email=email, session_id=session.sid)
            if send_email_flag and email:
                send_email(
                    to_email=email,
                    subject="Budget Report",
                    template_name="budget_email.html",
                    data=record["data"],
                    lang=session.get('lang', 'en')
                )
            session.pop('budget_step1', None)
            session.pop('budget_step2', None)
            session.pop('budget_step3', None)
            return redirect(url_for('budget.dashboard'))
        except ValueError:
            flash("Invalid numeric input for savings goal.")
            return redirect(url_for('budget.step4'))
    return render_template('budget_step4.html')

@budget_bp.route('/dashboard')
def dashboard():
    user_data = budget_storage.filter_by_session(session.sid)
    return render_template('budget_dashboard.html', data=user_data[-1]["data"] if user_data else {})
