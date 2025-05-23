from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Optional, Email
from json_store import JsonStorage
from mailersend_email import send_email
from datetime import datetime
import logging
import uuid
import random

quiz_bp = Blueprint('quiz', __name__)

QUESTION_POOL = [
    {
        'key': 'track_expenses',
        'label': 'How often do you track your expenses, such as daily purchases or subscriptions like DSTv?',
        'tooltip': 'Consider how frequently you monitor your spending, including small purchases like airtime or larger ones like rent.',
        'placeholder': 'e.g., I use an app like PiggyVest to track daily expenses'
    },
    {
        'key': 'save_regularly',
        'label': 'How often do you save money, such as through Ajo/Esusu/Adashe or a savings account?',
        'tooltip': 'Think about whether you consistently set aside money, like contributing to a thrift group or saving in a bank.',
        'placeholder': 'e.g., I save ₦10,000 monthly in my OPay account'
    },
    {
        'key': 'spend_non_essentials',
        'label': 'How often do you spend on non-essential items, like eating out or buying new clothes?',
        'tooltip': 'Reflect on your spending habits for things you don’t need, such as weekend outings or gadgets.',
        'placeholder': 'e.g., I buy new shoes every few months'
    },
    {
        'key': 'plan_expenses',
        'label': 'How often do you plan your expenses, such as budgeting for rent or school fees?',
        'tooltip': 'Consider whether you create a budget for monthly expenses like transport or household costs.',
        'placeholder': 'e.g., I budget for my children’s school fees every term'
    },
    {
        'key': 'impulse_purchases',
        'label': 'How often do you make impulse purchases, like buying items on Jumia without planning?',
        'tooltip': 'Think about unplanned purchases, such as buying a phone accessory you saw online.',
        'placeholder': 'e.g., I sometimes buy snacks on my way home'
    },
    {
        'key': 'use_budgeting_tools',
        'label': 'How often do you use budgeting tools or apps, like Moniepoint or Excel, to manage your finances?',
        'tooltip': 'Consider whether you use apps or spreadsheets to organize your income and expenses.',
        'placeholder': 'e.g., I use Cowrywise to plan my savings'
    },
    {
        'key': 'invest_money',
        'label': 'How often do you invest money, such as in farming, stocks, or real estate?',
        'tooltip': 'Reflect on whether you put money into investments like cooperative shares or land purchases.',
        'placeholder': 'e.g., I invest in a friend’s poultry farm'
    },
    {
        'key': 'emergency_fund',
        'label': 'How often do you contribute to an emergency fund for unexpected expenses like medical bills?',
        'tooltip': 'Think about whether you save for emergencies, such as car repairs or hospital visits.',
        'placeholder': 'e.g., I keep ₦50,000 in a separate GTBank account'
    },
    {
        'key': 'set_financial_goals',
        'label': 'How often do you set financial goals, like saving for a car or starting a business?',
        'tooltip': 'Consider whether you plan for big purchases or long-term goals, like opening a shop.',
        'placeholder': 'e.g., I’m saving to buy a used Toyota Corolla'
    },
    {
        'key': 'seek_financial_advice',
        'label': 'How often do you seek financial advice, such as from a mentor or financial apps like Risevest?',
        'tooltip': 'Reflect on whether you consult experts or use apps for financial guidance.',
        'placeholder': 'e.g., I follow financial tips on Nairaland'
    }
]

class Step1Form(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(message='quiz_first_name_required')])
    email = StringField('Email', validators=[Optional(), Email(message='quiz_email_invalid')])
    send_email = BooleanField('Send Email')
    submit = SubmitField('Start Quiz')

