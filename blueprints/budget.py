from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional, Email, NumberRange
from json_store import JsonStorage
from datetime import datetime
import uuid

try:
    from app import trans
except ImportError:
    def trans(key, lang=None, **kwargs):
        return key.format(**kwargs)

financial_health_bp = Blueprint('financial_health', __name__, url_prefix='/financial_health')

def init_financial_health_storage(app):
    """Initialize financial_health_storage within app context."""
    with app.app_context():
        app.logger.info("Initializing financial health storage")
        return JsonStorage('data/financial_health.json', logger_instance=app.logger)

class CommaSeparatedFloatField(FloatField):
    def process_formdata(self, valuelist):
        if valuelist:
            try:
                self.data = float(valuelist[0].replace(',', ''))
            except ValueError:
                self.data = None
                raise ValueError(self.gettext('Not a valid number'))

class CommaSeparatedIntegerField(IntegerField):
    def process_formdata(self, valuelist):
        if valuelist:
            try:
                self.data = int(valuelist[0].replace(',', ''))
            except ValueError:
                self.data = None
                raise ValueError(self.gettext('Not a number'))

class Step1Form(FlaskForm):
    first_name = StringField(trans('financial_health_first_name'), validators=[DataRequired(message=trans('required_first_name'))])
    email = StringField(trans('financial_health_email'), validators=[Optional(), Email(message=trans('financial_health_email_invalid'))])
    submit = SubmitField(trans('core_next'))

class Step2Form(FlaskForm):
    monthly_income = CommaSeparatedFloatField(trans('financial_health_monthly_income'), validators=[DataRequired(message=trans('required_monthly_income')), NumberRange(min=0, max=10000000000, message=trans('financial_health_income_exceed'))])
    monthly_expenses = CommaSeparatedFloatField(trans('financial_health_monthly_expenses'), validators=[DataRequired(message=trans('required_monthly_expenses')), NumberRange(min=0, max=10000000000, message=trans('financial_health_expenses_exceed'))])
    submit = SubmitField(trans('core_next'))

class Step3Form(FlaskForm):
    total_assets = CommaSeparatedFloatField(trans('financial_health_total_assets'), validators=[Optional(), NumberRange(min=0, max=10000000000, message=trans('financial_health_assets_max'))])
    total_liabilities = CommaSeparatedFloatField(trans('financial_health_total_liabilities'), validators=[Optional(), NumberRange(min=0, max=10000000000, message=trans('financial_health_liabilities_max'))])
    submit = SubmitField(trans('core_next'))

class Step4Form(FlaskForm):
    emergency_fund_months = CommaSeparatedIntegerField(trans('financial_health_emergency_fund_months'), validators=[Optional(), NumberRange(min=0, max=100, message=trans('financial_health_emergency_fund_max'))])
    debt_repayment_plan = SelectField(trans('financial_health_debt_repayment_plan'), choices=[('yes', trans('core_yes')), ('no', trans('core_no'))], validators=[DataRequired()])
    submit = SubmitField(trans('financial_health_calculate_button'))

