from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Email
from json_store import JsonStorage
from mailersend_email import send_email
from translations import trans
from datetime import datetime
import logging
import uuid

# Configure logging
logging.basicConfig(filename='data/storage.txt', level=logging.DEBUG)

financial_health_bp = Blueprint('financial_health', __name__)
financial_health_storage = JsonStorage('data/financial_health.json')

# Forms for financial health steps
class Step1Form(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(message='First name is required')])
    email = StringField('Email', validators=[Optional(), Email(message='Valid email is required')])
    user_type = SelectField('User Type', choices=[('individual', 'Individual'), ('business', 'Business')])
    send_email = BooleanField('Send Email')
    submit = SubmitField('Next')

class Step2Form(FlaskForm):
    income = FloatField('Monthly Income', validators=[DataRequired(message='Income is required'), NumberRange(min=0, max=10000000000, message='Income cannot exceed ₦10 billion')])
    expenses = FloatField('Monthly Expenses', validators=[DataRequired(message='Expenses are required'), NumberRange(min=0, max=10000000000, message='Expenses cannot exceed ₦10 billion')])
    submit = SubmitField('Next')

class Step3Form(FlaskForm):
    debt = FloatField('Total Debt', validators=[Optional(), NumberRange(min=0, max=10000000000, message='Debt cannot exceed ₦10 billion')])
    interest_rate = FloatField('Average Interest Rate', validators=[Optional(), NumberRange(min=0, message='Interest rate must be positive')])
    submit = SubmitField('Submit')

@financial_health_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    """Handle financial health step 1 form (personal info)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step1Form()
    t = trans('t')
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['health_step1'] = form.data
            logging.debug(f"Financial health step1 form data: {form.data}")
            return redirect(url_for('financial_health.step2'))
        return render_template('health_score_step1.html', form=form, t=t)
    except Exception as e:
        logging.exception(f"Error in financial_health.step1: {str(e)}")
        flash(t("Error processing personal information."), "danger")
        return render_template('health_score_step1.html', form=form, t=t)

@financial_health_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    """Handle financial health step 2 form (income and expenses)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step2Form()
    t = trans('t')
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['health_step2'] = form.data
            logging.debug(f"Financial health step2 form data: {form.data}")
            return redirect(url_for('financial_health.step3'))
        return render_template('health_score_step2.html', form=form, t=t)
    except Exception as e:
        logging.exception(f"Error in financial_health.step2: {str(e)}")
        flash(t("Invalid numeric input for income or expenses."), "danger")
        return render_template('health_score_step2.html', form=form, t=t)