class Step2Form(FlaskForm):
    def __init__(self, questions, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for q in questions:
            setattr(self, q['key'], SelectField(
                q['label'],
                choices=[
                    ('', 'Select an answer'),
                    ('always', 'Always'),
                    ('often', 'Often'),
                    ('sometimes', 'Sometimes'),
                    ('never', 'Never')
                ],
                validators=[DataRequired(message='quiz_answer_required')]
            ))
        # Set the submit button label dynamically based on form_type
        form_type = kwargs.get('form_type', '')
        self.submit = SubmitField('Continue' if 'step2a' in form_type else 'See Results')

@quiz_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step1Form()
    course_id = request.args.get('course_id', 'financial_quiz')
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['quiz_step1'] = form.data
            current_app.logger.debug(f"Quiz step1 form data: {form.data}")
            progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
            progress = progress_storage.filter_by_session(session['sid'])
            course_progress = next((p for p in progress if p['data']['course_id'] == course_id), None)
            if not course_progress:
                progress_data = {
                    'course_id': course_id,
                    'completed_lessons': [0],
                    'progress_percentage': (1/4) * 100,
                    'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                progress_storage.append(progress_data, session_id=session['sid'])
            else:
                if 0 not in course_progress['data']['completed_lessons']:
                    course_progress['data']['completed_lessons'].append(0)
                    course_progress['data']['progress_percentage'] = (len(course_progress['data']['completed_lessons']) / 4) * 100
                    course_progress['data']['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    progress_storage.update_by_id(course_progress['id'], course_progress['data'])
            current_app.logger.info(f"Quiz lesson 0 (step1) completed for course {course_id} by session {session['sid']}")
            return redirect(url_for('quiz.step2a', course_id=course_id))
        return render_template('quiz_step1.html', form=form, course_id=course_id)
    except Exception as e:
        current_app.logger.exception(f"Error in quiz.step1: {str(e)}")
        flash('quiz_error_personal_info', 'danger')
        return render_template('quiz_step1.html', form=form, course_id=course_id)

@quiz_bp.route('/step2a', methods=['GET', 'POST'])
def step2a():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    course_id = request.args.get('course_id', 'financial_quiz')
    if 'quiz_questions' not in session:
        session['quiz_questions'] = random.sample(QUESTION_POOL, 10)
    questions = session['quiz_questions'][:5]
    form = Step2Form(questions, form_type='step2a')
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['quiz_step2a'] = {q['key']: getattr(form, q['key']).data for q in questions}
            current_app.logger.debug(f"Quiz step2a form data: {session['quiz_step2a']}")
            progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
            progress = progress_storage.filter_by_session(session['sid'])
            course_progress = next((p for p in progress if p['data']['course_id'] == course_id), None)
            if course_progress and 1 not in course_progress['data']['completed_lessons']:
                course_progress['data']['completed_lessons'].append(1)
                course_progress['data']['progress_percentage'] = (len(course_progress['data']['completed_lessons']) / 4) * 100
                course_progress['data']['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                progress_storage.update_by_id(course_progress['id'], course_progress['data'])
            current_app.logger.info(f"Quiz lesson 1 (step2a) completed for course {course_id} by session {session['sid']}")
            return redirect(url_for('quiz.step2b', course_id=course_id))
        return render_template('quiz_step2a.html', form=form, questions=questions, course_id=course_id)
    except Exception as e:
        current_app.logger.exception(f"Error in quiz.step2a: {str(e)}")
        flash('quiz_error_quiz_answers', 'danger')
        return render_template('quiz_step2a.html', form=form, questions=questions, course_id=course_id)

@quiz_bp.route('/step2b', methods=['GET', 'POST'])
def step2b():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    course_id = request.args.get('course_id', 'financial_quiz')
    if 'quiz_questions' not in session:
        session['quiz_questions'] = random.sample(QUESTION_POOL, 10)
    questions = session['quiz_questions'][5:]
    form = Step2Form(questions, form_type='step2b')
    try:
        if request.method == 'POST' and form.validate_on_submit():
            answers = session.get('quiz_step2a', {})
            answers.update({q['key']: getattr(form, q['key']).data for q in questions})
            score = sum(
                3 if v == 'always' else 2 if v == 'often' else 1 if v == 'sometimes' else 0
                for v in answers.values()
            )
            personality = (
                'Planner' if score >= 24 else
                'Saver' if score >= 18 else
                'Balanced' if score >= 12 else
                'Spender'
            )
            badges = []
            if score >= 24:
                badges.append('Financial Guru')
            if score >= 18:
                badges.append('Savings Star')
            if answers.get('avoid_debt') in ['always', 'often']:
                badges.append('Debt Dodger')
            if answers.get('set_financial_goals') in ['always', 'often']:
                badges.append('Goal Setter')
            
            quiz_storage = current_app.config['STORAGE_MANAGERS']['quiz']
            record = {
                "id": str(uuid.uuid4()),
                "data": {
                    "first_name": session.get('quiz_step1', {}).get('first_name', ''),
                    "email": session.get('quiz_step1', {}).get('email', ''),
                    "answers": answers,
                    "score": score,
                    "personality": personality,
                    "badges": badges,
                    "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }
            email = session.get('quiz_step1', {}).get('email')
            send_email_flag = session.get('quiz_step1', {}).get('send_email', False)
            quiz_storage.append(record, user_email=email, session_id=session['sid'])
            
            if send_email_flag and email:
                send_email(
                    to_email=email,
                    subject='quiz_results_subject',
                    template_name="quiz_email.html",
                    data={
                        "first_name": record["data"]["first_name"],
                        "score": score,
                        "personality": personality,
                        "badges": badges,
                        "created_at": record["data"]["created_at"],
                        "cta_url": url_for('quiz.results', _external=True)
                    }
                )
            
            progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
            progress = progress_storage.filter_by_session(session['sid'])
            course_progress = next((p for p in progress if p['data']['course_id'] == course_id), None)
            if not course_progress:
                progress_data = {
                    'course_id': course_id,
                    'completed_lessons': [0, 1, 2],
                    'progress_percentage': (3/4) * 100,
                    'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                progress_storage.append(progress_data, session_id=session['sid'])
            else:
                if 2 not in course_progress['data']['completed_lessons']:
                    course_progress['data']['completed_lessons'].append(2)
                    course_progress['data']['progress_percentage'] = (len(course_progress['data']['completed_lessons']) / 4) * 100
                    course_progress['data']['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    progress_storage.update_by_id(course_progress['id'], course_progress['data'])
            
            current_app.logger.info(f"Quiz lesson 2 (step2b) completed for course {course_id} by session {session['sid']}")
            session.pop('quiz_step1', None)
            session.pop('quiz_step2a', None)
            session.pop('quiz_questions', None)
            flash('quiz_completed_success', 'success')
            return redirect(url_for('quiz.results', course_id=course_id))
        return render_template('quiz_step2b.html', form=form, questions=questions, course_id=course_id)
    except Exception as e:
        current_app.logger.exception(f"Error in quiz.step2b: {str(e)}")
        flash('quiz_error_quiz_answers', 'danger')
        return render_template('quiz_step2b.html', form=form, questions=questions, course_id=course_id)

@quiz_bp.route('/results', methods=['GET', 'POST'])
def results():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    course_id = request.args.get('course_id', 'financial_quiz')
    try:
        quiz_storage = current_app.config['STORAGE_MANAGERS']['quiz']
        user_data = quiz_storage.filter_by_session(session['sid'])
        records = [(record["id"], record["data"]) for record in user_data]
        latest_record = records[-1][1] if records else {}
        
        insights = []
        tips = [
            'quiz_tip_automate_savings',
            'quiz_tip_ajo_savings',
            'quiz_tip_learn_skills',
            'quiz_tip_track_expenses'
        ]
        if latest_record:
            if latest_record.get('personality') == 'Spender':
                insights.append('quiz_insight_high_spending')
                tips.append('quiz_tip_use_budgeting_app')
            if latest_record.get('score', 0) < 18:
                insights.append('quiz_insight_low_discipline')
            if latest_record.get('answers', {}).get('emergency_fund') in ['never', 'sometimes']:
                insights.append('quiz_insight_no_emergency_fund')
                tips.append('quiz_tip_emergency_fund')
            if latest_record.get('answers', {}).get('invest_money') in ['always', 'often']:
                insights.append('quiz_insight_good_investment')
        
        return render_template(
            'quiz_results.html',
            records=records,
            latest_record=latest_record,
            insights=insights,
            tips=tips,
            course_id=course_id
        )
    except Exception as e:
        current_app.logger.exception(f"Error in quiz.results: {str(e)}")
        flash('quiz_error_loading_results', 'danger')
        return render_template(
            'quiz_results.html',
            records=[],
            latest_record={},
            insights=[],
            tips=[
                'quiz_tip_automate_savings',
                'quiz_tip_ajo_savings',
                'quiz_tip_learn_skills',
                'quiz_tip_track_expenses'
            ],
            course_id=course_id
        )
