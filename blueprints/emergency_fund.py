from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Email
from json_store import JsonStorage
from mailersend_email import send_email
from ..translations import trans
import logging
import uuid

# Configure logging
logging.basicConfig(filename='data/storage.txt', level=logging.DEBUG)

emergency_fund_bp = Blueprint('emergency_fund', __name__)
emergency_fund_storage = JsonStorage('data/emergency_fund.json')

# Forms for emergency fund steps
class Step1Form(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    email = StringField('Email', validators=[Optional(), Email()])
    send_email = SelectField('Send Email', choices=[('on', 'Yes'), ('off', 'No')])
    monthly_expenses = FloatField('Monthly Expenses', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Next')

class Step2Form(FlaskForm):
    current_savings = FloatField('Current Savings', validators=[DataRequired(), NumberRange(min=0)])
    email = StringField('Email', validators=[Optional(), Email()])
    send_email = SelectField('Send Email', choices=[('on', 'Yes'), ('off', 'No')])
    submit = SubmitField('Submit')

@emergency_fund_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    """Handle emergency fund step 1 form."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step1Form()
    t = trans('t')
    if request.method == 'POST' and *form.validate_on_submit():
        try:
            session['emergency_fund_step1'] = form.data
            return redirect(url_for('emergency_fund.step2'))
        except Exception as e:
            logging.exception(f"Error in emergency_fund.step1: {str(e)}")
            flash(trans("Error processing step 1."))
            return redirect(url_for('emergency_fund.step1'))
    return render_template('emergency_fund_step1.html', form=form, t=t)

@emergency_fund_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    """Handle emergency fund step 2 form and calculate savings gap."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step2Form()
    t = trans('t')
    if request.method == 'POST' and form.validate_on_submit():
        try:
            data = form.data
            step1_data = session.get('emergency_fund_step1', {})
            monthly_expenses = step1_data.get('monthly_expenses', 0)
            current_savings = data.get('current_savings')
            target_savings = monthly_expenses * 6  # 6 months' expenses
            savings_gap = target_savings - current_savings
            record = {
                "data": {
                    "first_name": step1_data.get('first_name', ''),
                    "email": step1_data.get('email', ''),
                    "send_email": step1_data.get('send_email', 'off'),
                    "monthly_expenses": monthly_expenses,
                    "current_savings": current_savings,
                    "target_savings": target_savings,
                    "savings_gap": savings_gap
                }
            }
            email = data.get('email') or step1_data.get('email')
            send_email_flag = data.get('send_email') == 'on' or step1_data.get('send_email') == 'on'
            emergency_fund_storage.append(record, user_email=email, session_id=session['sid'])
            if send_email_flag and email:
                send_email(
                    to_email=email,
                    subject=trans("Emergency Fund Plan"),
                    template_name="emergency_fund_email.html",
                    data=record["data"],
                    lang=session.get('lang', 'en')
                )
            session.pop('emergency_fund_step1', None)
            flash(trans("Emergency fund plan completed."))
            return redirect(url_for('emergency_fund.dashboard'))
        except Exception as e:
            logging.exception(f"Error in emergency_fund.step2: {str(e)}")
            flash(trans("Error processing emergency fund plan."))
            return redirect(url_for('emergency_fund.step2'))
    return render_template('emergency_fund_step2.html', form=form, t=t)

@emergency_fund_bp.route('/dashboard')
def dashboard():
    """Display emergency fund dashboard."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    t = trans('t')
    try:
        user_data = emergency_fund_storage.filter_by_session(session['sid'])
        return render_template('emergency_fund_dashboard.html', data=user_data[-1]["data"] if user_data else {}, t=t)
    except Exception as e:
        logging.exception(f"Error in emergency_fund.dashboard: {str(e)}")
        flash(trans("Error loading dashboard."))
        return render_template('emergency_fund_dashboard.html', data={}, t=t)
