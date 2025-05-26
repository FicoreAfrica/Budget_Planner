from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Email
from json_store import JsonStorage
from mailersend_email import send_email
from datetime import datetime
import logging
import uuid
try:
    from app import trans
except ImportError:
    def trans(key, lang=None):
        return key

# Configure logging
logging.basicConfig(filename='data/storage.txt', level=logging.DEBUG)

budget_bp = Blueprint('budget', __name__, url_prefix='/budget')

def init_budget_storage(app):
    """Initialize budget_storage within app context."""
    with app.app_context():
        return JsonStorage('data/budget.json', logger_instance=app.logger)

def strip_commas(value):
    if isinstance(value, str):
        return value.replace(',', '')
    return value

class Step1Form(FlaskForm):
    first_name = StringField(trans('budget_first_name'), validators=[DataRequired(message=trans('budget_first_name_required'))])
    email = StringField(trans('budget_email'), validators=[Optional(), Email(message=trans('budget_email_invalid'))])
    send_email = BooleanField(trans('budget_send_email'))
    submit = SubmitField(trans('budget_next'))

class Step2Form(FlaskForm):
    income = FloatField(
        trans('budget_monthly_income'),
        validators=[
            DataRequired(message=trans('budget_income_required')),
            NumberRange(min=0, max=10000000000, message=trans('budget_income_max'))
        ],
        filters=[strip_commas]
    )
    submit = SubmitField(trans('budget_next'))

class Step3Form(FlaskForm):
    housing = FloatField(
        trans('budget_housing_rent'),
        validators=[DataRequired(message=trans('budget_housing_required')), NumberRange(min=0, message=trans('budget_amount_positive'))],
        filters=[strip_commas]
    )
    food = FloatField(
        trans('budget_food'),
        validators=[DataRequired(message=trans('budget_food_required')), NumberRange(min=0, message=trans('budget_amount_positive'))],
        filters=[strip_commas]
    )
    transport = FloatField(
        trans('budget_transport'),
        validators=[DataRequired(message=trans('budget_transport_required')), NumberRange(min=0, message=trans('budget_amount_positive'))],
        filters=[strip_commas]
    )
    dependents = FloatField(
        trans('budget_dependents_support'),
        validators=[DataRequired(message=trans('budget_dependents_required')), NumberRange(min=0, message=trans('budget_amount_positive'))],
        filters=[strip_commas]
    )
    miscellaneous = FloatField(
        trans('budget_miscellaneous'),
        validators=[DataRequired(message=trans('budget_miscellaneous_required')), NumberRange(min=0, message=trans('budget_amount_positive'))],
        filters=[strip_commas]
    )
    others = FloatField(
        trans('budget_others'),
        validators=[DataRequired(message=trans('budget_others_required')), NumberRange(min=0, message=trans('budget_amount_positive'))],
        filters=[strip_commas]
    )
    submit = SubmitField(trans('budget_next'))

class Step4Form(FlaskForm):
    savings_goal = FloatField(
        trans('budget_savings_goal'),
        validators=[DataRequired(message=trans('budget_savings_goal_required')), NumberRange(min=0, message=trans('budget_amount_positive'))],
        filters=[strip_commas]
    )
    submit = SubmitField(trans('budget_submit'))

@budget_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step1Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['budget_step1'] = form.data
            current_app.logger.debug(f"Budget step1 form data: {form.data}")
            return redirect(url_for('budget.step2'))
        return render_template('budget_step1.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in budget.step1: {str(e)}")
        flash(trans("budget_error_personal_info"), "danger")
        return render_template('budget_step1.html', form=form, trans=trans, lang=lang)

@budget_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step2Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['budget_step2'] = form.data
            current_app.logger.debug(f"Budget step2 form data: {form.data}")
            return redirect(url_for('budget.step3'))
        return render_template('budget_step2.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in budget.step2: {str(e)}")
        flash(trans("budget_error_income_invalid"), "danger")
        return render_template('budget_step2.html', form=form, trans=trans, lang=lang)

@budget_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step3Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['budget_step3'] = form.data
            current_app.logger.debug(f"Budget step3 form data: {form.data}")
            return redirect(url_for('budget.step4'))
        return render_template('budget_step3.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in budget.step3: {str(e)}")
        flash(trans("budget_error_expenses_invalid"), "danger")
        return render_template('budget_step3.html', form=form, trans=trans, lang=lang)

@budget_bp.route('/step4', methods=['GET', 'POST'])
def step4():
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
            budget_storage = current_app.config['STORAGE_MANAGERS']['budget']
            budget_storage.append(record, user_email=email, session_id=session['sid'])
            if send_email_flag and email:
                send_email(
                    to_email=email,
                    subject=trans("budget_plan_summary"),
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
            flash(trans("budget_budget_completed_success"), "success")
            return redirect(url_for('budget.dashboard'))
        return render_template('budget_step4.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in budget.step4: {str(e)}")
        flash(trans("budget_budget_process_error"), "danger")
        return render_template('budget_step4.html', form=form, trans=trans, lang=lang)

@budget_bp.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    try:
        budget_storage = current_app.config['STORAGE_MANAGERS']['budget']
        user_data = budget_storage.filter_by_session(session['sid'])
        budgets = [(record["id"], record["data"]) for record in user_data]
        latest_budget = budgets[-1][1] if budgets else {}

        if request.method == 'POST':
            action = request.form.get('action')
            budget_id = request.form.get('budget_id')

            if action == 'delete':
                try:
                    if budget_storage.delete_by_id(budget_id):
                        flash(trans("budget_budget_deleted_success"), "success")
                    else:
                        flash(trans("budget_budget_delete_failed"), "danger")
                        current_app.logger.error(f"Failed to delete budget ID {budget_id}")
                    return redirect(url_for('budget.dashboard'))
                except Exception as e:
                    current_app.logger.exception(f"Error deleting budget item: {str(e)}")
                    flash(trans("budget_budget_delete_error"), "danger")
                    return redirect(url_for('budget.dashboard'))

        tips = [
            trans("budget_tip_track_expenses"),
            trans("budget_tip_ajo_savings"),
            trans("budget_tip_data_subscriptions"),
            trans("budget_tip_plan_dependents")
        ]
        insights = []
        if latest_budget.get('surplus_deficit', 0) < 0:
            insights.append(trans("budget_insight_budget_deficit"))
        elif latest_budget.get('surplus_deficit', 0) > 0:
            insights.append(trans("budget_insight_budget_surplus"))
        if latest_budget.get('savings_goal', 0) == 0:
            insights.append(trans("budget_insight_set_savings_goal"))

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
        current_app.logger.exception(f"Error in budget.dashboard: {str(e)}")
        flash(trans("budget_dashboard_load_error"), "danger")
        return render_template(
            'budget_dashboard.html',
            budgets=[],
            latest_budget={},
            tips=[
                trans("budget_tip_track_expenses"),
                trans("budget_tip_ajo_savings"),
                trans("budget_tip_data_subscriptions"),
                trans("budget_tip_plan_dependents")
            ],
            insights=[],
            trans=trans,
            lang=lang
        )
