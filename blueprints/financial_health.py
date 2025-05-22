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

# Configure logging
logger = logging.getLogger('financial_health')
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - SessionID: %(session_id)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler('data/storage.txt')
file_handler.setLevel(logging.DEBUG)
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
            log.debug(f"Received POST data: {request.form}")
            if not form.validate_on_submit():
                log.warning(f"Form validation failed: {form.errors}")
                flash(t("Please correct the errors in the form."), "danger")
                return render_template('health_score_step1.html', form=form, t=t)
            
            form_data = form.data.copy()
            if form_data.get('email') and not isinstance(form_data['email'], str):
                log.error(f"Invalid email type: {type(form_data['email'])}")
                raise ValueError("Email must be a string")
            session['health_step1'] = form_data
            log.debug(f"Validated form data: {form_data}")

            try:
                storage_data = {
                    'step': 1,
                    'data': form_data
                }
                record_id = financial_health_storage.append(storage_data, user_email=form_data.get('email'), session_id=session['sid'])
                if record_id:
                    log.info(f"Step1 form data appended to storage with record ID {record_id} for session {session['sid']}")
                else:
                    log.error("Failed to append Step1 data to storage")
                    flash(t("Error saving data. Please try again."), "danger")
                    return render_template('health_score_step1.html', form=form, t=t), 500
            except Exception as storage_error:
                log.exception(f"Failed to append to JSON storage: {str(storage_error)}")
                flash(t("Error saving data. Please try again."), "danger")
                return render_template('health_score_step1.html', form=form, t=t), 500

            log.debug(f"Step1 form data saved to session: {form_data}")
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
            try:
                storage_data = {
                    'step': 2,
                    'data': session['health_step2']
                }
                record_id = financial_health_storage.append(storage_data, session_id=session['sid'])
                if record_id:
                    log.info(f"Step2 form data appended to storage with record ID {record_id} for session {session['sid']}")
                else:
                    log.error("Failed to append Step2 data to storage")
                    flash(t("Error saving data. Please try again."), "danger")
                    return render_template('health_score_step2.html', form=form, t=t), 500
            except Exception as storage_error:
                log.exception(f"Failed to append to JSON storage: {str(storage_error)}")
                flash(t("Error saving data. Please try again."), "danger")
                return render_template('health_score_step2.html', form=form, t=t), 500

            log.debug(f"Step2 form data saved to session: {session['health_step2']}")
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

            if income <= 0:
                log.error("Income is zero or negative, cannot calculate financial health metrics")
                flash(t("Income must be greater than zero to calculate financial health."), "danger")
                return render_template('health_score_step3.html', form=form, t=t), 500

            log.info("Calculating financial health metrics")
            try:
                debt_to_income = (debt / income * 100)
                savings_rate = ((income - expenses) / income * 100)
                interest_burden = (interest_rate * debt / 100) if debt > 0 else 0
            except ZeroDivisionError as zde:
                log.error(f"ZeroDivisionError during metric calculation: {str(zde)}")
                flash(t("Calculation error: Income cannot be zero."), "danger")
                return render_template('health_score_step3.html', form=form, t=t), 500

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

            record = {
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
            session['health_record'] = record
            try:
                storage_data = {
                    'step': 3,
                    'data': record
                }
                record_id = financial_health_storage.append(storage_data, user_email=step1_data.get('email'), session_id=session['sid'])
                if record_id:
                    log.info(f"Step3 final record appended to storage with record ID {record_id} for session {session['sid']}")
                else:
                    log.error("Failed to append Step3 final record to storage")
                    flash(t("Error saving final record. Please try again."), "danger")
                    return render_template('health_score_step3.html', form=form, t=t), 500
            except Exception as storage_error:
                log.exception(f"Failed to append to JSON storage: {str(storage_error)}")
                flash(t("Error saving final record. Please try again."), "danger")
                return render_template('health_score_step3.html', form=form, t=t), 500

            log.debug(f"Session contents after save: {dict(session)}")

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
                            "first_name": record["first_name"],
                            "score": record["score"],
                            "status": record["status"],
                            "income": record["income"],
                            "expenses": record["expenses"],
                            "debt": record["debt"],
                            "interest_rate": record["interest_rate"],
                            "debt_to_income": record["debt_to_income"],
                            "savings_rate": record["savings_rate"],
                            "interest_burden": record["interest_burden"],
                            "badges": record["badges"],
                            "created_at": record["created_at"],
                            "cta_url": url_for('financial_health.dashboard', _external=True)
                        },
                        lang=session.get('lang', 'en')
                    )
                except Exception as email_error:
                    log.error(f"Failed to send email: {str(email_error)}")
                    flash(t("Financial health assessment completed, but email sending failed."), "warning")

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
        # Retrieve user-specific record from session or storage
        health_record = session.get('health_record', {})
        log.debug(f"Session health_record: {health_record}")
        if not health_record:
            stored_records = financial_health_storage.filter_by_session(session['sid'])
            log.debug(f"Stored records: {stored_records}")
            if not stored_records:
                log.warning("No records found for this session in storage")
                latest_record = {}
                records = []
            else:
                # Find the latest record (prioritize step 3 if present)
                final_record = None
                for record in sorted(stored_records, key=lambda x: x['timestamp'], reverse=True):
                    if record['data'].get('step') == 3:
                        final_record = record
                        break
                if not final_record:
                    final_record = stored_records[-1]
                    log.warning("No step 3 record found, using latest record")
                # Handle both old and new structures
                if 'step' in final_record['data']:
                    latest_record = final_record['data'].get('data', {})
                else:
                    latest_record = final_record['data']
                # Validate required fields
                required_fields = ['score', 'income', 'expenses', 'debt', 'interest_rate', 'debt_to_income', 'savings_rate']
                for field in required_fields:
                    if field not in latest_record:
                        log.warning(f"Missing field '{field}' in latest record: {latest_record}")
                        latest_record[field] = 0
                    elif not isinstance(latest_record[field], (int, float)):
                        log.warning(f"Invalid type for '{field}' in latest record: {type(latest_record[field])}, setting to 0")
                        latest_record[field] = 0
                records = [(final_record['id'], latest_record)]
                log.debug(f"Retrieved user records: {records}")
        else:
            latest_record = health_record
            for field in required_fields:
                if field not in latest_record:
                    log.warning(f"Missing field '{field}' in session health_record: {latest_record}")
                    latest_record[field] = 0
                elif not isinstance(latest_record[field], (int, float)):
                    log.warning(f"Invalid type for '{field}' in session health_record: {type(latest_record[field])}, setting to 0")
                    latest_record[field] = 0
            records = [(str(uuid.uuid4()), latest_record)]
            log.debug(f"Retrieved user records from session: {records}")

        # Retrieve all records for comparison
        all_records = financial_health_storage._read()
        log.debug(f"All records from storage: {all_records}")
        total_users = len(all_records)
        cleaned_records = []
        for record in all_records:
            try:
                if record['data'].get('step') != 3 and 'step' in record['data']:
                    continue
                data = record['data'].get('data', record['data'])
                for key in ['score', 'income', 'expenses', 'debt', 'interest_rate']:
                    if key in data and isinstance(data[key], (str, type(None))):
                        try:
                            data[key] = float(data[key].replace(',', '')) if isinstance(data[key], str) else 0
                        except (ValueError, TypeError) as ve:
                            log.warning(f"Invalid {key} in record {record.get('id')}: {data[key]}, setting to 0")
                            data[key] = 0
                if 'step' in record['data']:
                    record['data']['data'] = data
                else:
                    record['data'] = data
                cleaned_records.append(record)
            except Exception as record_error:
                log.warning(f"Skipping invalid record for comparison: {str(record_error)}")
                continue
        log.debug(f"Cleaned records: {cleaned_records}")
        log.debug(f"Total users: {total_users}, Final records: {len(cleaned_records)}")

        # Calculate rank and average score
        rank = len(cleaned_records) if cleaned_records else 1
        average_score = 0
        if cleaned_records and latest_record.get('score', 0):
            try:
                sorted_records = sorted(
                    cleaned_records,
                    key=lambda x: x["data"].get("data", {}).get("score", 0) if 'step' in x['data'] else x["data"].get("score", 0),
                    reverse=True
                )
                user_score = latest_record.get("score", 0)
                for i, record in enumerate(sorted_records, 1):
                    score = record["data"].get("data", {}).get("score", 0) if 'step' in record['data'] else record["data"].get("score", 0)
                    if score <= user_score and record.get("session_id") == session['sid']:
                        rank = i
                        break
                scores = [record["data"].get("data", {}).get("score", 0) for record in cleaned_records if record["data"].get("data", {}).get("score", 0) > 0] + \
                         [record["data"].get("score", 0) for record in cleaned_records if record["data"].get("score", 0) > 0 and 'step' not in record['data']]
                average_score = sum(scores) / len(scores) if scores else 0
                log.debug(f"User rank: {rank}, Average score: {average_score}")
            except Exception as calc_error:
                log.error(f"Error calculating rank or average score: {str(calc_error)}")
                rank = len(cleaned_records) if cleaned_records else 1
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
                if len(cleaned_records) >= 5:
                    if rank <= len(cleaned_records) * 0.1:
                        insights.append(t("You're in the top 10% of users! Keep up the excellent financial habits."))
                    elif rank <= len(cleaned_records) * 0.3:
                        insights.append(t("You're in the top 30%. Great work, aim for the top 10%!"))
                    else:
                        insights.append(t("You're below the top 30%. Try our Budgeting Basics course to improve your score."))
            except Exception as insight_error:
                log.error(f"Error generating insights: {str(insight_error)}")
                insights.append(t("Unable to generate insights due to data issues."))
        if len(cleaned_records) < 5:
            insights.append(t("Not enough users for comparison yet. Invite others to join!"))

        return render_template(
            'health_score_dashboard.html',
            records=records,
            latest_record=latest_record,
            insights=insights,
            tips=tips,
            rank=rank,
            total_users=len(cleaned_records),
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

# Blueprint-level error handler
@financial_health_bp.errorhandler(Exception)
def handle_blueprint_error(e):
    """Handle unexpected errors in the financial_health blueprint."""
    t_dict = trans('t')
    t = lambda key: t_dict.get(key, key)
    log.exception(f"Unexpected error in financial_health blueprint: {str(e)}")
    flash(t("An unexpected error occurred. Please try again or contact support."), "danger")
    return render_template(
        'health_score_dashboard.html',
        records=[],
        latest_record={},
        insights=[t("No data available due to an error.")],
        tips=[],
        rank=0,
        total_users=0,
        average_score=0,
        t=t
    ), 500
