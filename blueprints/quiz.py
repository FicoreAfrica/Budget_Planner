from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from flask_wtf import FlaskForm
from flask_mail import Message
from wtforms import StringField, SelectField, BooleanField, SubmitField, RadioField
from wtforms.validators import DataRequired, Email, Optional
import uuid
from datetime import datetime
import pandas as pd
import threading
import logging
from translations import trans

# Configure logging
logger = logging.getLogger('ficore_app')

# Define the quiz blueprint
quiz_bp = Blueprint('quiz', __name__, template_folder='templates', static_folder='static', url_prefix='/quiz')

# Define QUESTION_KEYS
QUESTION_KEYS = [
    'track_expenses', 'save_regularly', 'spend_non_essentials', 'plan_expenses',
    'impulse_purchases', 'use_budgeting_tools', 'invest_money', 'emergency_fund',
    'set_financial_goals', 'seek_financial_advice'
]

# Hardcode QUIZ_QUESTIONS
QUIZ_QUESTIONS = [
    {
        'text': 'Do you track your expenses regularly?',
        'text_key': 'quiz_track_expenses_label',
        'type': 'radio',
        'options': ['Yes', 'No'],
        'positive_answers': ['Yes'],
        'negative_answers': ['No'],
        'weight': 1
    },
    {
        'text': 'Do you save a portion of your income regularly?',
        'text_key': 'quiz_save_regularly_label',
        'type': 'radio',
        'options': ['Yes', 'No'],
        'positive_answers': ['Yes'],
        'negative_answers': ['No'],
        'weight': 1
    },
    {
        'text': 'Do you often spend on non-essential items?',
        'text_key': 'quiz_spend_non_essentials_label',
        'type': 'radio',
        'options': ['Yes', 'No'],
        'positive_answers': ['No'],
        'negative_answers': ['Yes'],
        'weight': 1
    },
    {
        'text': 'Do you plan your monthly expenses in advance?',
        'text_key': 'quiz_plan_expenses_label',
        'type': 'radio',
        'options': ['Yes', 'No'],
        'positive_answers': ['Yes'],
        'negative_answers': ['No'],
        'weight': 1
    },
    {
        'text': 'Do you make impulse purchases frequently?',
        'text_key': 'quiz_impulse_purchases_label',
        'type': 'radio',
        'options': ['Yes', 'No'],
        'positive_answers': ['No'],
        'negative_answers': ['Yes'],
        'weight': 1
    },
    {
        'text': 'Do you use budgeting tools or apps?',
        'text_key': 'quiz_use_budgeting_tools_label',
        'type': 'radio',
        'options': ['Yes', 'No'],
        'positive_answers': ['Yes'],
        'negative_answers': ['No'],
        'weight': 1
    },
    {
        'text': 'Do you invest your money?',
        'text_key': 'quiz_invest_money_label',
        'type': 'radio',
        'options': ['Yes', 'No'],
        'positive_answers': ['Yes'],
        'negative_answers': ['No'],
        'weight': 1
    },
    {
        'text': 'Do you have an emergency fund?',
        'text_key': 'quiz_emergency_fund_label',
        'type': 'radio',
        'options': ['Yes', 'No'],
        'positive_answers': ['Yes'],
        'negative_answers': ['No'],
        'weight': 1
    },
    {
        'text': 'Do you set financial goals?',
        'text_key': 'quiz_set_financial_goals_label',
        'type': 'radio',
        'options': ['Yes', 'No'],
        'positive_answers': ['Yes'],
        'negative_answers': ['No'],
        'weight': 1
    },
    {
        'text': 'Do you seek financial advice from professionals?',
        'text_key': 'quiz_seek_financial_advice_label',
        'type': 'radio',
        'options': ['Yes', 'No'],
        'positive_answers': ['Yes'],
        'negative_answers': ['No'],
        'weight': 1
    },
]

