from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Email, ValidationError
from json_store import JsonStorage
from mailersend_email import send_email
from translations import trans
from datetime import datetime
import logging
import uuid
import traceback
import os

# Configure logging with immediate flush
logger = logging.getLogger('financial_health')
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler('data/storage.txt')
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - SessionID: %(session_id)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Add session ID to log context
class SessionAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        kwargs['extra'] = kwargs.get('extra', {})
        kwargs['extra']['session_id'] = session.get('sid', 'unknown')
        return msg, kwargs

log = SessionAdapter(logger, {})

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

    def validate_income(self, field):
        if field.data is not None:
            try:
                # Handle string input with commas
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data)
            except (ValueError, TypeError):
                log.error(f"Invalid income input: {field.data}")
                raise ValidationError('Income must be a valid number.')

    def validate_expenses(self, field):
        if field.data is not None:
            try:
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data)
            except (ValueError, TypeError):
                log.error(f"Invalid expenses input: {field.data}")
                raise ValidationError('Expenses must be a valid number.')

class Step3Form(FlaskForm):
    debt = FloatField('Total Debt', validators=[Optional(), NumberRange(min=0, max=10000000000, message='Debt cannot exceed ₦10 billion')])
    interest_rate = FloatField('Average Interest Rate', validators=[Optional(), NumberRange(min=0, message='Interest rate must be positive')])
    submit = SubmitField('Submit')

    def validate_debt(self, field):
        if field.data is not None:
            try:
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data) if cleaned_data else None
            except (ValueError, TypeError):
                log.error(f"Invalid debt input: {field.data}")
                raise ValidationError('Debt must be a valid number.')

    def validate_interest_rate(self, field):
        if field.data is not None:
            try:
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data) if cleaned_data else None
            except (ValueError, TypeError):
                log.error(f"Invalid interest rate input: {field.data}")
                raise ValidationError('Interest rate must be a valid number.')

@financial_health_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    """Handle financial health step 1 form (personal info)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step1Form()
    t_dict = trans('t')
    t = lambda key: t_dict.get(key, key)
    log.info(f"Starting step1 for session {session['sid']}")
    try:
        if request.method == 'POST':
            if not form.validate_on_submit():
                log.warning(f"Form validation failed: {form.errors}")
                flash(t("Please correct the errors in the form."), "danger")
                return render_template('health_score_step1.html', form=form, t=t)
            session['health_step1'] = form.data
            log.debug(f"Step1 form data: {form.data}")
            return redirect(url_for('financial_health.step2'))
        return render_template('health_score_step1.html', form=form, t=t)
    except Exception as e:
        log.exception(f"Error in step1: {str(e)}")
        flash(t("Error processing personal information. Please try again."), "danger")
        return render_template('health_score_step1.html', form=form, t=t), 500

@financial_health_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    """Handle financial health step 2 form (income and expenses)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step2Form()
    t_dict = trans('t')
    t = lambda key: t_dict.get(key, key)
    log.info(f"Starting step2 for session {session['sid']}")
    try:
        if request.method == 'POST':
            if not form.validate_on_submit():
                log.warning(f"Form validation failed: {form.errors}")
                flash(t("Please correct the errors in the form."), "danger")
                return render_template('health_score_step2.html', form=form, t=t)
            session['health_step2'] = {
                'income': float(form.income.data),
                'expenses': float(form.expenses.data),
                'submit': form.submit.data
            }
            log.debug(f"Step2 form data: {session['health_step2']}")
            return redirect(url_for('financial_health.step3'))
        return render_template('health_score_step2.html', form=form, t=t)
    except Exception as e:
        log.exception(f"Error in step2: {str(e)}")
        flash(t("Invalid numeric input for income or expenses."), "danger")
        return render_template('health_score_step2.html', form=form, t=t), 500

