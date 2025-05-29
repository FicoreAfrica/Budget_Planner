from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Optional, Email, NumberRange
from json_store import JsonStorage
from mailersend_email import send_email
from datetime import datetime
import logging
import uuid

logging.basicConfig(filename='data/storage.txt', level=logging.DEBUG)

try:
    from app import trans
except ImportError:
    def trans(key, lang=None, **kwargs):
        return key.format(**kwargs)

emergency_fund_bp = Blueprint('emergency_fund', __name__, url_prefix='/emergency_fund')
emergency_fund_storage = JsonStorage('data/emergency_fund.json')
budget_storage = JsonStorage('data/budget.json')

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
    first_name = StringField(trans('emergency_fund_first_name'), validators=[DataRequired(message=trans('required_first_name'))])
    email = StringField(trans('emergency_fund_email'), validators=[Optional(), Email(message=trans('emergency_fund_email_invalid'))])
    email_opt_in = BooleanField(trans('emergency_fund_send_email'), default=False)
    submit = SubmitField(trans('core_next'))

class Step2Form(FlaskForm):
    monthly_expenses = CommaSeparatedFloatField(trans('emergency_fund_monthly_expenses'), validators=[DataRequired(message=trans('required_monthly_expenses')), NumberRange(min=0, max=10000000000, message=trans('emergency_fund_monthly_exceed'))])
    monthly_income = CommaSeparatedFloatField(trans('emergency_fund_monthly_income'), validators=[Optional(), NumberRange(min=0, max=10000000000, message=trans('emergency_fund_monthly_exceed'))])
    submit = SubmitField(trans('core_next'))

class Step3Form(FlaskForm):
    current_savings = CommaSeparatedFloatField(trans('emergency_fund_current_savings'), validators=[Optional(), NumberRange(min=0, max=10000000000, message=trans('emergency_fund_savings_max'))])
    risk_tolerance_level = SelectField(trans('emergency_fund_risk_tolerance_level'), choices=[('low', trans('emergency_fund_risk_tolerance_level_low')), ('medium', trans('emergency_fund_risk_tolerance_level_medium')), ('high', trans('emergency_fund_risk_tolerance_level_high'))], validators=[DataRequired()])
    dependents = CommaSeparatedIntegerField(trans('emergency_fund_dependents'), validators=[Optional(), NumberRange(min=0, max=100, message=trans('emergency_fund_dependents_max'))])
    submit = SubmitField(trans('core_next'))

class Step4Form(FlaskForm):
    timeline = SelectField(trans('emergency_fund_timeline'), choices=[('6', trans('emergency_fund_6_months')), ('12', trans('emergency_fund_12_months')), ('18', trans('emergency_fund_18_months'))], validators=[DataRequired()])
    submit = SubmitField(trans('emergency_fund_calculate_button'))

@emergency_fund_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step1Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['emergency_fund_step1'] = {
                'first_name': form.first_name.data,
                'email': form.email.data,
                'email_opt_in': form.email_opt_in.data
            }
            return redirect(url_for('emergency_fund.step2'))
        return render_template('emergency_fund_step1.html', form=form, step=1, trans=trans, lang=lang)
    except Exception as e:
        logging.exception(f"Error in step1: {str(e)}")
        flash(trans('an_unexpected_error_occurred'), 'danger')
        return render_template('emergency_fund_step1.html', form=form, step=1, trans=trans, lang=lang)

@emergency_fund_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    if 'sid' not in session or 'emergency_fund_step1' not in session:
        flash(trans('emergency_fund_missing_step1'), 'danger')
        return redirect(url_for('emergency_fund.step1'))
    lang = session.get('lang', 'en')
    form = Step2Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['emergency_fund_step2'] = {
                'monthly_expenses': form.monthly_expenses.data,
                'monthly_income': form.monthly_income.data
            }
            return redirect(url_for('emergency_fund.step3'))
        return render_template('emergency_fund_step2.html', form=form, step=2, trans=trans, lang=lang)
    except Exception as e:
        logging.exception(f"Error in step2: {str(e)}")
        flash(trans('an_unexpected_error_occurred'), 'danger')
        return render_template('emergency_fund_step2.html', form=form, step=2, trans=trans, lang=lang)

