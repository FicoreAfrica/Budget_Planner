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

net_worth_bp = Blueprint('net_worth', __name__, url_prefix='/net_worth')
net_worth_storage = JsonStorage('data/networth.json')

# Forms for net worth steps
class Step1Form(FlaskForm):
    first_name = StringField(trans('net_worth_first_name'), validators=[DataRequired(message=trans('net_worth_first_name_required'))])
    email = StringField(trans('net_worth_email'), validators=[Optional(), Email(message=trans('net_worth_email_invalid'))])
    send_email = BooleanField(trans('net_worth_send_email'))
    submit = SubmitField(trans('net_worth_next'))

class Step2Form(FlaskForm):
    cash_savings = FloatField(trans('net_worth_cash_savings'), validators=[DataRequired(message=trans('net_worth_cash_savings_required')), NumberRange(min=0, max=10000000000, message=trans('net_worth_cash_savings_max'))])
    investments = FloatField(trans('net_worth_investments'), validators=[DataRequired(message=trans('net_worth_investments_required')), NumberRange(min=0, max=10000000000, message=trans('net_worth_investments_max'))])
    property = FloatField(trans('net_worth_property'), validators=[DataRequired(message=trans('net_worth_property_required')), NumberRange(min=0, max=10000000000, message=trans('net_worth_property_max'))])
    submit = SubmitField(trans('net_worth_next'))

class Step3Form(FlaskForm):
    loans = FloatField(trans('net_worth_loans'), validators=[Optional(), NumberRange(min=0, max=10000000000, message=trans('net_worth_loans_max'))])
    submit = SubmitField(trans('net_worth_submit'))

@net_worth_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    """Handle net worth step 1 form (personal info)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step1Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['net_worth_step1'] = form.data
            logging.debug(f"Net worth step1 form data: {form.data}")
            return redirect(url_for('net_worth.step2'))
        return render_template('net_worth_step1.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        logging.exception(f"Error in net_worth.step1: {str(e)}")
        flash(trans("net_worth_error_personal_info"), "danger")
        return render_template('net_worth_step1.html', form=form, trans=trans, lang=lang)

@net_worth_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    """Handle net worth step 2 form (assets)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step2Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['net_worth_step2'] = form.data
            logging.debug(f"Net worth step2 form data: {form.data}")
            return redirect(url_for('net_worth.step3'))
        return render_template('net_worth_step2.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        logging.exception(f"Error in net_worth.step2: {str(e)}")
        flash(trans("net_worth_error_assets_input"), "danger")
        return render_template('net_worth_step2.html', form=form, trans=trans, lang=lang)

@net_worth_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    """Handle net worth step 3 form (liabilities) and calculate net worth."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step3Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            data = form.data
            step1_data = session.get('net_worth_step1', {})
            step2_data = session.get('net_worth_step2', {})
            
            # Calculate assets and liabilities
            cash_savings = step2_data.get('cash_savings', 0)
            investments = step2_data.get('investments', 0)
            property = step2_data.get('property', 0)
            loans = data.get('loans', 0) or 0
            
            total_assets = cash_savings + investments + property
            total_liabilities = loans
            net_worth = total_assets - total_liabilities
            
            # Assign badges
            badges = []
            if net_worth > 0:
                badges.append(trans("net_worth_badge_wealth_builder"))
            if total_liabilities == 0:
                badges.append(trans("net_worth_badge_debt_free"))
            if cash_savings >= total_assets * 0.3:
                badges.append(trans("net_worth_badge_savings_champion"))
            if property >= total_assets * 0.5:
                badges.append(trans("net_worth_badge_property_mogul"))
            
            # Store record
            record = {
                "id": str(uuid.uuid4()),
                "data": {
                    "first_name": step1_data.get('first_name', ''),
                    "email": step1_data.get('email', ''),
                    "cash_savings": cash_savings,
                    "investments": investments,
                    "property": property,
                    "loans": loans,
                    "total_assets": total_assets,
                    "total_liabilities": total_liabilities,
                    "net_worth": net_worth,
                    "badges": badges,
                    "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }
            
            # Save and send email if requested
            email = step1_data.get('email')
            send_email_flag = step1_data.get('send_email', False)
            net_worth_storage.append(record, user_email=email, session_id=session['sid'])
            if send_email_flag and email:
                send_email(
                    to_email=email,
                    subject=trans("net_worth_net_worth_summary"),
                    template_name="net_worth_email.html",
                    data={
                        "first_name": record["data"]["first_name"],
                        "cash_savings": record["data"]["cash_savings"],
                        "investments": record["data"]["investments"],
                        "property": record["data"]["property"],
                        "loans": record["data"]["loans"],
                        "total_assets": record["data"]["total_assets"],
                        "total_liabilities": record["data"]["total_liabilities"],
                        "net_worth": record["data"]["net_worth"],
                        "badges": record["data"]["badges"],
                        "created_at": record["data"]["created_at"],
                        "cta_url": url_for('net_worth.dashboard', _external=True)
                    },
                    lang=lang
                )
            
            # Clear session
            session.pop('net_worth_step1', None)
            session.pop('net_worth_step2', None)
            flash(trans("net_worth_net_worth_completed_success"), "success")
            return redirect(url_for('net_worth.dashboard'))
        return render_template('net_worth_step3.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        logging.exception(f"Error in net_worth.step3: {str(e)}")
        flash(trans("net_worth_error_net_worth_calculation"), "danger")
        return render_template('net_worth_step3.html', form=form, trans=trans, lang=lang)

@net_worth_bp.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    """Display net worth dashboard."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    try:
        user_data = net_worth_storage.filter_by_session(session['sid'])
        records = [(record["id"], record["data"]) for record in user_data]
        latest_record = records[-1][1] if records else {}
        
        # Generate insights and tips
        insights = []
        tips = [
            trans("net_worth_tip_track_ajo"),
            trans("net_worth_tip_review_property"),
            trans("net_worth_tip_pay_loans_early"),
            trans("net_worth_tip_diversify_investments")
        ]
        if latest_record:
            if latest_record.get('total_liabilities', 0) > latest_record.get('total_assets', 0) * 0.5:
                insights.append(trans("net_worth_insight_high_loans"))
            if latest_record.get('cash_savings', 0) < latest_record.get('total_assets', 0) * 0.1:
                insights.append(trans("net_worth_insight_low_cash"))
            if latest_record.get('investments', 0) >= latest_record.get('total_assets', 0) * 0.3:
                insights.append(trans("net_worth_insight_strong_investments"))
            if latest_record.get('net_worth', 0) <= 0:
                insights.append(trans("net_worth_insight_negative_net_worth"))
        
        return render_template(
            'net_worth_dashboard.html',
            records=records,
            latest_record=latest_record,
            insights=insights,
            tips=tips,
            trans=trans,
            lang=lang
        )
    except Exception as e:
        logging.exception(f"Error in net_worth.dashboard: {str(e)}")
        flash(trans("net_worth_dashboard_load_error"), "danger")
        return render_template(
            'net_worth_dashboard.html',
            records=[],
            latest_record={},
            insights=[],
            tips=[
                trans("net_worth_tip_track_ajo"),
                trans("net_worth_tip_review_property"),
                trans("net_worth_tip_pay_loans_early"),
                trans("net_worth_tip_diversify_investments")
            ],
            trans=trans,
            lang=lang
        )
