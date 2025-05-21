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

net_worth_bp = Blueprint('net_worth', __name__)
net_worth_storage = JsonStorage('data/networth.json')

# Forms for net worth steps
class Step1Form(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(message='First name is required')])
    email = StringField('Email', validators=[Optional(), Email(message='Valid email is required')])
    send_email = BooleanField('Send Email')
    submit = SubmitField('Next')

class Step2Form(FlaskForm):
    cash_savings = FloatField('Cash & Savings', validators=[DataRequired(message='Cash & Savings is required'), NumberRange(min=0, max=10000000000, message='Cash & Savings cannot exceed ₦10 billion')])
    investments = FloatField('Investments', validators=[DataRequired(message='Investments is required'), NumberRange(min=0, max=10000000000, message='Investments cannot exceed ₦10 billion')])
    property = FloatField('Physical Property', validators=[DataRequired(message='Physical Property is required'), NumberRange(min=0, max=10000000000, message='Physical Property cannot exceed ₦10 billion')])
    submit = SubmitField('Next')

class Step3Form(FlaskForm):
    loans = FloatField('Loans', validators=[Optional(), NumberRange(min=0, max=10000000000, message='Loans cannot exceed ₦10 billion')])
    submit = SubmitField('Submit')

@net_worth_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    """Handle net worth step 1 form (personal info)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step1Form()
    t = trans('t')
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['net_worth_step1'] = form.data
            logging.debug(f"Net worth step1 form data: {form.data}")
            return redirect(url_for('net_worth.step2'))
        return render_template('net_worth_step1.html', form=form, t=t)
    except Exception as e:
        logging.exception(f"Error in net_worth.step1: {str(e)}")
        flash(t("Error processing personal information."), "danger")
        return render_template('net_worth_step1.html', form=form, t=t)

@net_worth_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    """Handle net worth step 2 form (assets)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step2Form()
    t = trans('t')
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['net_worth_step2'] = form.data
            logging.debug(f"Net worth step2 form data: {form.data}")
            return redirect(url_for('net_worth.step3'))
        return render_template('net_worth_step2.html', form=form, t=t)
    except Exception as e:
        logging.exception(f"Error in net_worth.step2: {str(e)}")
        flash(t("Invalid numeric input for assets."), "danger")
        return render_template('net_worth_step2.html', form=form, t=t)

@net_worth_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    """Handle net worth step 3 form (liabilities) and calculate net worth."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step3Form()
    t = trans('t')
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
                badges.append("Wealth Builder")
            if total_liabilities == 0:
                badges.append("Debt Free")
            if cash_savings >= total_assets * 0.3:
                badges.append("Savings Champion")
            if property >= total_assets * 0.5:
                badges.append("Property Mogul")
            
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
                    subject=t("Your Net Worth Summary"),
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
                    lang=session.get('lang', 'en')
                )
            
            # Clear session
            session.pop('net_worth_step1', None)
            session.pop('net_worth_step2', None)
            flash(t("Net worth calculation completed successfully."), "success")
            return redirect(url_for('net_worth.dashboard'))
        return render_template('net_worth_step3.html', form=form, t=t)
    except Exception as e:
        logging.exception(f"Error in net_worth.step3: {str(e)}")
        flash(t("Error processing net worth calculation."), "danger")
        return render_template('net_worth_step3.html', form=form, t=t)

@net_worth_bp.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    """Display net worth dashboard."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    t = trans('t')
    try:
        user_data = net_worth_storage.filter_by_session(session['sid'])
        records = [(record["id"], record["data"]) for record in user_data]
        latest_record = records[-1][1] if records else {}
        
        # Generate insights and tips
        insights = []
        tips = [
            t("Track your Ajo/Esusu/Adashe contributions monthly."),
            t("Review property values periodically with local experts."),
            t("Pay off mobile money loans early to avoid high interest."),
            t("Diversify investments beyond farming for stability.")
        ]
        if latest_record:
            if latest_record.get('total_liabilities', 0) > latest_record.get('total_assets', 0) * 0.5:
                insights.append(t("High loans relative to assets. Consider reducing borrowings from OPay or GT Bank."))
            if latest_record.get('cash_savings', 0) < latest_record.get('total_assets', 0) * 0.1:
                insights.append(t("Low cash reserves. Increase savings through Ajo/Esusu/Adashe for liquidity."))
            if latest_record.get('investments', 0) >= latest_record.get('total_assets', 0) * 0.3:
                insights.append(t("Strong investment portfolio! Explore more options like cooperative schemes."))
            if latest_record.get('net_worth', 0) <= 0:
                insights.append(t("Negative or zero net worth. Focus on reducing loans and building assets."))
        
        return render_template(
            'net_worth_dashboard.html',
            records=records,
            latest_record=latest_record,
            insights=insights,
            tips=tips,
            t=t
        )
    except Exception as e:
        logging.exception(f"Error in net_worth.dashboard: {str(e)}")
        flash(t("Error loading dashboard."), "danger")
        return render_template(
            'net_worth_dashboard.html',
            records=[],
            latest_record={},
            insights=[],
            tips=[],
            t=t
        )
