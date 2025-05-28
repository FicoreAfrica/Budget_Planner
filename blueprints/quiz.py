from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from flask_wtf import FlaskForm
from flask import make_response
from wtforms import StringField, SelectField, BooleanField, SubmitField, RadioField
from wtforms.validators import DataRequired, Email, Optional
import json
import uuid
from datetime import datetime
import pandas as pd
import threading
from translations import trans, get_translations

# Define the quiz blueprint
quiz_bp = Blueprint('quiz', __name__, template_folder='templates', static_folder='static', url_prefix='/quiz')

# Global QUIZ_QUESTIONS will be initialized later
QUIZ_QUESTIONS = []
QUESTION_KEYS = [
    'track_expenses', 'save_regularly', 'spend_non_essentials', 'plan_spending', 'impulse_purchases',
    'use_budget', 'invest_money', 'emergency_fund', 'set_financial_goals', 'seek_financial_advice', 'avoid_debt'
]

def init_quiz_questions(app):
    """Initialize QUIZ_QUESTIONS within app context."""
    global QUIZ_QUESTIONS
    with app.app_context():
        try:
            with open('quiz.json', 'r', encoding='utf-8') as f:
                QUIZ_QUESTIONS = json.load(f)
            app.logger.debug(f"Loaded QUIZ_QUESTIONS: {QUIZ_QUESTIONS}")
            if len(QUIZ_QUESTIONS) != len(QUESTION_KEYS):
                app.logger.error(f"QUIZ_QUESTIONS length {len(QUIZ_QUESTIONS)} does not match expected {len(QUESTION_KEYS)}")
                QUIZ_QUESTIONS = []
                return
            for i, key in enumerate(QUESTION_KEYS):
                QUIZ_QUESTIONS[i]['id'] = f'question_{i+1}'
                QUIZ_QUESTIONS[i]['key'] = key
        except FileNotFoundError:
            app.logger.error("quiz.json file not found.")
            QUIZ_QUESTIONS = []
        except json.JSONDecodeError as e:
            app.logger.error(f"Error decoding quiz.json: {e}")
            QUIZ_QUESTIONS = []

# Define the QuizForm
class QuizForm(FlaskForm):
    first_name = StringField(
        'First Name',
        validators=[DataRequired()],
        render_kw={
            'placeholder': 'e.g., Muhammad, Bashir, Umar',
            'title': 'Enter your first name'
        }
    )
    email = StringField(
        'Email',
        validators=[DataRequired(), Email()],
        render_kw={
            'placeholder': 'e.g., email@example.com',
            'title': 'Enter your email'
        }
    )
    language = SelectField(
        'Language',
        choices=[('en', 'English'), ('ha', 'Hausa')],
        default='en'
    )
    send_email = BooleanField(
        'Send Email',
        default=False,
        render_kw={'title': 'Receive email results'}
    )
    submit = SubmitField('Next')
    back = SubmitField('Back')

    def __init__(self, questions=None, language='en', formdata=None, personal_info=True, **kwargs):
        super().__init__(formdata=formdata, **kwargs)
        self.questions = questions or []
        self.language = language
        with current_app.app_context():
            current_app.logger.debug(f"Initializing QuizForm: questions={[q['id'] for q in self.questions]}, language={language}")

        if not personal_info:
            for q in self.questions:
                field_name = q['id']
                question_key = q.get('key', '')
                label_key = f"quiz_{question_key}_label"
                field = RadioField(
                    label_key,
                    validators=[DataRequired() if q.get('required', True) else Optional()],
                    choices=[(opt, opt) for opt in q['options']],
                    id=field_name,
                    default=q['options'][0] if q['options'] else None,
                    render_kw={
                        'title': f"quiz_{question_key}_tooltip",
                        'placeholder': f"quiz_{question_key}_placeholder"
                    }
                )
                bound_field = field.bind(self, field_name)
                bound_field.process(formdata, self.data.get(field_name, q['options'][0]) if formdata and q['options'] else None)
                self._fields[field_name] = bound_field
                with current_app.app_context():
                    current_app.logger.debug(f"Added field {field_name} with label key '{label_key}'")

        self.first_name.label.text = 'core_first_name'
        self.email.label.text = 'core_email'
        self.language.label.text = 'Language'
        self.send_email.label.text = 'Send Email'
        self.submit.label.text = 'Next'
        self.back.label.text = 'Back'

    def validate(self, extra_validators=None):
        with current_app.app_context():
            current_app.logger.debug(f"Validating QuizForm: fields={list(self._fields.keys())}")
        rv = super().validate(extra_validators)
        if not rv:
            with current_app.app_context():
                current_app.logger.error(f"Validation errors: {self.errors}")
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
    trans = get_translations(language)
    score = 0
    for q, a in answers:
        weight = q.get('weight', 1)
        positive = [trans.get(opt.capitalize(), opt.capitalize()) for opt in q.get('positive_answers', ['Yes'])]
        negative = [trans.get(opt.capitalize(), opt.capitalize()) for opt in q.get('negative_answers', ['No'])]
        if a in positive:
            score += weight
        elif a in negative:
            score -= weight
    if score >= 6:
        return 'Planner', trans.get('Planner', 'You plan well.'), trans.get('Planner Tip', 'Save regularly.')
    elif score >= 2:
        return 'Saver', trans.get('Saver', 'You save consistently.'), trans.get('Saver Tip', 'Increase savings.')
    elif score >= 0:
        return 'Balanced', trans.get('Balanced', 'Balanced approach.'), trans.get('Balanced Tip', 'Use a budget.')
    elif score >= -2:
        return 'Spender', trans.get('Spender', 'You enjoy spending.'), trans.get('Spender Tip', 'Track expenses.')
    else:
        return 'Avoider', trans.get('Avoider', 'You avoid planning.'), trans.get('Avoider Tip', 'Start simple.')

