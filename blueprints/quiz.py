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
try:
    from app import trans  # Import trans from app.py instead
except ImportError:
    def trans(key, lang=None):
        return key  # Fallback to return the key as the translation

quiz_bp = Blueprint('quiz', __name__, url_prefix='/quiz')

QUESTION_KEYS = [
    'track_expenses',
    'save_regularly',
    'spend_non_essentials',
    'plan_expenses',
    'impulse_purchases',
    'use_budgeting_tools',
    'invest_money',
    'emergency_fund',
    'set_financial_goals',
    'seek_financial_advice'
]

class Step1Form(FlaskForm):
    first_name = StringField(trans('quiz_first_name'), validators=[DataRequired(message=trans('quiz_first_name_required'))])
    email = StringField(trans('quiz_email'), validators=[Optional(), Email(message=trans('quiz_email_invalid'))])
    send_email = BooleanField(trans('quiz_send_email'))
    submit = SubmitField(trans('quiz_start_quiz'))

def make_step2_form(questions, form_type='step2a'):
    """
    Dynamically creates a WTForms form class for quiz steps 2a and 2b.
    """
    fields = {}
    for q in questions:
        fields[q['key']] = SelectField(
            label=q['label'],
            choices=[
                ('', trans('quiz_select_answer')),
                ('always', trans('quiz_always')),
                ('often', trans('quiz_often')),
                ('sometimes', trans('quiz_sometimes')),
                ('never', trans('quiz_never'))
            ],
            validators=[DataRequired(message=trans('quiz_answer_required'))],
            description=q.get('tooltip', '')
        )
    submit_label = trans('quiz_continue') if 'step2a' in form_type else trans('quiz_see_results')
    fields['submit'] = SubmitField(submit_label)
    Step2FormClass = type('Step2Form', (FlaskForm,), fields)
    return Step2FormClass()