def init_quiz_questions(app):
    """Initialize QUIZ_QUESTIONS with IDs and keys."""
    global QUIZ_QUESTIONS
    with app.app_context():
        for i, key in enumerate(QUESTION_KEYS):
            QUIZ_QUESTIONS[i]['id'] = f'question_{i+1}'
            QUIZ_QUESTIONS[i]['key'] = key
        logger.debug(f"Initialized QUIZ_QUESTIONS: {[q['id'] for q in QUIZ_QUESTIONS]}")

# Define the QuizForm
class QuizForm(FlaskForm):
    first_name = StringField(
        trans('core_first_name', default='First Name'),
        validators=[DataRequired()],
        render_kw={
            'placeholder': trans('core_first_name_placeholder', default='e.g., Muhammad, Bashir, Umar'),
            'title': trans('core_first_name_title', default='Enter your first name to personalize your quiz results')
        }
    )
    email = StringField(
        trans('core_email', default='Email'),
        validators=[DataRequired(), Email()],
        render_kw={
            'placeholder': trans('core_email_placeholder', default='e.g., muhammad@example.com'),
            'title': trans('core_email_title', default='Enter your email to receive quiz results')
        }
    )
    language = SelectField(
        trans('core_language', default='Language'),
        choices=[('en', trans('core_language_en', default='English')), ('ha', trans('core_language_ha', default='Hausa'))],
        default='en',
        validators=[Optional()]
    )
    send_email = BooleanField(
        trans('core_send_email', default='Send Email'),
        default=False,
        validators=[Optional()],
        render_kw={'title': trans('core_send_email_title', default='Check to receive an email with your quiz results')}
    )
    submit = SubmitField(trans('core_next', default='Next'))
    back = SubmitField(trans('core_back', default='Back'))

    def __init__(self, questions=None, language='en', formdata=None, personal_info=True, **kwargs):
        super().__init__(formdata=formdata, **kwargs)
        self.questions = questions or []
        logger.debug(f"Initializing QuizForm with personal_info={personal_info}, questions: {[q['id'] for q in self.questions]}, formdata={formdata}")

        if not personal_info:
            for q in self.questions:
                field_name = q['id']
                question_key = q.get('key', '')
                label_key = q.get('text_key', '')
                tooltip_key = f"quiz_{question_key}_tooltip"
                placeholder_key = f"quiz_{question_key}_placeholder"
                translated_text = trans(label_key, default=q['text'])
                translated_options = [(opt, trans(opt, default=opt)) for opt in q['options']]
                field = RadioField(
                    translated_text,
                    validators=[DataRequired() if q.get('required', True) else Optional()],
                    choices=translated_options,
                    id=field_name,
                    render_kw={
                        'title': trans(tooltip_key, default=''),
                        'placeholder': trans(placeholder_key, default='Select an option')
                    }
                )
                self._fields[field_name] = field
                logger.debug(f"Added field {field_name} with translated text '{translated_text}'")

    def validate(self, extra_validators=None):
        logger.debug(f"Validating QuizForm with fields: {list(self._fields.keys())}, data: {self.data}")
        rv = super().validate(extra_validators)
        if not rv:
            logger.error(f"Validation failed with errors: {self.errors}")
        return rv

# Helper Functions
def calculate_score(answers):
    score = 0
    for q, a in answers:
        positive = q.get('positive_answers', ['Yes'])
        negative = q.get('negative_answers', ['No'])
        if a in positive:
            score += 3
        elif a in negative:
            score -= 1
    return max(0, score)

def assign_personality(answers, language='en'):
    score = 0
    for q, a in answers:
        weight = q.get('weight', 1)
        positive = [trans(opt, default=opt) for opt in q.get('positive_answers', ['Yes'])]
        negative = [trans(opt, default=opt) for opt in q.get('negative_answers', ['No'])]
        if a in positive:
            score += weight
        elif a in negative:
            score -= weight
    if score >= 6:
        return 'Planner', trans('planner_desc', default='You plan your finances well.'), trans('planner_tip', default='Save regularly.')
    elif score >= 2:
        return 'Saver', trans('saver_desc', default='You save consistently.'), trans('saver_tip', default='Increase your savings rate.')
    elif score >= 0:
        return 'Balanced', trans('balanced_desc', default='You maintain a balanced approach.'), trans('balanced_tip', default='Consider a budget.')
    elif score >= -2:
        return 'Spender', trans('spender_desc', default='You enjoy spending.'), trans('spender_tip', default='Track your expenses.')
    else:
        return 'Avoider', trans('avoider_desc', default='You avoid financial planning.'), trans('avoider_tip', default='Start with a simple plan.')

