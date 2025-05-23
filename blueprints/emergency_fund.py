from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Email
from json_store import JsonStorage
from mailersend_email import send_email
from datetime import datetime
import logging
import uuid
try:
    from app import trans  # Import trans from app.py instead
except ImportError:
    def trans(key, lang=None):
        return key  # Fallback to return the key as the translation
        
# Configure logging
logging.basicConfig(filename='data/storage.txt', level=logging.DEBUG)

emergency_fund_bp = Blueprint('emergency_fund', __name__)
emergency_fund_storage = JsonStorage('data/emergency_fund.json')

# Forms for emergency fund steps
class Step1Form(FlaskForm):
    first_name = StringField(trans('first_name'), validators=[DataRequired(message=trans('first_name_required'))])
    email = StringField(trans('email'), validators=[Optional(), Email(message=trans('email_invalid'))])
    send_email = BooleanField(trans('send_email'))
    monthly_expenses = FloatField(trans('monthly_expenses'), validators=[DataRequired(message=trans('monthly_expenses_required')), NumberRange(min=0, max=10000000000, message=trans('expenses_range'))])
    submit = SubmitField(trans('continue_to_savings'))

class Step2Form(FlaskForm):
    current_savings = FloatField(trans('current_savings'), validators=[DataRequired(message=trans('current_savings_required')), NumberRange(min=0, max=10000000000, message=trans('savings_range'))])
    submit = SubmitField(trans('calculate_emergency_fund'))

@emergency_fund_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    """Handle emergency fund step 1 form (personal info and expenses)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step1Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['emergency_fund_step1'] = form.data
            logging.debug(f"Emergency fund step1 form data: {form.data}")
            return redirect(url_for('emergency_fund.step2'))
        return render_template('emergency_fund_step1.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        logging.exception(f"Error in emergency_fund.step1: {str(e)}")
        flash(trans("error_personal_info", lang=lang), "danger")
        return render_template('emergency_fund_step1.html', form=form, trans=trans, lang=lang)

@emergency_fund_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    """Handle emergency fund step 2 form and calculate savings gap."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step2Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            step1_data = session.get('emergency_fund_step1', {})
            monthly_expenses = step1_data.get('monthly_expenses', 0)
            current_savings = form.current_savings.data
            # Calculate target savings for 3 and 6 months
            target_savings_3m = monthly_expenses * 3
            target_savings_6m = monthly_expenses * 6
            savings_gap_3m = max(0, target_savings_3m - current_savings)
            savings_gap_6m = max(0, target_savings_6m - current_savings)
            # Assign badges
            badges = []
            if current_savings >= target_savings_6m:
                badges.append(trans("badge_fund_master", lang=lang))
            if current_savings >= target_savings_3m:
                badges.append(trans("badge_fund_builder", lang=lang))
            if current_savings > 0:
                badges.append(trans("badge_savings_pro", lang=lang))
            # Store record
            record = {
                "id": str(uuid.uuid4()),
                "data": {
                    "first_name": step1_data.get('first_name', ''),
                    "email": step1_data.get('email', ''),
                    "send_email": step1_data.get('send_email', False),
                    "monthly_expenses": monthly_expenses,
                    "current_savings": current_savings,
                    "target_savings_3m": target_savings_3m,
                    "target_savings_6m": target_savings_6m,
                    "savings_gap_3m": savings_gap_3m,
                    "savings_gap_6m": savings_gap_6m,
                    "badges": badges,
                    "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }
            email = step1_data.get('email')
            send_email_flag = step1_data.get('send_email', False)
            emergency_fund_storage.append(record, user_email=email, session_id=session['sid'])
            # Send email if requested
            if send_email_flag and email:
                send_email(
                    to_email=email,
                    subject=trans("emergency_fund_plan", lang=lang),
                    template_name="emergency_fund_email.html",
                    data={
                        "first_name": record["data"]["first_name"],
                        "monthly_expenses": monthly_expenses,
                        "current_savings": current_savings,
                        "target_savings_3m": target_savings_3m,
                        "target_savings_6m": target_savings_6m,
                        "savings_gap_3m": savings_gap_3m,
                        "savings_gap_6m": savings_gap_6m,
                        "badges": badges,
                        "created_at": record["data"]["created_at"],
                        "cta_url": url_for('emergency_fund.dashboard', _external=True)
                    },
                    lang=lang
                )
            session.pop('emergency_fund_step1', None)
            flash(trans("emergency_fund_completed_success", lang=lang), "success")
            return redirect(url_for('emergency_fund.dashboard'))
        return render_template('emergency_fund_step2.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        logging.exception(f"Error in emergency_fund.step2: {str(e)}")
        flash(trans("emergency_fund_process_error", lang=lang), "danger")
        return render_template('emergency_fund_step2.html', form=form, trans=trans, lang=lang)

@emergency_fund_bp.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    """Display emergency fund dashboard."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    try:
        user_data = emergency_fund_storage.filter_by_session(session['sid'])
        records = [(record["id"], record["data"]) for record in user_data]
        latest_record = records[-1][1] if records else {}
        # Generate insights and tips
        insights = []
        tips = [
            trans("tip_automate_savings", lang=lang),
            trans("tip_ajo_savings", lang=lang),
            trans("tip_track_expenses", lang=lang),
            trans("tip_monthly_savings_goals", lang=lang)
        ]
        if latest_record:
            if latest_record.get('savings_gap_6m', 0) > 0:
                insights.append(trans("insight_below_6m_target", lang=lang))
            if latest_record.get('current_savings', 0) == 0:
                insights.append(trans("insight_no_savings", lang=lang))
            if latest_record.get('current_savings', 0) >= latest_record.get('target_savings_6m', 0):
                insights.append(trans("insight_6m_covered", lang=lang))
        return render_template(
            'emergency_fund_dashboard.html',
            records=records,
            latest_record=latest_record,
            insights=insights,
            tips=tips,
            trans=trans,
            lang=lang
        )
    except Exception as e:
        logging.exception(f"Error in emergency_fund.dashboard: {str(e)}")
        flash(trans("dashboard_load_error", lang=lang), "danger")
        return render_template(
            'emergency_fund_dashboard.html',
            records=[],
            latest_record={},
            insights=[],
            tips=[
                trans("tip_automate_savings", lang=lang),
                trans("tip_ajo_savings", lang=lang),
                trans("tip_track_expenses", lang=lang),
                trans("tip_monthly_savings_goals", lang=lang)
            ],
            trans=trans,
            lang=lang
        )
