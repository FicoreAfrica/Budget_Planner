from flask import Blueprint, request, session, redirect, url_for, render_template, flash, g
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Email, ValidationError
from json_store import JsonStorage
from mailersend_email import send_email
from datetime import datetime
import logging
import uuid
import os
try:
    from app import trans  # Import trans from app.py instead
except ImportError:
    def trans(key, lang=None):
        return key  # Fallback to return the key as the translation
        
logger = logging.getLogger(__name__)

financial_health_bp = Blueprint('financial_health', __name__, url_prefix='/financial_health')
financial_health_storage = JsonStorage('data/financial_health.json')
progress_storage = JsonStorage('data/user_progress.json')

# Forms for financial health steps
class Step1Form(FlaskForm):
    first_name = StringField(trans('financial_health_first_name'), validators=[DataRequired(message=trans('financial_health_first_name_required'))])
    email = StringField(trans('financial_health_email'), validators=[Optional(), Email(message=trans('financial_health_email_invalid'))])
    user_type = SelectField(trans('financial_health_user_type'), choices=[
        ('individual', trans('financial_health_user_type_individual')),
        ('business', trans('financial_health_user_type_business'))
    ])
    send_email = BooleanField(trans('financial_health_send_email'))
    submit = SubmitField(trans('financial_health_next'))

class Step2Form(FlaskForm):
    income = FloatField(trans('financial_health_monthly_income'), validators=[DataRequired(message=trans('financial_health_income_required')), NumberRange(min=0, max=10000000000, message=trans('financial_health_income_max'))])
    expenses = FloatField(trans('financial_health_monthly_expenses'), validators=[DataRequired(message=trans('financial_health_expenses_required')), NumberRange(min=0, max=10000000000, message=trans('financial_health_expenses_max'))])
    submit = SubmitField(trans('financial_health_next'))

    def validate_income(self, field):
        if field.data is not None:
            try:
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data)
            except (ValueError, TypeError):
                g.log.error(f"Invalid income input: {field.data}")
                raise ValidationError(trans('financial_health_income_invalid'))

    def validate_expenses(self, field):
        if field.data is not None:
            try:
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data)
            except (ValueError, TypeError):
                g.log.error(f"Invalid expenses input: {field.data}")
                raise ValidationError(trans('financial_health_expenses_invalid'))

class Step3Form(FlaskForm):
    debt = FloatField(trans('financial_health_total_debt'), validators=[Optional(), NumberRange(min=0, max=10000000000, message=trans('financial_health_debt_max'))])
    interest_rate = FloatField(trans('financial_health_average_interest_rate'), validators=[Optional(), NumberRange(min=0, message=trans('financial_health_interest_rate_positive'))])
    submit = SubmitField(trans('financial_health_submit'))

    def validate_debt(self, field):
        if field.data is not None:
            try:
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data) if cleaned_data else None
            except (ValueError, TypeError):
                g.log.error(f"Invalid debt input: {field.data}")
                raise ValidationError(trans('financial_health_debt_invalid'))

    def validate_interest_rate(self, field):
        if field.data is not None:
            try:
                cleaned_data = str(field.data).replace(',', '')
                field.data = float(cleaned_data) if cleaned_data else None
            except (ValueError, TypeError):
                g.log.error(f"Invalid interest rate input: {field.data}")
                raise ValidationError(trans('financial_health_interest_rate_invalid'))