def assign_badges_quiz(user_df, all_users_df, language='en'):
    badges = []
    if user_df.empty:
        logger.warning("Empty user_df in assign_badges_quiz.")
        return badges
    try:
        user_df['Timestamp'] = pd.to_datetime(user_df['Timestamp'], errors='coerce')
        user_df = user_df.sort_values('Timestamp', ascending=False)
        user_row = user_df.iloc[0]
        if len(user_df) >= 1:
            badges.append(trans('badge_first_quiz', default='First Quiz Completed!'))
        if user_row['personality'] == 'Planner':
            badges.append(trans('badge_financial_guru', default='Financial Guru'))
        elif user_row['personality'] == 'Saver':
            badges.append(trans('badge_savings_star', default='Savings Star'))
        elif user_row['personality'] == 'Avoider' and len(all_users_df) > 10:
            badges.append(trans('badge_needs_guidance', default='Needs Guidance!'))
        return badges
    except Exception as e:
        logger.error(f"Error in assign_badges_quiz: {str(e)}")
        return badges

def generate_insights_and_tips(personality, language='en'):
    insights = []
    tips = []
    if personality == 'Planner':
        insights.append(trans('planner_insight', default='You have a strong grasp of financial planning.'))
        tips.append(trans('planner_tip', default='Continue setting long-term financial goals.'))
    elif personality == 'Saver':
        insights.append(trans('saver_insight', default='You excel at saving regularly.'))
        tips.append(trans('saver_tip', default='Consider investing to grow your savings.'))
    elif personality == 'Balanced':
        insights.append(trans('balanced_insight', default='You balance saving and spending well.'))
        tips.append(trans('balanced_tip', default='Try using a budgeting app to optimize your habits.'))
    elif personality == 'Spender':
        insights.append(trans('spender_insight', default='You enjoy spending, which can be a strength.'))
        tips.append(trans('spender_tip', default='Start tracking expenses to avoid overspending.'))
    elif personality == 'Avoider':
        insights.append(trans('avoider_insight', default='You may find financial planning challenging.'))
        tips.append(trans('avoider_tip', default='Begin with small steps, like a monthly budget.'))
    return insights, tips

def send_quiz_email(to_email, user_name, personality, personality_desc, tip, language):
    try:
        msg = Message(
            subject=trans('quiz_report_subject', default='Your Quiz Report'),
            recipients=[to_email],
            html=render_template(
                'quiz_email.html',
                user_name=user_name or 'User',
                personality=personality,
                personality_desc=personality_desc,
                tip=tip,
                base_url=current_app.config.get('BASE_URL', ''),
                FEEDBACK_FORM_URL=current_app.config.get('FEEDBACK_FORM_URL', ''),
                WAITLIST_FORM_URL=current_app.config.get('WAITLIST_FORM_URL', ''),
                CONSULTANCY_FORM_URL=current_app.config.get('CONSULTANCY_FORM_URL', ''),
                LINKEDIN_URL=current_app.config.get('LINKEDIN_URL', ''),
                TWITTER_URL=current_app.config.get('TWITTER_URL', ''),
                language=language
            )
        )
        current_app.extensions['mail'].send(msg)
        logger.info(f"Quiz email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Error sending quiz email to {to_email}: {str(e)}")
        return False

def send_quiz_email_async(app, to_email, user_name, personality, personality_desc, tip, language):
    try:
        with app.app_context():
            send_quiz_email(to_email, user_name, personality, personality_desc, tip, language)
    except Exception as e:
        logger.error(f"Async email sending failed: {str(e)}")