@emergency_fund_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    if 'sid' not in session or 'emergency_fund_step2' not in session:
        flash(trans('emergency_fund_missing_step2'), 'danger')
        return redirect(url_for('emergency_fund.step1'))
    lang = session.get('lang', 'en')
    form = Step3Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['emergency_fund_step3'] = {
                'current_savings': form.current_savings.data,
                'risk_tolerance_level': form.risk_tolerance_level.data,
                'dependents': form.dependents.data
            }
            return redirect(url_for('emergency_fund.step4'))
        return render_template('emergency_fund_step3.html', form=form, step=3, trans=trans, lang=lang)
    except Exception as e:
        logging.exception(f"Error in step3: {str(e)}")
        flash(trans('an_unexpected_error_occurred'), 'danger')
        return render_template('emergency_fund_step3.html', form=form, step=3, trans=trans, lang=lang)

@emergency_fund_bp.route('/step4', methods=['GET', 'POST'])
def step4():
    if 'sid' not in session or 'emergency_fund_step3' not in session:
        flash(trans('emergency_fund_missing_step3'), 'danger')
        return redirect(url_for('emergency_fund.step1'))
    lang = session.get('lang', 'en')
    form = Step4Form()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            step1_data = session['emergency_fund_step1']
            step2_data = session['emergency_fund_step2']
            step3_data = session['emergency_fund_step3']
            months = int(form.timeline.data)
            base_target = step2_data['monthly_expenses'] * months
            recommended_months = months
            if step3_data['risk_tolerance_level'] == 'high':
                recommended_months = max(months, 12)
            elif step3_data['risk_tolerance_level'] == 'low':
                recommended_months = min(months, 6)
            if step3_data['dependents'] and step3_data['dependents'] > 2:
                recommended_months += 2
            target_amount = step2_data['monthly_expenses'] * recommended_months
            gap = target_amount - (step3_data['current_savings'] or 0)
            percent_of_income_needed = None
            monthly_savings = gap / months if gap > 0 else 0
            if step2_data['monthly_income'] and step2_data['monthly_income'] > 0:
                percent_of_income_needed = (monthly_savings / step2_data['monthly_income']) * 100
            badges = []
            if form.timeline.data in ['6', '12']:
                badges.append('Planner')
            if step3_data['dependents'] and step3_data['dependents'] > 2:
                badges.append('Protector')
            if gap > 0:
                badges.append('Steady Saver')
            if step3_data['current_savings'] and step3_data['current_savings'] >= target_amount:
                badges.append('Fund Master')
            record = {
                'id': str(uuid.uuid4()),
                'session_id': session['sid'],
                'data': {
                    'first_name': step1_data['first_name'],
                    'email': step1_data['email'],
                    'email_opt_in': step1_data['email_opt_in'],
                    'language': lang,
                    'monthly_expenses': step2_data['monthly_expenses'],
                    'monthly_income': step2_data['monthly_income'],
                    'current_savings': step3_data['current_savings'] or 0,
                    'risk_tolerance_level': step3_data['risk_tolerance_level'],
                    'dependents': step3_data['dependents'] or 0,
                    'timeline': months,
                    'recommended_months': recommended_months,
                    'target_amount': target_amount,
                    'savings_gap': gap,
                    'monthly_savings': monthly_savings,
                    'percent_of_income_needed': percent_of_income_needed,
                    'badges': badges,
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }
            emergency_fund_storage.append(record, user_email=step1_data['email'] if step1_data['email'] else None, session_id=session['sid'])
            if step1_data['email_opt_in'] and step1_data['email']:
                send_email(
                    to_email=step1_data['email'],
                    subject=trans('emergency_fund_email_subject', lang=lang),
                    template_name='emergency_fund_email.html',
                    data={
                        'first_name': step1_data['first_name'],
                        'language': lang,
                        'monthly_expenses': step2_data['monthly_expenses'],
                        'monthly_income': step2_data['monthly_income'],
                        'current_savings': step3_data['current_savings'] or 0,
                        'risk_tolerance_level': step3_data['risk_tolerance_level'],
                        'dependents': step3_data['dependents'] or 0,
                        'timeline': months,
                        'recommended_months': recommended_months,
                        'target_amount': target_amount,
                        'savings_gap': gap,
                        'monthly_savings': monthly_savings,
                        'percent_of_income_needed': percent_of_income_needed,
                        'badges': badges,
                        'created_at': record['data']['created_at'],
                        'cta_url': url_for('emergency_fund.dashboard', _external=True)
                    },
                    lang=lang
                )
            flash(trans('emergency_fund_emergency_fund_completed_success'), 'success')
            for key in ['emergency_fund_step1', 'emergency_fund_step2', 'emergency_fund_step3']:
                session.pop(key, None)
            return redirect(url_for('emergency_fund.dashboard'))
        return render_template('emergency_fund_step4.html', form=form, step=4, trans=trans, lang=lang)
    except Exception as e:
        logging.exception(f"Error in step4: {str(e)}")
        flash(trans('an_unexpected_error_occurred'), 'danger')
        return render_template('emergency_fund_step4.html', form=form, step=4, trans=trans, lang=lang)

@emergency_fund_bp.route('/dashboard', methods=['GET'])
def dashboard():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        logging.debug(f"New session ID created: {session['sid']}")
    lang = session.get('lang', 'en')
    try:
        user_data = emergency_fund_storage.filter_by_session(session['sid'])
        email = None
        if not user_data and 'emergency_fund_step1' in session and session['emergency_fund_step1'].get('email'):
            email = session['emergency_fund_step1']['email']
            user_data = emergency_fund_storage.filter_by_email(email)
        records = [(record['id'], record['data']) for record in user_data]
        latest_record = records[-1][1] if records else {}
        insights = []
        if latest_record:
            if latest_record.get('savings_gap', 0) == 0:
                insights.append(trans('emergency_fund_insight_fully_funded'))
            else:
                insights.append(trans('emergency_fund_insight_savings_gap', savings_gap=latest_record.get('savings_gap'), months=latest_record.get('timeline')))
                if latest_record.get('percent_of_income_needed') and latest_record.get('percent_of_income_needed') > 30:
                    insights.append(trans('emergency_fund_insight_high_income_percentage'))
                if latest_record.get('dependents', 0) > 2:
                    insights.append(trans('emergency_fund_insight_large_family', recommended_months=latest_record.get('recommended_months')))
        cross_tool_insights = []
        budget_data = budget_storage.filter_by_session(session['sid']) or (budget_storage.filter_by_email(email) if email else [])
        if budget_data and latest_record and latest_record.get('savings_gap', 0) > 0:
            latest_budget = budget_data[-1]['data']
            if latest_budget.get('monthly_income') and latest_budget.get('monthly_expenses'):
                savings_possible = latest_budget['monthly_income'] - latest_budget['monthly_expenses']
                if savings_possible > 0:
                    cross_tool_insights.append(trans('emergency_fund_cross_tool_savings_possible', amount=savings_possible))
        return render_template(
            'emergency_fund_dashboard.html',
            records=records,
            latest_record=latest_record,
            insights=insights,
            cross_tool_insights=cross_tool_insights,
            tips=[
                trans('emergency_fund_tip_automate_savings'),
                trans('emergency_fund_tip_ajo_savings'),
                trans('emergency_fund_tip_track_expenses'),
                trans('emergency_fund_tip_monthly_savings_goals')
            ],
            trans=trans,
            lang=lang
        )
    except Exception as e:
        logging.exception(f"Error in dashboard: {str(e)}")
        flash(trans('emergency_fund_dashboard_load_error'), 'danger')
        return render_template(
            'emergency_fund_dashboard.html',
            records=[],
            latest_record={},
            insights=[],
            cross_tool_insights=[],
            tips=[
                trans('emergency_fund_tip_automate_savings'),
                trans('emergency_fund_tip_ajo_savings'),
                trans('emergency_fund_tip_track_expenses'),
                trans('emergency_fund_tip_monthly_savings_goals')
            ],
            trans=trans,
            lang=lang
        )
