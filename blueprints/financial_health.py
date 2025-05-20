from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Email
from json_store import JsonStorage
from mailersend_email import send_email
from translations import t
import logging
import uuid

# Configure logging
logging.basicConfig(filename='data/storage.txt', level=logging.DEBUG)

financial_health_bp = Blueprint('financial_health', __name__)
financial_health_storage = JsonStorage('data/financial_health.json')

# Forms for financial health steps
class Step1Form(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    email = StringField('Email', validators=[Optional(), Email()])
    business_name = StringField('Business Name', validators=[Optional()])
    user_type = SelectField('User Type', choices=[('individual', 'Individual'), ('business', 'Business')])
    send_email = BooleanField('Send Email')
    submit = SubmitField('Next')

class Step2Form(FlaskForm):
    income = FloatField('Income', validators=[DataRequired(), NumberRange(min=0, max=10000000000)])
    expenses = FloatField('Expenses', validators=[DataRequired(), NumberRange(min=0, max=10000000000)])
    submit = SubmitField('Next')

class Step3Form(FlaskForm):
    debt = FloatField('Debt', validators=[DataRequired(), NumberRange(min=0, max=10000000000)])
    interest_rate = FloatField('Interest Rate', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Submit')

@financial_health_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    """Handle financial health step 1 form."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step1Form()
    if request.method == 'POST' and form.validate_on_submit():
        try:
            session['health_step1'] = form.data
            return redirect(url_for('financial_health.step2'))
        except Exception as e:
            logging.exception(f"Error in financial_health.step1: {str(e)}")
            flash(t("Error processing step 1.") or "Error processing step 1.", "danger")
            return redirect(url_for('financial_health.step1'))
    return render_template('health_score_step1.html', form=form)

@financial_health_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    """Handle financial health step 2 form."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step2Form()
    if request.method == 'POST' and form.validate_on_submit():
        try:
            session['health_step2'] = form.data
            return redirect(url_for('financial_health.step3'))
        except Exception as e:
            logging.exception(f"Error in financial_health.step2: {str(e)}")
            flash(t("Invalid numeric input for income or expenses.") or "Invalid numeric input for income or expenses.", "danger")
            return redirect(url_for('financial_health.step2'))
    return render_template('health_score_step2.html', form=form)

@financial_health_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    """Handle financial health step 3 form and calculate score."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step3Form()
    if request.method == 'POST' and form.validate_on_submit():
        try:
            data = form.data
            step1_data = session.get('health_step1', {})
            step2_data = session.get('health_step2', {})
            income = step2_data.get('income', 0)
            expenses = step2_data.get('expenses', 0)
            debt = data['debt']
            interest_rate = data['interest_rate']
            debt_to_income = (debt / income * 100) if income > 0 else 0
            savings_rate = ((income - expenses) / income * 100) if income > 0 else 0
            score = min(100, max(0, 100 - debt_to_income - interest_rate + savings_rate))
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
            send_email_flag = step1_data.get('send_email', False)
            financial_health_storage.append(record, user_email=email, session_id=session['sid'])
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
            flash(t("Financial health assessment completed.") or "Financial health assessment completed.", "success")
            return redirect(url_for('financial_health.dashboard'))
        except Exception as e:
            logging.exception(f"Error in financial_health.step3: {str(e)}")
            flash(t("Error processing financial health assessment.") or "Error processing financial health assessment.", "danger")
            return redirect(url_for('financial_health.step3'))
    return render_template('health_score_step3.html', form=form)

@financial_health_bp.route('/dashboard')
def dashboard():
    """Display financial health dashboard."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    try:
        user_data = financial_health_storage.filter_by_session(session['sid'])
        return render_template('health_score_dashboard.html', data=user_data[-1]["data"] if user_data else {})
    except Exception as e:
        logging.exception(f"Error in financial_health.dashboard: {str(e)}")
        flash(t("Error loading dashboard.") or "Error loading dashboard.", "danger")
        return render_template('health_score_dashboard.html', data={})