def assign_badges_quiz(user_df, all_users_df, language='en'):
    badges = []
    if user_df.empty:
        with current_app.app_context():
            current_app.logger.warning("Empty user_df in assign_badges_quiz.")
        return badges
    try:
        user_df['Timestamp'] = pd.to_datetime(user_df['Timestamp'], format='mixed', errors='coerce')
        user_df = user_df.sort_values('Timestamp', ascending=False)
        user_row = user_df.iloc[0]
        trans = get_translations(language)
        if len(user_df) >= 1:
            badges.append(trans.get('First Quiz Completed!', 'First Quiz Completed!'))
        if user_row['personality'] == 'Planner':
            badges.append('Financial Guru')
        elif user_row['personality'] == 'Saver':
            badges.append('Savings Star')
        elif user_row['personality'] == 'Avoider' and len(all_users_df) > 10:
            badges.append('Needs Guidance!')
        return badges
    except Exception as e:
        with current_app.app_context():
            current_app.logger.error(f"Error in assign_badges_quiz: {e}")
        return badges

def generate_insights_and_tips(personality, language='en'):
    trans = get_translations(language)
    insights = []
    tips = []
    if personality == 'Planner':
        insights.append(trans.get('Planner Insight', 'Strong financial planning.'))
        tips.append(trans.get('Planner Tip', 'Set long-term goals.'))
    elif personality == 'Saver':
        insights.append(trans.get('Saver Insight', 'Excellent at saving.'))
        tips.append(trans.get('Saver Tip', 'Consider investing.'))
    elif personality == 'Balanced':
        insights.append(trans.get('Balanced Insight', 'Balanced saving/spending.'))
        tips.append(trans.get('Balanced Tip', 'Optimize with a budgeting app.'))
    elif personality == 'Spender':
        insights.append(trans.get('Spender Insight', 'Enjoy spending.'))
        tips.append(trans.get('Spender Tip', 'Track expenses.'))
    elif personality == 'Avoider':
        insights.append(trans.get('Avoider Insight', 'Planning is challenging.'))
        tips.append(trans.get('Avoider Tip', 'Start with a budget.'))
    return insights, tips

