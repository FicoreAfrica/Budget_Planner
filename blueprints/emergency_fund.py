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

emergency_fund_bp = Blueprint('emergency_fund', __name__)
emergency_fund_storage = JsonStorage('data/emergency_fund.json')

# Forms for emergency fund steps
class Step1Form(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(message='First name is required')])
    email = StringField('Email', validators=[Optional(), Email(message='Valid email is required')])
    send_email = BooleanField('Send Email')
    monthly_expenses = FloatField('Monthly Expenses', validators=[DataRequired(message='Monthly expenses are required'), NumberRange(min=0, max=10000000000, message='Expenses must be between ₦0 and ₦10 billion')])
    submit = SubmitField('Continue to Savings')

class Step2Form(FlaskForm):
    current_savings = FloatField('Current Savings', validators=[DataRequired(message='Current savings are required'), NumberRange(min=0, max=10000000000, message='Savings must be between ₦0 and ₦10 billion')])
    submit = SubmitField('Calculate Emergency Fund')

@emergency_fund_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    """Handle emergency fund step 1 form (personal info and expenses)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step1Form()
    t = trans('t')
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['emergency_fund_step1'] = form.data
            logging.debug(f"Emergency fund step1 form data: {form.data}")
            return redirect(url_for('emergency_fund.step2'))
        return render_template('emergency_fund_step1.html', form=form, t=t)
    except Exception as e:
        logging.exception(f"Error in emergency_fund.step1: {str(e)}")
        flash(t("Error processing personal information."), "danger")
        return render_template('emergency_fund_step1.html', form=form, t=t)

@emergency_fund_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    """Handle emergency fund step 2 form and calculate savings gap."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step2Form()
    t = trans('t')
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
                badges.append("Fund Master")
            if current_savings >= target_savings_3m:
                badges.append("Fund Builder")
            if current_savings > 0:
                badges.append("Savings Pro")
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
                    subject=t("Your Emergency Fund Plan"),
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
                    lang=session.get('lang', 'en')
                )
            session.pop('emergency_fund_step1', None)
            flash(t("Emergency fund plan completed successfully."), "success")
            return redirect(url_for('emergency_fund.dashboard'))
        return render_template('emergency_fund_step2.html', form=form, t=t)
    except Exception as e:
        logging.exception(f"Error in emergency_fund.step2: {str(e)}")
        flash(t("Error processing emergency fund plan."), "danger")
        return render_template('emergency_fund_step2.html', form=form, t=t)

@emergency_fund_bp.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    """Display emergency fund dashboard."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    t = trans('t')
    try:
        user_data = emergency_fund_storage.filter_by_session(session['sid'])
        records = [(record["id"], record["data"]) for record in user_data]
        latest_record = records[-1][1] if records else {}
        # Generate insights and tips
        insights = []
        tips = [
            t("Use apps like PiggyVest or Cowrywise to automate savings."),
            t("Join Ajo/Esusu/Adashe groups for disciplined saving habits."),
            t("Track expenses weekly using Moniepoint or Flowdiary."),
            t("Set small monthly savings goals to build your fund.")
        ]
        if latest_record:
            if latest_record.get('savings_gap_6m', 0) > 0:
                insights.append(t("Your savings are below the 6-month target. Consider using Cowrywise to automate savings."))
            if latest_record.get('current_savings', 0) == 0:
                insights.append(t("No emergency savings yet. Start with small contributions via Ajo/Esusu/Adashe."))
            if latest_record.get('current_savings', 0) >= latest_record.get('target_savings_6m', 0):
                insights.append(t("Excellent! Your fund covers 6 months of expenses. Maintain or grow it with PiggyVest."))
        return render_template(
            'emergency_fund_dashboard.html',
            records=records,
            latest_record=latest_record,
            insights=insights,
            tips=tips,
            t=t
        )
    except Exception as e:
        logging.exception(f"Error in emergency_fund.dashboard: {str(e)}")
        flash(t("Error loading emergency fund dashboard."), "danger")
        return render_template(
            'emergency_fund_dashboard.html',
            records=[],
            latest_record={},
            insights=[],
            tips=[],
            t=t
        )
