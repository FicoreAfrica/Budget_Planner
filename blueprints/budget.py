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

budget_bp = Blueprint('budget', __name__)
budget_storage = JsonStorage('data/budget.json')

# Forms for budget steps
class Step1Form(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[Optional(), Email()])
    send_email = SelectField('Send Email', choices=[('on', 'Yes'), ('off', 'No')])
    submit = SubmitField('Next')

class Step2Form(FlaskForm):
    income = FloatField('Monthly Income', validators=[DataRequired(), NumberRange(min=0, max=10000000000)])
    submit = SubmitField('Next')

class Step3Form(FlaskForm):
    housing = FloatField('Housing Expenses', validators=[DataRequired(), NumberRange(min=0)])
    food = FloatField('Food Expenses', validators=[DataRequired(), NumberRange(min=0)])
    transport = FloatField('Transport Expenses', validators=[DataRequired(), NumberRange(min=0)])
    other = FloatField('Other Expenses', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Next')

class Step4Form(FlaskForm):
    savings_goal = FloatField('Savings Goal', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Submit')

@budget_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    """Handle budget step 1 form."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step1Form()
    t = trans('t')
    if request.method == 'POST' and form.validate_on_submit():
        try:
            session['budget_step1'] = form.data
            return redirect(url_for('budget.step2'))
        except Exception as e:
            logging.exception(f"Error in budget.step1: {str(e)}")
            flash(trans("Error processing step 1."))
            return redirect(url_for('budget.step1'))
    return render_template('budget_step1.html', form=form, t=t)

@budget_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    """Handle budget step 2 form."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step2Form()
    t = trans('t')
    if request.method == 'POST' and form.validate_on_submit():
        try:
            session['budget_step2'] = form.data
            return redirect(url_for('budget.step3'))
        except Exception as e:
            logging.exception(f"Error in budget.step2: {str(e)}")
            flash(trans("Invalid numeric input for income."))
            return redirect(url_for('budget.step2'))
    return render_template('budget_step2.html', form=form, t=t)

@budget_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    """Handle budget step 3 form."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step3Form()
    t = trans('t')
    if request.method == 'POST' and form.validate_on_submit():
        try:
            session['budget_step3'] = form.data
            return redirect(url_for('budget.step4'))
        except Exception as e:
            logging.exception(f"Error in budget.step3: {str(e)}")
            flash(trans("Invalid numeric input for expenses."))
            return redirect(url_for('budget.step3'))
    return render_template('budget_step3.html', form=form, t=t)

@budget_bp.route('/step4', methods=['GET', 'POST'])
def step4():
    """Handle budget step 4 form and calculate budget."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step4Form()
    t = trans('t')
    if request.method == 'POST' and form.validate_on_submit():
        try:
            data = form.data
            step1_data = session.get('budget_step1', {})
            step2_data = session.get('budget_step2', {})
            step3_data = session.get('budget_step3', {})
            income = step2_data.get('income', 0)
            expenses = sum([
                step3_data.get('housing', 0),
                step3_data.get('food', 0),
                step3_data.get('transport', 0),
                step3_data.get('other', 0)
            ])
            surplus_deficit = income - expenses
            savings_goal = data['savings_goal']
            record = {
                "data": {
                    "name": step1_data.get('name', ''),
                    "email": step1_data.get('email', ''),
                    "income": income,
                    "expenses": expenses,
                    "housing": step3_data.get('housing', 0),
                    "food": step3_data.get('food', 0),
                    "transport": step3_data.get('transport', 0),
                    "other": step3_data.get('other', 0),
                    "savings_goal": savings_goal,
                    "surplus_deficit": surplus_deficit
                }
            }
            email = step1_data.get('email')
            send_email_flag = step1_data.get('send_email') == 'on'
            budget_storage.append(record, user_email=email, session_id=session['sid'])
            if send_email_flag and email:
                send_email(
                    to_email=email,
                    subject=trans("Budget Plan Summary"),
                    template_name="budget_email.html",
                    data=record["data"],
                    lang=session.get('lang', 'en')
                )
            session.pop('budget_step1', None)
            session.pop('budget_step2', None)
            session.pop('budget_step3', None)
            flash(trans("Budget plan completed."))
            return redirect(url_for('budget.dashboard'))
        except Exception as e:
            logging.exception(f"Error in budget.step4: {str(e)}")
            flash(trans("Error processing budget plan."))
            return redirect(url_for('budget.step4'))
    return render_template('budget_step4.html', form=form, t=t)

@budget_bp.route('/dashboard')
def dashboard():
    """Display budget dashboard."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    t = trans('t')
    try:
        user_data = budget_storage.filter_by_session(session['sid'])
        return render_template('budget_dashboard.html', data=user_data[-1]["data"] if user_data else {}, t=t)
    except Exception as e:
        logging.exception(f"Error in budget.dashboard: {str(e)}")
        flash(trans("Error loading dashboard."))
        return render_template('budget_dashboard.html', data={}, t=t)
