from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Email
from json_store import JsonStorage
from mailersend_email import send_email
from translations import trans
from datetime import datetime
import logging
import uuid

# Configure logging
logging.basicConfig(filename='data/storage.txt', level=logging.DEBUG)

budget_bp = Blueprint('budget', __name__)
budget_storage = JsonStorage('data/budget.json')

# Forms for budget steps
class Step1Form(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(message='First name is required')])
    email = StringField('Email', validators=[Optional(), Email(message='Valid email is required')])
    send_email = BooleanField('Send Email')
    submit = SubmitField('Next')

class Step2Form(FlaskForm):
    income = FloatField('Monthly Income', validators=[DataRequired(message='Income is required'), NumberRange(min=0, max=10000000000, message='Income cannot exceed ₦10 billion')])
    submit = SubmitField('Next')

class Step3Form(FlaskForm):
    housing = FloatField('Housing/Rent', validators=[DataRequired(message='Housing cost is required'), NumberRange(min=0, message='Amount must be positive')])
    food = FloatField('Food', validators=[DataRequired(message='Food cost is required'), NumberRange(min=0, message='Amount must be positive')])
    transport = FloatField('Transport', validators=[DataRequired(message='Transport cost is required'), NumberRange(min=0, message='Amount must be positive')])
    dependents = FloatField('Dependents Support', validators=[DataRequired(message='Dependents support cost is required'), NumberRange(min=0, message='Amount must be positive')])
    miscellaneous = FloatField('Miscellaneous', validators=[DataRequired(message='Miscellaneous cost is required'), NumberRange(min=0, message='Amount must be positive')])
    others = FloatField('Others', validators=[DataRequired(message='Other expenses are required'), NumberRange(min=0, message='Amount must be positive')])
    submit = SubmitField('Next')

class Step4Form(FlaskForm):
    savings_goal = FloatField('Monthly Savings Goal', validators=[DataRequired(message='Savings goal is required'), NumberRange(min=0, message='Amount must be positive')])
    submit = SubmitField('Submit')

@budget_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    """Handle budget step 1 form (personal info)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step1Form()
    t = trans('t')
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['budget_step1'] = form.data
            logging.debug(f"Budget step1 form data: {form.data}")
            return redirect(url_for('budget.step2'))
        return render_template('budget_step1.html', form=form, t=t)
    except Exception as e:
        logging.exception(f"Error in budget.step1: {str(e)}")
        flash(t("Error processing personal information."))
        return render_template('budget_step1.html', form=form, t=t)

@budget_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    """Handle budget step 2 form (income)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step2Form()
    t = trans('t')
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['budget_step2'] = form.data
            logging.debug(f"Budget step2 form data: {form.data}")
            return redirect(url_for('budget.step3'))
        return render_template('budget_step2.html', form=form, t=t)
    except Exception as e:
        logging.exception(f"Error in budget.step2: {str(e)}")
        flash(t("Invalid numeric input for income."))
        return render_template('budget_step2.html', form=form, t=t)