@financial_health_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    """Handle financial health step 1 form (personal info)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step1Form()
    g.log.info(f"Starting step1 for session {session['sid']}")
    try:
        if request.method == 'POST':
            g.log.debug(f"Received POST data: {request.form}")
            if not form.validate_on_submit():
                g.log.warning(f"Form validation failed: {form.errors}")
                flash(trans("financial_health_form_errors"), "danger")
                return render_template('health_score_step1.html', form=form, trans=trans, lang=lang)
            
            form_data = form.data.copy()
            if form_data.get('email') and not isinstance(form_data['email'], str):
                g.log.error(f"Invalid email type: {type(form_data['email'])}")
                raise ValueError(trans("financial_health_email_must_be_string"))
            session['health_step1'] = form_data
            g.log.debug(f"Validated form data: {form_data}")

            try:
                storage_data = {
                    'step': 1,
                    'data': form_data
                }
                record_id = financial_health_storage.append(storage_data, user_email=form_data.get('email'), session_id=session['sid'])
                if record_id:
                    g.log.info(f"Step1 form data appended to storage with record ID {record_id} for session {session['sid']}")
                else:
                    g.log.error("Failed to append Step1 data to storage")
                    flash(trans("financial_health_save_data_error"), "danger")
                    return render_template('health_score_step1.html', form=form, trans=trans, lang=lang), 500
            except Exception as storage_error:
                g.log.exception(f"Failed to append to JSON storage: {str(storage_error)}")
                flash(trans("financial_health_save_data_error"), "danger")
                return render_template('health_score_step1.html', form=form, trans=trans, lang=lang), 500

            g.log.debug(f"Step1 form data saved to session: {form_data}")
            return redirect(url_for('financial_health.step2'))
        return render_template('health_score_step1.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        g.log.exception(f"Error in step1: {str(e)}")
        flash(trans("financial_health_error_personal_info"), "danger")
        return render_template('health_score_step1.html', form=form, trans=trans, lang=lang), 500

@financial_health_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    """Handle financial health step 2 form (income and expenses)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step2Form()
    g.log.info(f"Starting step2 for session {session['sid']}")
    try:
        if request.method == 'POST':
            if not form.validate_on_submit():
                g.log.warning(f"Form validation failed: {form.errors}")
                flash(trans("financial_health_form_errors"), "danger")
                return render_template('health_score_step2.html', form=form, trans=trans, lang=lang)
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
                    g.log.info(f"Step2 form data appended to storage with record ID {record_id} for session {session['sid']}")
                else:
                    g.log.error("Failed to append Step2 data to storage")
                    flash(trans("financial_health_save_data_error"), "danger")
                    return render_template('health_score_step2.html', form=form, trans=trans, lang=lang), 500
            except Exception as storage_error:
                g.log.exception(f"Failed to append to JSON storage: {str(storage_error)}")
                flash(trans("financial_health_save_data_error"), "danger")
                return render_template('health_score_step2.html', form=form, trans=trans, lang=lang), 500

            g.log.debug(f"Step2 form data saved to session: {session['health_step2']}")
            return redirect(url_for('financial_health.step3'))
        return render_template('health_score_step2.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        g.log.exception(f"Error in step2: {str(e)}")
        flash(trans("financial_health_error_income_expenses"), "danger")
        return render_template('health_score_step2.html', form=form, trans=trans, lang=lang), 500

@financial_health_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    """Handle financial health step 3 form (debt and interest) and calculate score."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step3Form()
    g.log.info(f"Starting step3 for session {session['sid']}")
    try:
        if request.method == 'POST':
            if not form.validate_on_submit():
                g.log.warning(f"Form validation failed: {form.errors}")
                flash(trans("financial_health_form_errors"), "danger")
                return render_template('health_score_step3.html', form=form, trans=trans, lang=lang)

            data = {
                'debt': float(form.debt.data) if form.debt.data is not None else 0,
                'interest_rate': float(form.interest_rate.data) if form.interest_rate.data is not None else 0,
                'submit': form.submit.data
            }
            step1_data = session.get('health_step1', {})
            step2_data = session.get('health_step2', {})
            g.log.debug(f"Step1 data: {step1_data}")
            g.log.debug(f"Step2 data: {step2_data}")
            g.log.debug(f"Step3 form data: {data}")

            income = float(step2_data.get('income', 0) or 0)
            expenses = float(step2_data.get('expenses', 0) or 0)
            debt = data.get('debt', 0)
            interest_rate = data.get('interest_rate', 0)

            if income <= 0:
                g.log.error("Income is zero or negative, cannot calculate financial health metrics")
                flash(trans("financial_health_income_zero_error"), "danger")
                return render_template('health_score_step3.html', form=form, trans=trans, lang=lang), 500

            g.log.info("Calculating financial health metrics")
            try:
                debt_to_income = (debt / income * 100)
                savings_rate = ((income - expenses) / income * 100)
                interest_burden = (interest_rate * debt / 100) if debt > 0 else 0
            except ZeroDivisionError as zde:
                g.log.error(f"ZeroDivisionError during metric calculation: {str(zde)}")
                flash(trans("financial_health_calculation_error"), "danger")
                return render_template('health_score_step3.html', form=form, trans=trans, lang=lang), 500

            score = 100
            if debt_to_income > 0:
                score -= min(debt_to_income, 50)
            if savings_rate < 0:
                score -= min(abs(savings_rate), 30)
            elif savings_rate > 0:
                score += min(savings_rate / 2, 20)
            score -= min(interest_burden, 20)
            score = max(0, min(100, round(score)))
            g.log.debug(f"Calculated score: {score}")

            status = (trans("financial_health_status_excellent") if score >= 80 else
                      trans("financial_health_status_good") if score >= 60 else
                      trans("financial_health_status_needs_improvement"))
            badges = []
            if score >= 80:
                badges.append(trans("financial_health_badge_financial_star"))
            if debt_to_income < 20:
                badges.append(trans("financial_health_badge_debt_manager"))
            if savings_rate >= 20:
                badges.append(trans("financial_health_badge_savings_pro"))
            if interest_burden == 0 and debt > 0:
                badges.append(trans("financial_health_badge_interest_free"))
            g.log.debug(f"Status: {status}, Badges: {badges}")

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
                    g.log.info(f"Step3 final record appended to storage with record ID {record_id} for session {session['sid']}")
                else:
                    g.log.error("Failed to append Step3 final record to storage")
                    flash(trans("financial_health_save_final_error"), "danger")
                    return render_template('health_score_step3.html', form=form, trans=trans, lang=lang), 500
            except Exception as storage_error:
                g.log.exception(f"Failed to append to JSON storage: {str(storage_error)}")
                flash(trans("financial_health_save_final_error"), "danger")
                return render_template('health_score_step3.html', form=form, trans=trans, lang=lang), 500

            g.log.debug(f"Session contents after save: {dict(session)}")

            email = step1_data.get('email')
            send_email_flag = step1_data.get('send_email', False)
            if send_email_flag and email:
                g.log.info(f"Sending email to {email}")
                try:
                    send_email(
                        to_email=email,
                        subject=trans("financial_health_financial_health_report"),
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
                        lang=lang
                    )
                except Exception as email_error:
                    g.log.error(f"Failed to send email: {str(email_error)}")
                    flash(trans("financial_health_email_failed"), "warning")

            session.pop('health_step1', None)
            session.pop('health_step2', None)
            g.log.info("Financial health assessment completed successfully")
            flash(trans("financial_health_health_completed_success"), "success")
            return redirect(url_for('financial_health.dashboard'))
        return render_template('health_score_step3.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        g.log.exception(f"Unexpected error in step3: {str(e)}")
        flash(trans("financial_health_unexpected_error"), "danger")
        return render_template('health_score_step3.html', form=form, trans=trans, lang=lang), 500

@financial_health_bp.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    """Display financial health dashboard with comparison to others."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    g.log.info(f"Starting dashboard for session {session['sid']}")
    try:
        # Define required_fields here for consistent use
        required_fields = ['score', 'income', 'expenses', 'debt', 'interest_rate', 'debt_to_income', 'savings_rate']

        # Retrieve user-specific record from session or storage
        health_record = session.get('health_record', {})
        g.log.debug(f"Session health_record: {health_record}")
        if not health_record:
            stored_records = financial_health_storage.filter_by_session(session['sid'])
            g.log.debug(f"Raw stored records for current session: {stored_records}")
            if not stored_records:
                g.log.warning("No records found for this session in storage")
                latest_record = {}
                records = []
            else:
                # Find the latest record (prioritize step 3 if present)
                final_record = None
                # Sort by timestamp in descending order
                for record in sorted(stored_records, key=lambda x: x.get('timestamp', ''), reverse=True):
                    # Check for 'data' key before accessing 'step'
                    if record.get('data') and record['data'].get('step') == 3:
                        final_record = record
                        break
                if not final_record:
                    # If no step 3, use the absolute latest record based on timestamp
                    final_record = sorted(stored_records, key=lambda x: x.get('timestamp', ''), reverse=True)[0]
                    g.log.warning("No step 3 record found for session, using absolute latest record.")

                # Handle both old (flat data) and new (nested data) structures
                if final_record.get('data') and 'step' in final_record['data']:
                    latest_record = final_record['data'].get('data', {})
                else:
                    latest_record = final_record.get('data', {})

                # Validate required fields and ensure numeric types
                for field in required_fields:
                    if field not in latest_record or latest_record[field] is None:
                        g.log.warning(f"Missing or None field '{field}' in latest record for session {session['sid']}: {latest_record}. Setting to 0.")
                        latest_record[field] = 0
                    elif not isinstance(latest_record[field], (int, float)):
                        try:
                            latest_record[field] = float(latest_record[field])
                            g.log.debug(f"Converted '{field}' to float: {latest_record[field]}")
                        except (ValueError, TypeError):
                            g.log.warning(f"Invalid type for '{field}' in latest record for session {session['sid']}: {type(latest_record[field])}, setting to 0.")
                            latest_record[field] = 0
                records = [(final_record.get('id', str(uuid.uuid4())), latest_record)]
                g.log.debug(f"Processed user records from storage: {records}")
        else:
            latest_record = health_record
            # Validate required fields for session health_record
            for field in required_fields:
                if field not in latest_record or latest_record[field] is None:
                    g.log.warning(f"Missing or None field '{field}' in session health_record: {latest_record}. Setting to 0.")
                    latest_record[field] = 0
                elif not isinstance(latest_record[field], (int, float)):
                    try:
                        latest_record[field] = float(latest_record[field])
                        g.log.debug(f"Converted '{field}' to float: {latest_record[field]}")
                    except (ValueError, TypeError):
                        g.log.warning(f"Invalid type for '{field}' in session health_record: {type(latest_record[field])}, setting to 0.")
                        latest_record[field] = 0
            records = [(str(uuid.uuid4()), latest_record)]
            g.log.debug(f"Processed user records from session: {records}")

        # Retrieve all records for comparison
        all_records = financial_health_storage._read()
        g.log.debug(f"All records from storage (before cleaning): {all_records}")
        
        cleaned_records = []
        for record_item in all_records:
            try:
                # Only consider records from step 3 for comparison, or old records without 'step'
                if record_item.get('data') and 'step' in record_item['data'] and record_item['data'].get('step') != 3:
                    continue
                
                # Handle both old and new structures for data extraction
                data = record_item.get('data', {})
                if 'step' in data:
                    data = data.get('data', {})
                
                # Ensure 'score' is present and numeric
                score = data.get('score')
                if score is None:
                    g.log.warning(f"Record {record_item.get('id', 'N/A')} has no 'score' field. Skipping for comparison.")
                    continue
                if not isinstance(score, (int, float)):
                    try:
                        score = float(str(score).replace(',', ''))
                    except (ValueError, TypeError):
                        g.log.warning(f"Record {record_item.get('id', 'N/A')} has invalid 'score' type: {type(score)}. Skipping for comparison.")
                        continue
                
                # Reconstruct record for cleaned_records list, ensuring consistent structure
                cleaned_records.append({
                    'id': record_item.get('id'),
                    'session_id': record_item.get('session_id'),
                    'timestamp': record_item.get('timestamp'),
                    'data': {'data': data}
                })
            except Exception as record_cleaning_error:
                g.log.warning(f"Skipping invalid record during cleaning for comparison (ID: {record_item.get('id', 'N/A')}): {str(record_cleaning_error)}", exc_info=True)
                continue
        
        g.log.debug(f"Cleaned records for comparison: {cleaned_records}")
        
        total_users = len(cleaned_records)
        rank = 0
        average_score = 0
        
        if cleaned_records:
            all_scores_for_comparison = []
            for rec in cleaned_records:
                # Access score consistently from the normalized structure
                score_val = rec['data']['data'].get('score')
                if isinstance(score_val, (int, float)):
                    all_scores_for_comparison.append(score_val)
            
            if all_scores_for_comparison:
                all_scores_for_comparison.sort(reverse=True)
                
                user_score = latest_record.get("score", 0)
                
                rank = 1
                for s in all_scores_for_comparison:
                    if s > user_score:
                        rank += 1
                    else:
                        break
                
                average_score = sum(all_scores_for_comparison) / len(all_scores_for_comparison)
                g.log.debug(f"Calculated user rank: {rank}, Average score of all users: {average_score}")
            else:
                g.log.warning("No valid scores found in cleaned records for rank/average calculation.")
                rank = 0
                average_score = 0
        else:
            g.log.info("No cleaned records available for comparison, rank and average score set to 0.")
            rank = 0
            average_score = 0

        # Generate insights and tips
        insights = []
        tips = [
            trans("financial_health_tip_track_expenses"),
            trans("financial_health_tip_ajo_savings"),
            trans("financial_health_tip_pay_debts"),
            trans("financial_health_tip_plan_expenses")
        ]
        
        if latest_record:
            try:
                if latest_record.get('debt_to_income', 0) > 40:
                    insights.append(trans("financial_health_insight_high_debt"))
                if latest_record.get('savings_rate', 0) < 0:
                    insights.append(trans("financial_health_insight_negative_savings"))
                elif latest_record.get('savings_rate', 0) >= 20:
                    insights.append(trans("financial_health_insight_good_savings"))
                if latest_record.get('interest_burden', 0) > 10:
                    insights.append(trans("financial_health_insight_high_interest"))
                
                if total_users >= 5:
                    if rank <= total_users * 0.1:
                        insights.append(trans("financial_health_insight_top_10"))
                    elif rank <= total_users * 0.3:
                        insights.append(trans("financial_health_insight_top_30"))
                    else:
                        insights.append(trans("financial_health_insight_below_30"))
                else:
                    insights.append(trans("financial_health_insight_not_enough_users"))

            except Exception as insight_error:
                g.log.exception(f"Error generating insights: {str(insight_error)}")
                insights.append(trans("financial_health_insight_data_issues"))
        else:
            insights.append(trans("financial_health_insight_no_data"))

        # Load course progress for the "My Courses" card
        progress_records = []
        if 'sid' in session:
            progress_records = progress_storage.filter_by_session(session['sid'])
            g.log.debug(f"Course progress records for session {session['sid']}: {progress_records}")

        return render_template(
            'health_score_dashboard.html',
            records=records,
            latest_record=latest_record,
            insights=insights,
            tips=tips,
            rank=rank,
            total_users=total_users,
            average_score=average_score,
            trans=trans,
            lang=lang,
            progress_records=progress_records
        )
    except Exception as e:
        g.log.exception(f"Critical error in dashboard: {str(e)}")
        flash(trans("financial_health_dashboard_load_error"), "danger")
        return render_template(
            'health_score_dashboard.html',
            records=[],
            latest_record={},
            insights=[trans("financial_health_insight_no_data")],
            tips=[
                trans("financial_health_tip_track_expenses"),
                trans("financial_health_tip_ajo_savings"),
                trans("financial_health_tip_pay_debts"),
                trans("financial_health_tip_plan_expenses")
            ],
            rank=0,
            total_users=0,
            average_score=0,
            trans=trans,
            lang=lang,
            progress_records=[]
        ), 500