@financial_health_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    """Handle financial health step 3 form (debt and interest) and calculate score."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step3Form()
    t_dict = trans('t')
    t = lambda key: t_dict.get(key, key)
    log.info(f"Starting step3 for session {session['sid']}")
    try:
        if request.method == 'POST':
            if not form.validate_on_submit():
                log.warning(f"Form validation failed: {form.errors}")
                flash(t("Please correct the errors in the form."), "danger")
                return render_template('health_score_step3.html', form=form, t=t)

            # Extract and validate data
            data = {
                'debt': float(form.debt.data) if form.debt.data is not None else 0,
                'interest_rate': float(form.interest_rate.data) if form.interest_rate.data is not None else 0,
                'submit': form.submit.data
            }
            step1_data = session.get('health_step1', {})
            step2_data = session.get('health_step2', {})
            log.debug(f"Step1 data: {step1_data}")
            log.debug(f"Step2 data: {step2_data}")
            log.debug(f"Step3 form data: {data}")

            income = float(step2_data.get('income', 0) or 0)
            expenses = float(step2_data.get('expenses', 0) or 0)
            debt = data.get('debt', 0)
            interest_rate = data.get('interest_rate', 0)

            # Validate income to prevent division by zero
            if income <= 0:
                log.error("Income is zero or negative, cannot calculate financial health metrics")
                flash(t("Income must be greater than zero to calculate financial health."), "danger")
                return render_template('health_score_step3.html', form=form, t=t)

            # Calculate financial health metrics
            log.info("Calculating financial health metrics")
            try:
                debt_to_income = (debt / income * 100)
                savings_rate = ((income - expenses) / income * 100)
                interest_burden = interest_rate if debt > 0 else 0
            except ZeroDivisionError as zde:
                log.error(f"ZeroDivisionError during metric calculation: {str(zde)}")
                flash(t("Calculation error: Income cannot be zero."), "danger")
                return render_template('health_score_step3.html', form=form, t=t), 500

            # Financial health score (0-100)
            log.info("Calculating financial health score")
            score = 100
            if debt_to_income > 0:
                score -= min(debt_to_income, 50)
            if savings_rate < 0:
                score -= min(abs(savings_rate), 30)
            elif savings_rate > 0:
                score += min(savings_rate / 2, 20)
            score -= min(interest_burden, 20)
            score = max(0, min(100, round(score)))
            log.debug(f"Calculated score: {score}")

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
            log.debug(f"Status: {status}, Badges: {badges}")

            # Store record
            record = {
                "id": str(uuid.uuid4()),
                "session_id": session['sid'],
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
            log.info("Saving financial health record")
            try:
                financial_health_storage.append(record, user_email=step1_data.get('email'), session_id=session['sid'])
            except Exception as storage_error:
                log.error(f"Failed to save record to storage: {str(storage_error)}")
                flash(t("Error saving financial health data. Please try again."), "danger")
                return render_template('health_score_step3.html', form=form, t=t), 500

            # Send email if requested
            email = step1_data.get('email')
            send_email_flag = step1_data.get('send_email', False)
            if send_email_flag and email:
                log.info(f"Sending email to {email}")
                try:
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
                except Exception as email_error:
                    log.error(f"Failed to send email: {str(email_error)}")
                    flash(t("Financial health assessment completed, but email sending failed."), "warning")

            # Clear session
            session.pop('health_step1', None)
            session.pop('health_step2', None)
            log.info("Financial health assessment completed successfully")
            flash(t("Financial health assessment completed successfully."), "success")
            return redirect(url_for('financial_health.dashboard'))
        return render_template('health_score_step3.html', form=form, t=t)
    except Exception as e:
        log.exception(f"Unexpected error in step3: {str(e)}")
        flash(t("Unexpected error during financial health assessment. Please try again."), "danger")
        return render_template('health_score_step3.html', form=form, t=t), 500

@financial_health_bp.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    """Display financial health dashboard with comparison to others."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    t_dict = trans('t')
    t = lambda key: t_dict.get(key, key)
    log.info(f"Starting dashboard for session {session['sid']}")
    try:
        # Retrieve user-specific records with fallback
        try:
            user_data = financial_health_storage.filter_by_session(session['sid'])
        except Exception as storage_error:
            log.error(f"Failed to retrieve user data: {str(storage_error)}")
            user_data = []
        records = []
        for record in user_data:
            try:
                # Clean numeric fields
                data = record.get("data", {})
                for key in ['income', 'expenses', 'debt', 'interest_rate', 'score', 'debt_to_income', 'savings_rate', 'interest_burden']:
                    if key in data and isinstance(data[key], str):
                        try:
                            data[key] = float(data[key].replace(',', ''))
                        except (ValueError, TypeError):
                            log.warning(f"Invalid {key} in record {record.get('id')}: {data[key]}")
                            data[key] = 0
                records.append((record.get("id", str(uuid.uuid4())), data))
            except Exception as record_error:
                log.warning(f"Skipping invalid record: {str(record_error)}")
                continue
        latest_record = records[-1][1] if records else {}
        log.debug(f"Retrieved user records: {len(records)}")

        # Retrieve all records for comparison with fallback
        try:
            all_records = financial_health_storage.get_all()
        except Exception as storage_error:
            log.error(f"Failed to retrieve all records: {str(storage_error)}")
            all_records = []
        total_users = len(all_records)
        cleaned_records = []
        for record in all_records:
            try:
                data = record.get("data", {})
                for key in ['score', 'income', 'expenses', 'debt', 'interest_rate']:
                    if key in data and isinstance(data[key], str):
                        try:
                            data[key] = float(data[key].replace(',', ''))
                        except (ValueError, TypeError):
                            log.warning(f"Invalid {key} in record {record.get('id')}: {data[key]}")
                            data[key] = 0
                cleaned_records.append(record)
            except Exception as record_error:
                log.warning(f"Skipping invalid record for comparison: {str(record_error)}")
                continue
        log.debug(f"Total users: {total_users}")

        # Calculate rank and average score
        rank = total_users
        average_score = 0
        if cleaned_records and latest_record:
            try:
                sorted_records = sorted(
                    cleaned_records,
                    key=lambda x: x["data"].get("score", 0),
                    reverse=True
                )
                user_score = latest_record.get("score", 0)
                for i, record in enumerate(sorted_records, 1):
                    if record["data"].get("score", 0) <= user_score and record.get("session_id") == session['sid']:
                        rank = i
                        break
                scores = [record["data"].get("score", 0) for record in cleaned_records]
                average_score = sum(scores) / total_users if total_users > 0 else 0
                log.debug(f"User rank: {rank}, Average score: {average_score}")
            except Exception as calc_error:
                log.error(f"Error calculating rank or average score: {str(calc_error)}")
                rank = 0
                average_score = 0

        # Generate insights and tips
        insights = []
        tips = [
            t("Track expenses like data subscriptions and outings weekly."),
            t("Join an Ajo/Esusu/Adashe group for disciplined savings."),
            t("Pay off high-interest debts early to reduce interest burden."),
            t("Plan for recurring expenses like food and clothing.")
        ]
        if latest_record:
            try:
                if latest_record.get('debt_to_income', 0) > 40:
                    insights.append(t("High debt-to-income ratio. Consider reducing borrowings from friends or banks."))
                if latest_record.get('savings_rate', 0) < 0:
                    insights.append(t("Negative savings rate. Cut non-essential expenses like outings or subscriptions."))
                elif latest_record.get('savings_rate', 0) >= 20:
                    insights.append(t("Great savings rate! Explore investment options like Ajo or fixed deposits."))
                if latest_record.get('interest_burden', 0) > 10:
                    insights.append(t("High interest burden. Refinance or pay off high-interest loans."))
                if total_users >= 5:
                    if rank <= total_users * 0.1:
                        insights.append(t("You're in the top 10% of users! Keep up the excellent financial habits."))
                    elif rank <= total_users * 0.3:
                        insights.append(t("You're in the top 30%. Great work, aim for the top 10%!"))
                    else:
                        insights.append(t("You're below the top 30%. Try our Budgeting Basics course to improve your score."))
            except Exception as insight_error:
                log.error(f"Error generating insights: {str(insight_error)}")
                insights.append(t("Unable to generate insights due to data issues."))
        if total_users < 5:
            insights.append(t("Not enough users for comparison yet. Invite others to join!"))

        return render_template(
            'health_score_dashboard.html',
            records=records,
            latest_record=latest_record,
            insights=insights,
            tips=tips,
            rank=rank,
            total_users=total_users,
            average_score=average_score,
            t=t
        )
    except Exception as e:
        log.exception(f"Critical error in dashboard: {str(e)}")
        flash(t("Error loading dashboard. Please try again or contact support."), "danger")
        return render_template(
            'health_score_dashboard.html',
            records=[],
            latest_record={},
            insights=[t("No data available. Please complete the financial health assessment.")],
            tips=[],
            rank=0,
            total_users=0,
            average_score=0,
            t=t
        ), 500