@budget_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    """Handle budget step 3 form (expenses)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step3Form()
    t = trans('t')
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['budget_step3'] = form.data
            logging.debug(f"Budget step3 form data: {form.data}")
            return redirect(url_for('budget.step4'))
        return render_template('budget_step3.html', form=form, t=t)
    except Exception as e:
        logging.exception(f"Error in budget.step3: {str(e)}")
        flash(t("Invalid numeric input for expenses."))
        return render_template('budget_step3.html', form=form, t=t)

@budget_bp.route('/step4', methods=['GET', 'POST'])
def step4():
    """Handle budget step 4 form (savings goal) and calculate budget."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step4Form()
    t = trans('t')
    try:
        if request.method == 'POST' and form.validate_on_submit():
            data = form.data
            step1_data = session.get('budget_step1', {})
            step2_data = session.get('budget_step2', {})
            step3_data = session.get('budget_step3', {})
            income = step2_data.get('income', 0)
            expenses = sum([
                step3_data.get('housing', 0),
                step3_data.get('food', 0),
                step3_data.get('transport', 0),
                step3_data.get('dependents', 0),
                step3_data.get('miscellaneous', 0),
                step3_data.get('others', 0)
            ])
            surplus_deficit = income - expenses - data['savings_goal']
            record = {
                "id": str(uuid.uuid4()),
                "data": {
                    "first_name": step1_data.get('first_name', ''),
                    "email": step1_data.get('email', ''),
                    "income": income,
                    "expenses": expenses,
                    "housing": step3_data.get('housing', 0),
                    "food": step3_data.get('food', 0),
                    "transport": step3_data.get('transport', 0),
                    "dependents": step3_data.get('dependents', 0),
                    "miscellaneous": step3_data.get('miscellaneous', 0),
                    "others": step3_data.get('others', 0),
                    "savings_goal": data['savings_goal'],
                    "surplus_deficit": surplus_deficit,
                    "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }
            email = step1_data.get('email')
            send_email_flag = step1_data.get('send_email', False)
            budget_storage.append(record, user_email=email, session_id=session['sid'])
            if send_email_flag and email:
                send_email(
                    to_email=email,
                    subject=t("Your Budget Plan Summary"),
                    template_name="budget_email.html",
                    data={
                        "first_name": record["data"]["first_name"],
                        "income": record["data"]["income"],
                        "expenses": record["data"]["expenses"],
                        "housing": record["data"]["housing"],
                        "food": record["data"]["food"],
                        "transport": record["data"]["transport"],
                        "dependents": record["data"]["dependents"],
                        "miscellaneous": record["data"]["miscellaneous"],
                        "others": record["data"]["others"],
                        "savings_goal": record["data"]["savings_goal"],
                        "surplus_deficit": record["data"]["surplus_deficit"],
                        "created_at": record["data"]["created_at"],
                        "cta_url": url_for('budget.dashboard', _external=True)
                    },
                    lang=session.get('lang', 'en')
                )
            session.pop('budget_step1', None)
            session.pop('budget_step2', None)
            session.pop('budget_step3', None)
            flash(t("Budget plan completed successfully."))
            return redirect(url_for('budget.dashboard'))
        return render_template('budget_step4.html', form=form, t=t)
    except Exception as e:
        logging.exception(f"Error in budget.step4: {str(e)}")
        flash(t("Error processing budget plan."))
        return render_template('budget_step4.html', form=form, t=t)

@budget_bp.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    """Display budget dashboard with delete functionality."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    t = trans('t')
    try:
        user_data = budget_storage.filter_by_session(session['sid'])
        budgets = [(record["id"], record["data"]) for record in user_data]
        latest_budget = budgets[-1][1] if budgets else {}
        
        if request.method == 'POST':
            action = request.form.get('action')
            budget_id = request.form.get('budget_id')
            
            if action == 'delete':
                try:
                    if budget_storage.delete_by_id(budget_id):
                        flash(t("Budget item deleted successfully."))
                    else:
                        flash(t("Failed to delete budget item."))
                        logging.error(f"Failed to delete budget ID {budget_id}")
                    return redirect(url_for('budget.dashboard'))
                except Exception as e:
                    logging.exception(f"Error deleting budget item: {str(e)}")
                    flash(t("Error deleting budget item."))
                    return redirect(url_for('budget.dashboard'))
        
        # Calculate insights and tips
        tips = [
            t("Track expenses weekly to stay within budget."),
            t("Contribute to Ajo/Esusu/Adashe for disciplined savings."),
            t("Top up data subscriptions early to avoid interruptions."),
            t("Plan for dependents’ needs to avoid overspending.")
        ]
        insights = []
        if latest_budget.get('surplus_deficit', 0) < 0:
            insights.append(t("Your budget shows a deficit. Consider reducing miscellaneous expenses like outings or subscriptions."))
        elif latest_budget.get('surplus_deficit', 0) > 0:
            insights.append(t("Great job! Invest your surplus in savings schemes like Ajo or fixed deposits."))
        if latest_budget.get('savings_goal', 0) == 0:
            insights.append(t("Set a savings goal to build financial security."))

        return render_template(
            'budget_dashboard.html',
            budgets=budgets,
            latest_budget=latest_budget,
            tips=tips,
            insights=insights,
            t=t
        )
    except Exception as e:
        logging.exception(f"Error in budget.dashboard: {str(e)}")
        flash(t("Error loading dashboard."))
        return render_template(
            'budget_dashboard.html',
            budgets=[],
            latest_budget={},
            tips=[],
            insights=[],
            t=t
        )