# Routes
@quiz_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    if not QUIZ_QUESTIONS:
        flash(trans('quiz_config_error', default='Quiz configuration error. Please try again later.'), 'danger')
        return redirect(url_for('index'))

    try:
        if 'sid' not in session:
            session['sid'] = str(uuid.uuid4())
            session.modified = True
            logger.debug(f"New session created with sid: {session['sid']}")
    except Exception as e:
        logger.error(f"Session initialization failed: {str(e)}")
        flash(trans('session_error', default='Session error. Please try again.'), 'danger')
        return redirect(url_for('index'))

    language = session.get('language', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')

    form = QuizForm(language=language, personal_info=True, formdata=request.form if request.method == 'POST' else None)
    form.submit.label.text = trans('quiz_start_quiz', default='Start Quiz')

    if request.method == 'POST':
        logger.debug(f"Received POST data: {request.form}")
        if form.validate_on_submit():
            try:
                session['quiz_data'] = {
                    'first_name': form.first_name.data,
                    'email': form.email.data,
                    'language': form.language.data or 'en',
                    'send_email': form.send_email.data
                }
                session['language'] = form.language.data or 'en'
                session.modified = True
                logger.info(f"Quiz step 1 validated successfully, session updated: {session['quiz_data']}")

                progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
                progress = progress_storage.filter_by_session(session['sid'])
                course_progress = next((p for p in progress if p['data'].get('course_id') == course_id), None)
                if not course_progress:
                    progress_data = {
                        'course_id': course_id,
                        'completed_lessons': [0],
                        'progress_percentage': (1/3) * 100,
                        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    progress_storage.append(progress_data, session_id=session['sid'])
                else:
                    if 0 not in course_progress['data'].get('completed_lessons', []):
                        course_progress['data']['completed_lessons'].append(0)
                        course_progress['data']['progress_percentage'] = (len(course_progress['data']['completed_lessons']) / 3) * 100
                        course_progress['data']['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        progress_storage.update_by_id(course_progress['id'], course_progress['data'])
                logger.info(f"Quiz lesson 0 (step1) completed for course {course_id} by session {session['sid']}")

                return redirect(url_for('quiz.step2a', course_id=course_id))
            except Exception as e:
                logger.error(f"Error processing step1 POST: {str(e)}")
                flash(trans('server_error', default='An error occurred. Please try again.'), 'danger')
        else:
            logger.error(f"Form validation failed: {form.errors}")
            flash(trans('form_errors', default='Please correct the errors below'), 'danger')

    logger.debug(f"Rendering step1 with session: {session}")
    return render_template(
        'quiz_step1.html',
        form=form,
        course_id=course_id,
        base_url=current_app.config.get('BASE_URL', ''),
        FEEDBACK_FORM_URL=current_app.config.get('FEEDBACK_FORM_URL', ''),
        WAITLIST_FORM_URL=current_app.config.get('WAITLIST_FORM_URL', ''),
        CONSULTANCY_FORM_URL=current_app.config.get('CONSULTANCY_FORM_URL', ''),
        LINKEDIN_URL=current_app.config.get('LINKEDIN_URL', ''),
        TWITTER_URL=current_app.config.get('TWITTER_URL', ''),
        language=language,
        total_steps=3
    )

@quiz_bp.route('/step2a', methods=['GET', 'POST'])
def step2a():
    if not QUIZ_QUESTIONS:
        flash(trans('quiz_config_error', default='Quiz configuration error. Please try again later.'), 'danger')
        return redirect(url_for('index'))

    try:
        if 'sid' not in session or 'quiz_data' not in session:
            flash(trans('session_expired', default='Session expired. Please start again.'), 'danger')
            return redirect(url_for('quiz.step1', course_id=request.args.get('course_id', 'financial_quiz')))
    except Exception as e:
        logger.error(f"Session check failed: {str(e)}")
        flash(trans('session_error', default='Session error. Please try again.'), 'danger')
        return redirect(url_for('index'))

    language = session.get('language', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')

    preprocessed_questions = [
        {
            'id': q['id'],
            'key': q.get('key', ''),
            'text_key': q.get('text_key', ''),
            'label': trans(q['text_key'], default=q['text']),
            'text': trans(q['text_key'], default=q['text']),
            'type': q['type'],
            'options': [trans(opt, default=opt) for opt in q['options']],
            'required': q.get('required', True),
            'positive_answers': q.get('positive_answers', ['Yes']),
            'negative_answers': q.get('negative_answers', ['No']),
            'weight': q.get('weight', 1),
            'tooltip': trans(f"quiz_{q.get('key', '')}_tooltip", default=''),
            'placeholder': trans(f"quiz_{q.get('key', '')}_placeholder", default='Select an option')
        }
        for q in QUIZ_QUESTIONS[:5]
    ]

    form = QuizForm(questions=preprocessed_questions, language=language, personal_info=False, formdata=request.form if request.method == 'POST' else None)
    form.submit.label.text = trans('core_continue', default='Continue')
    form.back.label.text = trans('core_back', default='Back')

    if request.method == 'POST':
        logger.debug(f"Received POST data for step2a: {request.form}")
        if form.validate_on_submit():
            try:
                session['quiz_data'].update({
                    q['id']: form[q['id']].data for q in preprocessed_questions if q['id'] in form._fields
                })
                session.modified = True
                logger.info(f"Quiz step 2a validated successfully, session updated: {session['quiz_data']}")

                progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
                progress = progress_storage.filter_by_session(session['sid'])
                course_progress = next((p for p in progress if p['data'].get('course_id') == course_id), None)
                if course_progress and 1 not in course_progress['data'].get('completed_lessons', []):
                    course_progress['data']['completed_lessons'].append(1)
                    course_progress['data']['progress_percentage'] = (len(course_progress['data']['completed_lessons']) / 3) * 100
                    course_progress['data']['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    progress_storage.update_by_id(course_progress['id'], course_progress['data'])
                logger.info(f"Quiz lesson 1 (step2a) completed for course {course_id} by session {session['sid']}")

                return redirect(url_for('quiz.step2b', course_id=course_id))
            except Exception as e:
                logger.error(f"Error processing step2a POST: {str(e)}")
                flash(trans('server_error', default='An error occurred. Please try again.'), 'danger')
        else:
            logger.error(f"Form validation failed in step2a: {form.errors}")
            flash(trans('form_errors', default='Please correct the errors below'), 'danger')

    if 'quiz_data' in session:
        for q in preprocessed_questions:
            if q['id'] in session['quiz_data']:
                form[q['id']].data = session['quiz_data'][q['id']]

    return render_template(
        'quiz_step.html',
        form=form,
        questions=preprocessed_questions,
        course_id=course_id,
        base_url=current_app.config.get('BASE_URL', ''),
        FEEDBACK_FORM_URL=current_app.config.get('FEEDBACK_FORM_URL', ''),
        WAITLIST_FORM_URL=current_app.config.get('WAITLIST_FORM_URL', ''),
        CONSULTANCY_FORM_URL=current_app.config.get('CONSULTANCY_FORM_URL', ''),
        LINKEDIN_URL=current_app.config.get('LINKEDIN_URL', ''),
        TWITTER_URL=current_app.config.get('TWITTER_URL', ''),
        language=language,
        step_num=2,
        total_steps=3
    )

@quiz_bp.route('/step2b', methods=['GET', 'POST'])
def step2b():
    if not QUIZ_QUESTIONS:
        flash(trans('quiz_config_error', default='Quiz configuration error. Please try again later.'), 'danger')
        return redirect(url_for('index'))

    try:
        if 'sid' not in session or 'quiz_data' not in session:
            flash(trans('session_expired', default='Session expired. Please start again.'), 'danger')
            return redirect(url_for('quiz.step1', course_id=request.args.get('course_id', 'financial_quiz')))
    except Exception as e:
        logger.error(f"Session check failed: {str(e)}")
        flash(trans('session_error', default='Session error. Please try again.'), 'danger')
        return redirect(url_for('index'))

    language = session.get('language', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')

    preprocessed_questions = [
        {
            'id': q['id'],
            'key': q.get('key', ''),
            'text_key': q.get('text_key', ''),
            'label': trans(q['text_key'], default=q['text']),
            'text': trans(q['text_key'], default=q['text']),
            'type': q['type'],
            'options': [trans(opt, default=opt) for opt in q['options']],
            'required': q.get('required', True),
            'positive_answers': q.get('positive_answers', ['Yes']),
            'negative_answers': q.get('negative_answers', ['No']),
            'weight': q.get('weight', 1),
            'tooltip': trans(f"quiz_{q.get('key', '')}_tooltip", default=''),
            'placeholder': trans(f"quiz_{q.get('key', '')}_placeholder", default='Select an option')
        }
        for q in QUIZ_QUESTIONS[5:10]
    ]

    form = QuizForm(questions=preprocessed_questions, language=language, personal_info=False, formdata=request.form if request.method == 'POST' else None)
    form.submit.label.text = trans('quiz_see_results', default='See Results')
    form.back.label.text = trans('core_back', default='Back')

    if request.method == 'POST':
        logger.debug(f"Received POST data for step2b: {request.form}")
        if form.validate_on_submit():
            try:
                session['quiz_data'].update({
                    q['id']: form[q['id']].data for q in preprocessed_questions if q['id'] in form._fields
                })
                session.modified = True
                logger.info(f"Quiz step 2b validated successfully, session updated: {session['quiz_data']}")

                answers = [(QUIZ_QUESTIONS[int(k.split('_')[1]) - 1], v) for k, v in session['quiz_data'].items() if k.startswith('question_')]
                personality, personality_desc, tip = assign_personality(answers, language)
                score = calculate_score(answers)
                user_df = pd.DataFrame([{
                    'Timestamp': datetime.utcnow(),
                    'first_name': session['quiz_data'].get('first_name', ''),
                    'email': session['quiz_data'].get('email', ''),
                    'language': session['quiz_data'].get('language', 'en'),
                    'personality': personality,
                    'score': score,
                    **{f'question_{i}': trans(QUIZ_QUESTIONS[i-1]['text_key'], default=QUIZ_QUESTIONS[i-1]['text']) for i in range(1, 11)},
                    **{f'answer_{i}': session['quiz_data'].get(f'question_{i}', '') for i in range(1, 11)}
                }])

                storage_managers = current_app.config['STORAGE_MANAGERS']
                all_users_df = storage_managers['quiz'].read_all()
                all_users_df = pd.DataFrame([r['data'] for r in all_users_df if 'data' in r])

                badges = assign_badges_quiz(user_df, all_users_df, language)
                data = {
                    'Timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
                    'first_name': session['quiz_data'].get('first_name', ''),
                    'email': session['quiz_data'].get('email', ''),
                    'language': session['quiz_data'].get('language', 'en'),
                    **{f'question_{i}': trans(QUIZ_QUESTIONS[i-1]['text_key'], default=QUIZ_QUESTIONS[i-1]['text']) for i in range(1, 11)},
                    **{f'answer_{i}': session['quiz_data'].get(f'question_{i}', '') for i in range(1, 11)},
                    'personality': personality,
                    'score': str(score),
                    'badges': ','.join(badges),
                    'send_email': str(session['quiz_data'].get('send_email', False)).lower()
                }

                storage_managers['quiz'].append(data, session_id=session['sid'])

                progress_storage = storage_managers['user_progress']
                progress = progress_storage.filter_by_session(session['sid'])
                course_progress = next((p for p in progress if p['data'].get('course_id') == course_id), None)
                if course_progress and 2 not in course_progress['data'].get('completed_lessons', []):
                    course_progress['data']['completed_lessons'].append(2)
                    course_progress['data']['progress_percentage'] = (len(course_progress['data']['completed_lessons']) / 3) * 100
                    course_progress['data']['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    progress_storage.update_by_id(course_progress['id'], course_progress['data'])
                logger.info(f"Quiz lesson 2 (step2b) completed for course {course_id} by session {session['sid']}")

                records = []
                if not all_users_df.empty:
                    user_records = all_users_df[all_users_df['email'] == session['quiz_data'].get('email', '')].sort_values('Timestamp', ascending=False)
                    for idx, row in user_records.iterrows():
                        records.append((idx, {
                            'created_at': row['Timestamp'].strftime('%Y-%m-%d %H:%M:%S') if pd.notna(row['Timestamp']) else 'N/A',
                            'personality': row['personality'],
                            'score': int(row['score']) if pd.notna(row['score']) else 0,
                            'badges': row['badges'].split(',') if pd.notna(row['badges']) and row['badges'] else []
                        }))

                latest_record = records[0][1] if records else None
                insights, tips = generate_insights_and_tips(personality, language)
                results = {
                    'first_name': session['quiz_data'].get('first_name', ''),
                    'personality': personality,
                    'score': score,
                    'badges': badges,
                    'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
                }
                session['quiz_results'] = {
                    'latest_record': results,
                    'records': records,
                    'insights': insights,
                    'tips': tips
                }
                session.modified = True

                if session['quiz_data'].get('send_email') and session['quiz_data'].get('email'):
                    try:
                        threading.Thread(
                            target=send_quiz_email_async,
                            args=(current_app._get_current_object(), session['quiz_data']['email'], session['quiz_data']['first_name'], personality, personality_desc, tip, language)
                        ).start()
                        flash(trans('email_sent', default='Check your inbox for results.'), 'success')
                    except Exception as e:
                        logger.error(f"Failed to start email thread: {str(e)}")
                        flash(trans('email_error', default='Failed to send email. Please try again later.'), 'danger')

                flash(trans('submission_success', default='Submission successful!'), 'success')
                return redirect(url_for('quiz.results', course_id=course_id))
            except Exception as e:
                logger.error(f"Error processing step2b POST: {str(e)}")
                flash(trans('server_error', default='An error occurred. Please try again.'), 'danger')
        else:
            logger.error(f"Form validation failed in step2b: {form.errors}")
            flash(trans('form_errors', default='Please correct the errors below'), 'danger')

    if 'quiz_data' in session:
        for q in preprocessed_questions:
            if q['id'] in session['quiz_data']:
                form[q['id']].data = session['quiz_data'][q['id']]

    return render_template(
        'quiz_step.html',
        form=form,
        questions=preprocessed_questions,
        course_id=course_id,
        base_url=current_app.config.get('BASE_URL', ''),
        FEEDBACK_FORM_URL=current_app.config.get('FEEDBACK_FORM_URL', ''),
        WAITLIST_FORM_URL=current_app.config.get('WAITLIST_FORM_URL', ''),
        CONSULTANCY_FORM_URL=current_app.config.get('CONSULTANCY_FORM_URL', ''),
        LINKEDIN_URL=current_app.config.get('LINKEDIN_URL', ''),
        TWITTER_URL=current_app.config.get('TWITTER_URL', ''),
        language=language,
        step_num=3,
        total_steps=3
    )

@quiz_bp.route('/results', methods=['GET'])
def results():
    try:
        language = session.get('language', 'en')
        course_id = request.args.get('course_id', 'financial_quiz')
        results = session.get('quiz_results', {})

        if not results:
            flash(trans('session_expired', default='Session expired. Please start again.'), 'danger')
            return redirect(url_for('quiz.step1', course_id=course_id))

        session.pop('quiz_data', None)
        session.pop('quiz_results', None)
        session.modified = True
    except Exception as e:
        logger.error(f"Session access failed: {str(e)}")
        flash(trans('session_error', default='Session error. Please try again.'), 'danger')
        return redirect(url_for('index'))

    return render_template(
        'quiz_results.html',
        latest_record=results.get('latest_record', {}),
        records=results.get('records', []),
        insights=results.get('insights', []),
        tips=results.get('tips', []),
        course_id=course_id,
        base_url=current_app.config.get('BASE_URL', ''),
        FEEDBACK_FORM_URL=current_app.config.get('FEEDBACK_FORM_URL', ''),
        WAITLIST_FORM_URL=current_app.config.get('WAITLIST_FORM_URL', ''),
        CONSULTANCY_FORM_URL=current_app.config.get('CONSULTANCY_FORM_URL', ''),
        LINKEDIN_URL=current_app.config.get('LINKEDIN_URL', ''),
        TWITTER_URL=current_app.config.get('TWITTER_URL', ''),
        language=language
    )