@financial_health_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    """Handle financial health step 3 form (debt and interest) and calculate score."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step3Form()
    t = trans('t')
    try:
        if request.method == 'POST' and form.validate_on_submit():
            data = form.data
            step1_data = session.get('health_step1', {})
            step2_data = session.get('health_step2', {})
            income = step2_data.get('income', 0)
            expenses = step2_data.get('expenses', 0)
            debt = data.get('debt', 0) or 0
            interest_rate = data.get('interest_rate', 0) or 0

            # Calculate financial health metrics
            debt_to_income = (debt / income * 100) if income > 0 else 0
            savings_rate = ((income - expenses) / income * 100) if income > 0 else 0
            interest_burden = interest_rate if debt > 0 else 0

            # Financial health score (0-100)
            score = 100
            if debt_to_income > 0:
                score -= min(debt_to_income, 50)  # High debt-to-income reduces score
            if savings_rate < 0:
                score -= min(abs(savings_rate), 30)  # Negative savings rate penalizes
            elif savings_rate > 0:
                score += min(savings_rate / 2, 20)  # Positive savings boosts score
            score -= min(interest_burden, 20)  # High interest burden penalizes
            score = max(0, min(100, round(score)))

            # Status and badges
            status = ("Excellent" if score >= 80 else
                     "Good" if score >= 60 else
                     "Needs Improvement")
            badges = []
            if score >= 80:
                badges.append("Financial Star")
            if debt_to_income < 20:
                badges.append("Debt Manager")
            if savings_rate >= 20:
                badges.append("Savings Pro")
            if interest_burden == 0 and debt > 0:
                badges.append("Interest-Free Borrower")

            # Store record
            record = {
                "id": str(uuid.uuid4()),
                "data": {
                    "first_name": step1_data.get('first_name', ''),
                    "email": step1_data.get('email', ''),
                    "user_type": step1_data.get('user_type', 'individual'),
                    "income": income,
                    "expenses": expenses,
                    "debt": debt,
                    "interest_rate": interest_rate,
                    "debt_to_income": debt_to_income,
                    "savings_rate": savings_rate,
                    "interest_burden": interest_burden,
                    "score": score,
                    "status": status,
                    "badges": badges,
                    "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }

            # Save and send email if requested
            email = step1_data.get('email')
            send_email_flag = step1_data.get('send_email', False)
            financial_health_storage.append(record, user_email=email, session_id=session['sid'])
            if send_email_flag and email:
                send_email(
                    to_email=email,
                    subject=t("Your Financial Health Report"),
                    template_name="health_score_email.html",
                    data={
                        "first_name": record["data"]["first_name"],
                        "score": record["data"]["score"],
                        "status": record["data"]["status"],
                        "income": record["data"]["income"],
                        "expenses": record["data"]["expenses"],
                        "debt": record["data"]["debt"],
                        "interest_rate": record["data"]["interest_rate"],
                        "debt_to_income": record["data"]["debt_to_income"],
                        "savings_rate": record["data"]["savings_rate"],
                        "interest_burden": record["data"]["interest_burden"],
                        "badges": record["data"]["badges"],
                        "created_at": record["data"]["created_at"],
                        "cta_url": url_for('financial_health.dashboard', _external=True)
                    },
                    lang=session.get('lang', 'en')
                )

            # Clear session
            session.pop('health_step1', None)
            session.pop('health_step2', None)
            flash(t("Financial health assessment completed successfully."), "success")
            return redirect(url_for('financial_health.dashboard'))
        return render_template('health_score_step3.html', form=form, t=t)
    except Exception as e:
        logging.exception(f"Error in financial_health.step3: {str(e)}")
        flash(t("Error processing financial health assessment."), "danger")
        return render_template('health_score_step3.html', form=form, t=t)

@financial_health_bp.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    """Display financial health dashboard."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    t = trans('t')
    try:
        user_data = financial_health_storage.filter_by_session(session['sid'])
        records = [(record["id"], record["data"]) for record in user_data]
        latest_record = records[-1][1] if records else {}

        # Generate insights and tips
        insights = []
        tips = [
            t("Track expenses like data subscriptions and outings weekly."),
            t("Join an Ajo/Esusu/Adashe group for disciplined savings."),
            t("Pay off high-interest debts early to reduce interest burden."),
            t("Plan for recurring expenses like food and clothing.")
        ]
        if latest_record:
            if latest_record.get('debt_to_income', 0) > 40:
                insights.append(t("High debt-to-income ratio. Consider reducing borrowings from friends or banks."))
            if latest_record.get('savings_rate', 0) < 0:
                insights.append(t("Negative savings rate. Cut non-essential expenses like outings or subscriptions."))
            elif latest_record.get('savings_rate', 0) >= 20:
                insights.append(t("Great savings rate! Explore investment options like Ajo or fixed deposits."))
            if latest_record.get('interest_burden', 0) > 10:
                insights.append(t("High interest burden. Refinance or pay off high-interest loans."))

        return render_template(
            'health_score_dashboard.html',
            records=records,
            latest_record=latest_record,
            insights=insights,
            tips=tips,
            t=t
        )
    except Exception as e:
        logging.exception(f"Error in financial_health.dashboard: {str(e)}")
        flash(t("Error loading dashboard."), "danger")
        return render_template(
            'health_score_dashboard.html',
            records=[],
            latest_record={},
            insights=[],
            tips=[],
            t=t
        )
