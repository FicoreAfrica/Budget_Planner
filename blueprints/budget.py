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
    first_name = StringField(trans('first_name'), validators=[DataRequired(message=trans('first_name_required'))])
    email = StringField(trans('email'), validators=[Optional(), Email(message=trans('email_invalid'))])
    send_email = BooleanField(trans('send_email'))
    submit = SubmitField(trans('next'))

class Step2Form(FlaskForm):
    income = FloatField(trans('monthly_income'), validators=[DataRequired(message=trans('income_required')), NumberRange(min=0, max=10000000000, message=trans('income_max'))])
    submit = SubmitField(trans('next'))

class Step3Form(FlaskForm):
    housing = FloatField(trans('housing_rent'), validators=[DataRequired(message=trans('housing_required')), NumberRange(min=0, message=trans('amount_positive'))])
    food = FloatField(trans('food'), validators=[DataRequired(message=trans('food_required')), NumberRange(min=0, message=trans('amount_positive'))])
    transport = FloatField(trans('transport'), validators=[DataRequired(message=trans('transport_required')), NumberRange(min=0, message=trans('amount_positive'))])
    dependents = FloatField(trans('dependents_support'), validators=[DataRequired(message=trans('dependents_required')), NumberRange(min=0, message=trans('amount_positive'))])
    miscellaneous = FloatField(trans('miscellaneous'), validators=[DataRequired(message=trans('miscellaneous_required')), NumberRange(min=0, message=trans('amount_positive'))])
    others = FloatField(trans('others'), validators=[DataRequired(message=trans('others_required')), NumberRange(min=0, message=trans('amount_positive'))])
    submit = SubmitField(trans('next'))

class Step4Form(FlaskForm):
    savings_goal = FloatField(trans('savings_goal'), validators=[DataRequired(message=trans('savings_goal_required')), NumberRange(min=0, message=trans('amount_positive'))])
    submit = SubmitField(trans('submit'))

@budget_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    """Handle budget step 1 form (personal info)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step1Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['budget_step1'] = form.data
            logging.debug(f"Budget step1 form data: {form.data}")
            return redirect(url_for('budget.step2'))
        return render_template('budget_step1.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        logging.exception(f"Error in budget.step1: {str(e)}")
        flash(trans("error_personal_info", lang=lang), "danger")
        return render_template('budget_step1.html', form=form, trans=trans, lang=lang)

@budget_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    """Handle budget step 2 form (income)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step2Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['budget_step2'] = form.data
            logging.debug(f"Budget step2 form data: {form.data}")
            return redirect(url_for('budget.step3'))
        return render_template('budget_step2.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        logging.exception(f"Error in budget.step2: {str(e)}")
        flash(trans("error_income_invalid", lang=lang), "danger")
        return render_template('budget_step2.html', form=form, trans=trans, lang=lang)

@budget_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    """Handle budget step 3 form (expenses)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step3Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['budget_step3'] = form.data
            logging.debug(f"Budget step3 form data: {form.data}")
            return redirect(url_for('budget.step4'))
        return render_template('budget_step3.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        logging.exception(f"Error in budget.step3: {str(e)}")
        flash(trans("error_expenses_invalid", lang=lang), "danger")
        return render_template('budget_step3.html', form=form, trans=trans, lang=lang)

@budget_bp.route('/step4', methods=['GET', 'POST'])
def step4():
    """Handle budget step 4 form (savings goal) and calculate budget."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step4Form()
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
                    subject=trans("budget_plan_summary", lang=lang),
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
                    lang=lang
                )
            session.pop('budget_step1', None)
            session.pop('budget_step2', None)
            session.pop('budget_step3', None)
            flash(trans("budget_completed_success", lang=lang), "success")
            return redirect(url_for('budget.dashboard'))
        return render_template('budget_step4.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        logging.exception(f"Error in budget.step4: {str(e)}")
        flash(trans("budget_process_error", lang=lang), "danger")
        return render_template('budget_step4.html', form=form, trans=trans, lang=lang)

@budget_bp.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    """Display budget dashboard with delete functionality."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
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
                        flash(trans("budget_deleted_success", lang=lang), "success")
                    else:
                        flash(trans("budget_delete_failed", lang=lang), "danger")
                        logging.error(f"Failed to delete budget ID {budget_id}")
                    return redirect(url_for('budget.dashboard'))
                except Exception as e:
                    logging.exception(f"Error deleting budget item: {str(e)}")
                    flash(trans("budget_delete_error", lang=lang), "danger")
                    return redirect(url_for('budget.dashboard'))
        
        # Calculate insights and tips
        tips = [
            trans("tip_track_expenses", lang=lang),
            trans("tip_ajo_savings", lang=lang),
            trans("tip_data_subscriptions", lang=lang),
            trans("tip_plan_dependents", lang=lang)
        ]
        insights = []
        if latest_budget.get('surplus_deficit', 0) < 0:
            insights.append(trans("insight_budget_deficit", lang=lang))
        elif latest_budget.get('surplus_deficit', 0) > 0:
            insights.append(trans("insight_budget_surplus", lang=lang))
        if latest_budget.get('savings_goal', 0) == 0:
            insights.append(trans("insight_set_savings_goal", lang=lang))

        return render_template(
            'budget_dashboard.html',
            budgets=budgets,
            latest_budget=latest_budget,
            tips=tips,
            insights=insights,
            trans=trans,
            lang=lang
        )
    except Exception as e:
        logging.exception(f"Error in budget.dashboard: {str(e)}")
        flash(trans("dashboard_load_error", lang=lang), "danger")
        return render_template(
            'budget_dashboard.html',
            budgets=[],
            latest_budget={},
            tips=[
                trans("tip_track_expenses", lang=lang),
                trans("tip_ajo_savings", lang=lang),
                trans("tip_data_subscriptions", lang=lang),
                trans("tip_plan_dependents", lang=lang)
            ],
            insights=[],
            trans=trans,
            lang=lang
        )
