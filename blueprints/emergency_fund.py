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
    first_name = StringField(trans('emergency_fund_first_name'), validators=[DataRequired(message=trans('emergency_fund_first_name_required'))])
    email = StringField(trans('emergency_fund_email'), validators=[Optional(), Email(message=trans('emergency_fund_email_invalid'))])
    send_email = BooleanField(trans('emergency_fund_send_email'))
    monthly_expenses = FloatField(trans('emergency_fund_monthly_expenses'), validators=[DataRequired(message=trans('emergency_fund_monthly_expenses_required')), NumberRange(min=0, max=10000000000, message=trans('emergency_fund_expenses_range'))])
    submit = SubmitField(trans('emergency_fund_continue_to_savings'))

class Step2Form(FlaskForm):
    current_savings = FloatField(trans('emergency_fund_current_savings'), validators=[DataRequired(message=trans('emergency_fund_current_savings_required')), NumberRange(min=0, max=10000000000, message=trans('emergency_fund_savings_range'))])
    submit = SubmitField(trans('emergency_fund_calculate_emergency_fund'))

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
        flash(trans("emergency_fund_error_personal_info"), "danger")
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
                badges.append(trans("emergency_fund_badge_fund_master"))
            if current_savings >= target_savings_3m:
                badges.append(trans("emergency_fund_badge_fund_builder"))
            if current_savings > 0:
                badges.append(trans("emergency_fund_badge_savings_pro"))
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
                    subject=trans("emergency_fund_plan"),
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
            flash(trans("emergency_fund_emergency_fund_completed_success"), "success")
            return redirect(url_for('emergency_fund.dashboard'))
        return render_template('emergency_fund_step2.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        logging.exception(f"Error in emergency_fund.step2: {str(e)}")
        flash(trans("emergency_fund_emergency_fund_process_error"), "danger")
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
            trans("emergency_fund_tip_automate_savings"),
            trans("emergency_fund_tip_ajo_savings"),
            trans("emergency_fund_tip_track_expenses"),
            trans("emergency_fund_tip_monthly_savings_goals")
        ]
        if latest_record:
            if latest_record.get('savings_gap_6m', 0) > 0:
                insights.append(trans("emergency_fund_insight_below_6m_target"))
            if latest_record.get('current_savings', 0) == 0:
                insights.append(trans("emergency_fund_insight_no_savings"))
            if latest_record.get('current_savings', 0) >= latest_record.get('target_savings_6m', 0):
                insights.append(trans("emergency_fund_insight_6m_covered"))
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
        flash(trans("emergency_fund_dashboard_load_error"), "danger")
        return render_template(
            'emergency_fund_dashboard.html',
            records=[],
            latest_record={},
            insights=[],
            tips=[
                trans("emergency_fund_tip_automate_savings"),
                trans("emergency_fund_tip_ajo_savings"),
                trans("emergency_fund_tip_track_expenses"),
                trans("emergency_fund_tip_monthly_savings_goals")
            ],
            trans=trans,
            lang=lang
        )