def send_quiz_email(to_email, user_name, personality, personality_desc, tip, language):
    from flask_mail import Message
    trans = get_translations(language)
    try:
        msg = Message(
            subject=trans.get('Quiz Report Subject', 'Your Quiz Report'),
            recipients=[to_email],
            html=render_template(
                'quiz_email.html',
                trans=trans,
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
        with current_app.app_context():
            current_app.logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        with current_app.app_context():
            current_app.logger.error(f"Email error to {to_email}: {e}")
        return False

def send_quiz_email_async(app, to_email, user_name, personality, personality_desc, tip, language):
    with app.app_context():
        send_quiz_email(to_email, user_name, personality, personality_desc, tip, language)

# Setup session before every request
@quiz_bp.before_request
def setup_session():
    """Ensure session ID and language are set for all quiz routes."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        current_app.logger.debug(f"Initialized new session ID: {session['sid']}")
    if 'language' not in session:
        session['language'] = 'en'
        current_app.logger.debug(f"Set default language: en")
    session.modified = True

# Routes
@quiz_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    if not QUIZ_QUESTIONS:
        flash(trans('Quiz configuration error.', lang=session.get('language', 'en')), 'error')
        return redirect(url_for('index'))

    language = session.get('language', 'en')
    trans_dict = get_translations(language)
    course_id = request.args.get('course_id', 'financial_quiz')

    form = QuizForm(language=language, personal_info=True, formdata=request.form if request.method == 'POST' else None)
    form.submit.label.text = 'Start Quiz'

    if request.method == 'POST':
        if form.validate_on_submit():
            session['quiz_data'] = {
                'first_name': form.first_name.data,
                'email': form.email.data,
                'language': form.language.data,
                'send_email': form.send_email.data
            }
            session['language'] = form.language.data
            session.modified = True
            current_app.logger.info(f"Step 1 validated, session: {session['quiz_data']}")

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
            current_app.logger.info(f"Lesson 0 (step1) completed for course {course_id}")

            return redirect(url_for('quiz.step2a', course_id=course_id))
        else:
            current_app.logger.error(f"Validation failed: {form.errors}")
            flash(trans('Please correct the errors below', lang=language), 'error')

    return render_template(
        'quiz_step1.html',
        form=form,
        course_id=course_id,
        translations=trans_dict,
        base_url=current_app.config.get('BASE_URL', ''),
        FEEDBACK_FORM_URL=current_app.config.get('FEEDBACK_FORM_URL', ''),
        WAITLIST_FORM_URL=current_app.config.get('WAITLIST_FORM_URL', ''),
        CONSULTANCY_FORM_URL=current_app.config.get('CONSULTANCY_FORM_URL', ''),
        LINKEDIN_URL=current_app.config.get('LINKEDIN_URL', ''),
        TWITTER_URL=current_app.config.get('TWITTER_URL', ''),
        language=language
    )

@quiz_bp.route('/step2a', methods=['GET', 'POST'])
def step2a():
    if not QUIZ_QUESTIONS:
        flash(trans('Quiz configuration error.', lang=session.get('language', 'en')), 'error')
        return redirect(url_for('index'))

    if 'sid' not in session or 'quiz_data' not in session:
        current_app.logger.error(f"Session missing: sid={session.get('sid')}, quiz_data={session.get('quiz_data')}")
        flash(trans('Session Expired', lang=session.get('language', 'en')), 'error')
        return redirect(url_for('quiz.step1', course_id=request.args.get('course_id', 'financial_quiz')))

    language = session.get('language', 'en')
    trans_dict = get_translations(language)
    course_id = request.args.get('course_id', 'financial_quiz')

    preprocessed_questions = [
        {
            'id': q['id'],
            'key': q.get('key', ''),
            'label': f"quiz_{q.get('key', '')}_label",
            'text': q['text'],
            'type': q['type'],
            'options': q['options'],
            'required': q.get('required', True),
            'positive_answers': q.get('positive_answers', ['Yes']),
            'negative_answers': q.get('negative_answers', ['No']),
            'weight': q.get('weight', 1),
            'tooltip': f"quiz_{q.get('key', '')}_tooltip",
            'placeholder': f"quiz_{q.get('key', '')}_placeholder"
        }
        for q in QUIZ_QUESTIONS[:5]
    ]

    form = QuizForm(questions=preprocessed_questions, language=language, personal_info=False, formdata=request.form if request.method == 'POST' else None)
    form.submit.label.text = 'Continue'
    form.back.label.text = 'Back'

    if request.method == 'POST':
        if form.validate_on_submit():
            session['quiz_data'].update({
                q['id']: form[q['id']].data for q in preprocessed_questions if q['id'] in form._fields
            })
            session['language'] = form.language.data
            session.modified = True
            current_app.logger.info(f"Step 2a validated, session: {session['quiz_data']}")

            progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
            progress = progress_storage.filter_by_session(session['sid'])
            course_progress = next((p for p in progress if p['data'].get('course_id') == course_id), None)
            if course_progress and 1 not in course_progress['data'].get('completed_lessons', []):
                course_progress['data']['completed_lessons'].append(1)
                course_progress['data']['progress_percentage'] = (len(course_progress['data']['completed_lessons']) / 3) * 100
                course_progress['data']['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                progress_storage.update_by_id(course_progress['id'], course_progress['data'])
            current_app.logger.info(f"Lesson 1 (step2a) completed for course {course_id}")

            return redirect(url_for('quiz.step2b', course_id=course_id))
        else:
            current_app.logger.error(f"Validation failed: {form.errors}")
            flash(trans('Please correct the errors below', lang=language), 'error')

    if 'quiz_data' in session:
        for q in preprocessed_questions:
            if q['id'] in session['quiz_data']:
                form[q['id']].data = session['quiz_data'][q['id']]

    response = make_response(render_template(
        'quiz_step2a.html',
        form=form,
        questions=preprocessed_questions,
        course_id=course_id,
        translations=trans_dict,
        base_url=current_app.config.get('BASE_URL', ''),
        FEEDBACK_FORM_URL=current_app.config.get('FEEDBACK_FORM_URL', ''),
        WAITLIST_FORM_URL=current_app.config.get('WAITLIST_FORM_URL', ''),
        CONSULTANCY_FORM_URL=current_app.config.get('CONSULTANCY_FORM_URL', ''),
        LINKEDIN_URL=current_app.config.get('LINKEDIN_URL', ''),
        TWITTER_URL=current_app.config.get('TWITTER_URL', ''),
        language=language
    ))
    return response

@quiz_bp.route('/step2b', methods=['GET', 'POST'])
def step2b():
    if not QUIZ_QUESTIONS:
        flash(trans('Quiz configuration error.', lang=session.get('language', 'en')), 'error')
        return redirect(url_for('index'))

    if 'sid' not in session or 'quiz_data' not in session:
        flash(trans('Session Expired', lang=session.get('language', 'en')), 'error')
        return redirect(url_for('quiz.step1', course_id=request.args.get('course_id', 'financial_quiz')))

    language = session.get('language', 'en')
    trans_dict = get_translations(language)
    course_id = request.args.get('course_id', 'financial_quiz')

    preprocessed_questions = [
        {
            'id': q['id'],
            'key': q.get('key', ''),
            'label': f"quiz_{q.get('key', '')}_label",
            'text': q['text'],
            'type': q['type'],
            'options': q['options'],
            'required': q.get('required', True),
            'positive_answers': q.get('positive_answers', ['Yes']),
            'negative_answers': q.get('negative_answers', ['No']),
            'weight': q.get('weight', 1),
            'tooltip': f"quiz_{q.get('key', '')}_tooltip",
            'placeholder': f"quiz_{q.get('key', '')}_placeholder"
        }
        for q in QUIZ_QUESTIONS[5:10]
    ]

    form = QuizForm(questions=preprocessed_questions, language=language, personal_info=False, formdata=request.form if request.method == 'POST' else None)
    form.submit.label.text = 'See Results'
    form.back.label.text = 'Back'

    if request.method == 'POST':
        if form.validate_on_submit():
            session['quiz_data'].update({
                q['id']: form[q['id']].data for q in preprocessed_questions if q['id'] in form._fields
            })
            session['language'] = form.language.data
            session.modified = True
            current_app.logger.info(f"Step 2b validated, session: {session['quiz_data']}")

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
                **{f'question_{i}': QUIZ_QUESTIONS[i-1]['text'] for i in range(1, 11)},
                **{f'answer_{i}': session['quiz_data'].get(f'question_{i}', '') for i in range(1, 11)}
            }])

            storage_managers = current_app.config['STORAGE_MANAGERS']
            all_users_df = storage_managers['sheets'].fetch_data_from_sheet(
                headers=storage_managers['PREDETERMINED_HEADERS_QUIZ'],
                worksheet_name='Quiz'
            )

            badges = assign_badges_quiz(user_df, all_users_df, language)
            data = [
                datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
                session['quiz_data'].get('first_name', ''),
                session['quiz_data'].get('email', ''),
                session['quiz_data'].get('language', 'en'),
                *[QUIZ_QUESTIONS[i-1]['text'] for i in range(1, 11)],
                *[session['quiz_data'].get(f'question_{i}', '') for i in range(1, 11)],
                personality,
                str(score),
                ','.join(badges),
                str(session['quiz_data'].get('send_email', False)).lower()
            ]

            if not storage_managers['sheets'].append_to_sheet(data, storage_managers['PREDETERMINED_HEADERS_QUIZ'], 'Quiz'):
                flash(trans('Google Sheets Error', lang=language), 'error')
                return redirect(url_for('quiz.step2b', course_id=course_id))

            progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
            progress = progress_storage.filter_by_session(session['sid'])
            course_progress = next((p for p in progress if p['data'].get('course_id') == course_id), None)
            if course_progress and 2 not in course_progress['data'].get('completed_lessons', []):
                course_progress['data']['completed_lessons'].append(2)
                course_progress['data']['progress_percentage'] = (len(course_progress['data']['completed_lessons']) / 3) * 100
                progress_storage.update_by_id(course_progress['id'], course_progress['data'])
            current_app.logger.info(f"Lesson 2 (step2b) completed for course {course_id}")

            records = []
            if not all_users_df.empty:
                user_records = all_users_df[all_users_df['email'] == session['quiz_data'].get('email', '')].sort_values('Timestamp')
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
                threading.Thread(
                    target=send_quiz_email_async,
                    args=(current_app._get_current_object(), session['quiz_data']['email'], session['quiz_data']['first_name'], personality, personality_desc, tip, language)
                ).start()
                flash(trans('Check Inbox', lang=language), 'success')

            flash(trans('Submission Success', lang=language))
            return redirect(url_for('quiz.results', course_id=course_id))
        else:
            current_app.logger.error(f"Validation failed: {form.errors}")
            flash(trans('Please correct the errors below', lang=language), 'error')

    if 'quiz_data' in session:
        for q in preprocessed_questions:
            if q['id'] in session['quiz_data']:
                form[q['id']].data = session['quiz_data'][q['id']]

    response = make_response(render_template(
        'quiz_step2b.html',
        form=form,
        questions=preprocessed_questions,
        course_id=course_id,
        translations=trans_dict,
        base_url=current_app.config.get('BASE_URL', ''),
        FEEDBACK_FORM_URL=current_app.config.get('FEEDBACK_FORM_URL', ''),
        WAITLIST_FORM_URL=current_app.config.get('WAITLIST_FORM_URL', ''),
        CONSULTANCY_FORM_URL=current_app.config.get('CONSULTANCY_FORM_URL', ''),
        LINKEDIN_URL=current_app.config.get('LINKEDIN_URL', ''),
        TWITTER_URL=current_app.config.get('TWITTER_URL', ''),
        language=language
    ))
    return response

@quiz_bp.route('/results', methods=['GET'])
def results():
    language = session.get('language', 'en')
    trans_dict = get_translations(language)
    course_id = request.args.get('course_id', 'financial_quiz')
    results = session.get('quiz_results', {})

    if not results:
        flash(trans('Session Expired', lang=language), 'error')
        return redirect(url_for('quiz.step1', course_id=course_id))

    session.pop('quiz_data', None)
    session.pop('quiz_results', None)
    session['language'] = language
    session.modified = True

    response = make_response(render_template(
        'quiz_results.html',
        latest_record=results.get('latest_record', {}),
        records=results.get('records', []),
        insights=results.get('insights', []),
        tips=results.get('tips', []),
        course_id=course_id,
        translations=trans_dict,
        base_url=current_app.config.get('BASE_URL', ''),
        FEEDBACK_FORM_URL=current_app.config.get('FEEDBACK_FORM_URL', ''),
        WAITLIST_FORM_URL=current_app.config.get('WAITLIST_FORM_URL', ''),
        CONSULTANCY_FORM_URL=current_app.config.get('CONSULTANCY_FORM_URL', ''),
        LINKEDIN_URL=current_app.config.get('LINKEDIN_URL', ''),
        TWITTER_URL=current_app.config.get('TWITTER_URL', ''),
        language=language
    ))
    return response