@financial_health_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step1Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['financial_health_step1'] = {
                'first_name': form.first_name.data,
                'email': form.email.data
            }
            return redirect(url_for('financial_health.step2'))
        return render_template('financial_health_step1.html', form=form, step=1, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in step1: {str(e)}")
        flash(trans('an_unexpected_error_occurred'), 'danger')
        return render_template('financial_health_step1.html', form=form, step=1, trans=trans, lang=lang)

@financial_health_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    if 'sid' not in session or 'financial_health_step1' not in session:
        flash(trans('financial_health_missing_step1'), 'danger')
        return redirect(url_for('financial_health.step1'))
    lang = session.get('lang', 'en')
    form = Step2Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['financial_health_step2'] = {
                'monthly_income': form.monthly_income.data,
                'monthly_expenses': form.monthly_expenses.data
            }
            return redirect(url_for('financial_health.step3'))
        return render_template('financial_health_step2.html', form=form, step=2, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in step2: {str(e)}")
        flash(trans('an_unexpected_error_occurred'), 'danger')
        return render_template('financial_health_step2.html', form=form, step=2, trans=trans, lang=lang)

@financial_health_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    if 'sid' not in session or 'financial_health_step2' not in session:
        flash(trans('financial_health_missing_step2'), 'danger')
        return redirect(url_for('financial_health.step1'))
    lang = session.get('lang', 'en')
    form = Step3Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['financial_health_step3'] = {
                'total_assets': form.total_assets.data,
                'total_liabilities': form.total_liabilities.data
            }
            return redirect(url_for('financial_health.step4'))
        return render_template('financial_health_step3.html', form=form, step=3, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in step3: {str(e)}")
        flash(trans('an_unexpected_error_occurred'), 'danger')
        return render_template('financial_health_step3.html', form=form, step=3, trans=trans, lang=lang)

@financial_health_bp.route('/step4', methods=['GET', 'POST'])
def step4():
    if 'sid' not in session or 'financial_health_step3' not in session:
        flash(trans('financial_health_missing_step3'), 'danger')
        return redirect(url_for('financial_health.step1'))
    lang = session.get('lang', 'en')
    form = Step4Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            step1_data = session['financial_health_step1']
            step2_data = session['financial_health_step2']
            step3_data = session['financial_health_step3']
            emergency_fund_months = form.emergency_fund_months.data or 0
            debt_repayment_plan = form.debt_repayment_plan.data == 'yes'
            savings_rate = ((step2_data['monthly_income'] - step2_data['monthly_expenses']) / step2_data['monthly_income']) * 100 if step2_data['monthly_income'] > 0 else 0
            debt_to_income_ratio = (step3_data['total_liabilities'] / step2_data['monthly_income']) * 12 * 100 if step2_data['monthly_income'] > 0 and step3_data['total_liabilities'] else 0
            net_worth = (step3_data['total_assets'] or 0) - (step3_data['total_liabilities'] or 0)
            score = 0
            recommendations = []
            if savings_rate >= 20:
                score += 25
            elif savings_rate < 10:
                recommendations.append(trans('financial_health_recommendation_savings_rate'))
            if debt_to_income_ratio < 36:
                score += 25
            elif debt_to_income_ratio > 43:
                recommendations.append(trans('financial_health_recommendation_debt_to_income'))
            if emergency_fund_months >= 6:
                score += 25
            elif emergency_fund_months < 3:
                recommendations.append(trans('financial_health_recommendation_emergency_fund'))
            if debt_repayment_plan:
                score += 25
            else:
                recommendations.append(trans('financial_health_recommendation_debt_repayment_plan'))
            status = 'Excellent' if score >= 80 else 'Good' if score >= 60 else 'Needs Improvement'
            record = {
                'id': str(uuid.uuid4()),
                'session_id': session['sid'],
                'data': {
                    'first_name': step1_data.get('first_name'),
                    'email': step1_data.get('email'),
                    'language': lang,
                    'monthly_income': step2_data.get('monthly_income'),
                    'monthly_expenses': step2_data.get('monthly_expenses'),
                    'total_assets': step3_data.get('total_assets', 0),
                    'total_liabilities': step3_data.get('total_liabilities', 0),
                    'emergency_fund_months': emergency_fund_months,
                    'debt_repayment_plan': debt_repayment_plan,
                    'savings_rate': round(savings_rate, 2),
                    'debt_to_income_ratio': round(debt_to_income_ratio, 2),
                    'net_worth': round(net_worth, 2),
                    'score': score,
                    'status': status,
                    'recommendations': recommendations,
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }
            financial_health_storage = current_app.config['STORAGE_MANAGERS']['financial_health']
            financial_health_storage.append(record, user_email=step1_data.get('email'), session_id=session['sid'])
            flash(trans('financial_health_completed_successfully'), 'success')
            for key in ['financial_health_step1', 'financial_health_step2', 'financial_health_step3']:
                session.pop(key, None)
            return redirect(url_for('financial_health.dashboard'))
        return render_template('financial_health_step4.html', form=form, step=4, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in step4: {str(e)}")
        flash(trans('an_unexpected_error_occurred'), 'danger')
        return render_template('financial_health_step4.html', form=form, step=4, trans=trans, lang=lang)

@financial_health_bp.route('/dashboard', methods=['GET'])
def dashboard():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    try:
        financial_health_storage = current_app.config['STORAGE_MANAGERS']['financial_health']
        user_data = financial_health_storage.filter_by_session(session['sid'])
        email = None
        if not user_data and 'financial_health_step1' in session and session['financial_health_step1'].get('email'):
            email = session['financial_health_step1']['email']
            user_data = financial_health_storage.filter_by_email(email)
        records = [(record['id'], record['data']) for record in user_data]
        latest_record = records[-1][1] if records else {}
        tips = [
            trans('financial_health_tip_budget'),
            trans('financial_health_tip_emergency_fund'),
            trans('financial_health_tip_debt'),
            trans('financial_health_tip_invest'),
        ]
        return render_template(
            'financial_health_dashboard.html',
            records=records,
            latest_record=latest_record,
            tips=tips,
            trans=trans,
            lang=lang
        )
    except Exception as e:
        current_app.logger.exception(f"Error in dashboard: {str(e)}")
        flash(trans('financial_health_load_dashboard_error'), 'danger')
        return render_template(
            'financial_health_dashboard.html',
            records=[],
            latest_record={},
            tips=[
                trans('financial_health_tip_budget'),
                trans('financial_health_tip_emergency_fund'),
                trans('financial_health_tip_debt'),
                trans('financial_health_tip_invest'),
            ],
            trans=trans,
            lang=lang
        )