@quiz_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step1Form()
    course_id = request.args.get('course_id', 'financial_quiz')
    if request.method == 'POST' and form.validate_on_submit():
        session['quiz_step1'] = form.data
        current_app.logger.debug(f"Quiz step1 form data: {form.data}")
        progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
        progress = progress_storage.filter_by_session(session['sid'])
        course_progress = next((p for p in progress if p['data'].get('course_id') == course_id), None)
        if not course_progress:
            progress_data = {
                'course_id': course_id,
                'completed_lessons': [0],
                'progress_percentage': (1/4) * 100,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            progress_storage.append(progress_data, session_id=session['sid'])
        else:
            if 0 not in course_progress['data'].get('completed_lessons', []):
                course_progress['data']['completed_lessons'].append(0)
                course_progress['data']['progress_percentage'] = (len(course_progress['data']['completed_lessons']) / 4) * 100
                course_progress['data']['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                progress_storage.update_by_id(course_progress['id'], course_progress['data'])
        current_app.logger.info(f"Quiz lesson 0 (step1) completed for course {course_id} by session {session['sid']}")
        return redirect(url_for('quiz.step2a', course_id=course_id))
    return render_template('quiz_step1.html', form=form, course_id=course_id)

@quiz_bp.route('/step2a', methods=['GET', 'POST'])
def step2a():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    course_id = request.args.get('course_id', 'financial_quiz')
    if 'quiz_questions' not in session:
        session['quiz_questions'] = random.sample(QUESTION_KEYS, 10)
    question_keys = session['quiz_questions'][:5]
    questions = [
        {
            'key': key,
            'label': trans(f'quiz_{key}_label'),
            'tooltip': trans(f'quiz_{key}_tooltip'),
            'placeholder': trans(f'quiz_{key}_placeholder')
        } for key in question_keys
    ]
    form = make_step2_form(questions, form_type='step2a')
    if request.method == 'POST' and form.validate_on_submit():
        session['quiz_step2a'] = {q['key']: getattr(form, q['key']).data for q in questions}
        current_app.logger.debug(f"Quiz step2a form data: {session['quiz_step2a']}")
        progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
        progress = progress_storage.filter_by_session(session['sid'])
        course_progress = next((p for p in progress if p['data'].get('course_id') == course_id), None)
        if course_progress and 1 not in course_progress['data'].get('completed_lessons', []):
            course_progress['data']['completed_lessons'].append(1)
            course_progress['data']['progress_percentage'] = (len(course_progress['data']['completed_lessons']) / 4) * 100
            course_progress['data']['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            progress_storage.update_by_id(course_progress['id'], course_progress['data'])
        current_app.logger.info(f"Quiz lesson 1 (step2a) completed for course {course_id} by session {session['sid']}")
        return redirect(url_for('quiz.step2b', course_id=course_id))
    return render_template('quiz_step2a.html', form=form, questions=questions, course_id=course_id)

@quiz_bp.route('/step2b', methods=['GET', 'POST'])
def step2b():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    course_id = request.args.get('course_id', 'financial_quiz')
    if 'quiz_questions' not in session:
        session['quiz_questions'] = random.sample(QUESTION_KEYS, 10)
    question_keys = session['quiz_questions'][5:]
    questions = [
        {
            'key': key,
            'label': trans(f'quiz_{key}_label'),
            'tooltip': trans(f'quiz_{key}_tooltip'),
            'placeholder': trans(f'quiz_{key}_placeholder')
        } for key in question_keys
    ]
    form = make_step2_form(questions, form_type='step2b')
    if request.method == 'POST' and form.validate_on_submit():
        answers = session.get('quiz_step2a', {})
        answers.update({q['key']: getattr(form, q['key']).data for q in questions})
        score = sum(
            3 if v == 'always' else 2 if v == 'often' else 1 if v == 'sometimes' else 0
            for v in answers.values()
        )
        # PERSONALITY: don't translate the string here, store a raw value
        if score >= 24:
            personality_key = 'Planner'
        elif score >= 18:
            personality_key = 'Saver'
        elif score >= 12:
            personality_key = 'Balanced'
        else:
            personality_key = 'Spender'
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
                "personality": personality_key,
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
                subject=trans('quiz_results_subject'),
                template_name="quiz_email.html",
                data={
                    "first_name": record["data"]["first_name"],
                    "score": score,
                    "personality": personality_key,
                    "badges": badges,
                    "created_at": record["data"]["created_at"],
                    "cta_url": url_for('quiz.results', _external=True)
                }
            )

        progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
        progress = progress_storage.filter_by_session(session['sid'])
        course_progress = next((p for p in progress if p['data'].get('course_id') == course_id), None)
        if not course_progress:
            progress_data = {
                'course_id': course_id,
                'completed_lessons': [0, 1, 2],
                'progress_percentage': (3/4) * 100,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            progress_storage.append(progress_data, session_id=session['sid'])
        else:
            if 2 not in course_progress['data'].get('completed_lessons', []):
                course_progress['data']['completed_lessons'].append(2)
                course_progress['data']['progress_percentage'] = (len(course_progress['data']['completed_lessons']) / 4) * 100
                course_progress['data']['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                progress_storage.update_by_id(course_progress['id'], course_progress['data'])

        current_app.logger.info(f"Quiz lesson 2 (step2b) completed for course {course_id} by session {session['sid']}")
        session.pop('quiz_step1', None)
        session.pop('quiz_step2a', None)
        session.pop('quiz_questions', None)
        flash(trans('quiz_completed_success'), 'success')
        return redirect(url_for('quiz.results', course_id=course_id))
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
            trans('quiz_tip_automate_savings'),
            trans('quiz_tip_ajo_savings'),
            trans('quiz_tip_learn_skills'),
            trans('quiz_tip_track_expenses')
        ]
        if latest_record:
            if latest_record.get('personality') == 'Spender':
                insights.append(trans('quiz_insight_high_spending'))
                tips.append(trans('quiz_tip_use_budgeting_app'))
            if latest_record.get('score', 0) < 18:
                insights.append(trans('quiz_insight_low_discipline'))
            if latest_record.get('answers', {}).get('emergency_fund') in ['never', 'sometimes']:
                insights.append(trans('quiz_insight_no_emergency_fund'))
                tips.append(trans('quiz_tip_emergency_fund'))
            if latest_record.get('answers', {}).get('invest_money') in ['always', 'often']:
                insights.append(trans('quiz_insight_good_investment'))

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
        flash(trans('quiz_error_loading_results'), 'danger')
        return render_template(
            'quiz_results.html',
            records=[],
            latest_record={},
            insights=[],
            tips=[
                trans('quiz_tip_automate_savings'),
                trans('quiz_tip_ajo_savings'),
                trans('quiz_tip_learn_skills'),
                trans('quiz_tip_track_expenses')
            ],
            course_id=course_id
        )