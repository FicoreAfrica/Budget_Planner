from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, make_response
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, BooleanField, SubmitField, RadioField
from wtforms.validators import DataRequired, Email, Optional
import json
import uuid
from datetime import datetime
import pandas as pd
import threading
from translations import trans, get_translations
from flask_mail import Message

# Define the quiz blueprint
quiz_bp = Blueprint('quiz', __name__, template_folder='templates', static_folder='static', url_prefix='/quiz')

# Global QUIZ_QUESTIONS will be initialized later
QUIZ_QUESTIONS = []
QUESTION_KEYS = [
    'track_expenses', 'save_regularly', 'spend_non_essentials', 'plan_spending', 'impulse_purchases',
    'use_budget', 'invest_money', 'emergency_fund', 'set_financial_goals', 'seek_financial_advice'
]

def init_quiz_questions(app):
    """Initialize QUIZ_QUESTIONS within app context."""
    global QUIZ_QUESTIONS
    with app.app_context():
        try:
            with open('questions.json', 'r', encoding='utf-8') as f:
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
            app.logger.error("questions.json file not found.")
            QUIZ_QUESTIONS = []
        except json.JSONDecodeError as e:
            app.logger.error(f"Error decoding questions.json: {e}")
            QUIZ_QUESTIONS = []

# Define the QuizForm
class QuizForm(FlaskForm):
    first_name = StringField(
        'First Name',
        validators=[DataRequired()],
        render_kw={
            'placeholder': 'e.g., Muhammad, Bashir, Umar',
            'title': 'Enter your first name',
            'aria-label': 'First Name'
        }
    )
    email = StringField(
        'Email',
        validators=[DataRequired(), Email()],
        render_kw={
            'placeholder': 'e.g., email@example.com',
            'title': 'Enter your email',
            'aria-label': 'Email'
        }
    )
    language = SelectField(
        'Language',
        choices=[('en', 'English'), ('ha', 'Hausa')],
        default='en',
        render_kw={'aria-label': 'Select Language'}
    )
    send_email = BooleanField(
        'Send Email',
        default=False,
        render_kw={'title': 'Receive email results', 'aria-label': 'Send Email Checkbox'}
    )
    submit = SubmitField('Next', render_kw={'aria-label': 'Submit Form'})
    back = SubmitField('Back', render_kw={'aria-label': 'Go Back'})

    def __init__(self, questions=None, language='en', formdata=None, personal_info=True, **kwargs):
        super().__init__(formdata=formdata, **kwargs)
        self.questions = questions or []
        self.language = language
        with current_app.app_context():
            current_app.logger.debug(f"Initializing QuizForm: questions={[q['id'] for q in self.questions]}, language={language}")

        # Initialize static fields
        if personal_info:
            self.first_name.label.text = trans('core_first_name', lang=language)
            self.email.label.text = trans('core_email', lang=language)
            self.language.label.text = trans('core_language', lang=language)
            self.send_email.label.text = trans('core_send_email', lang=language)
            self.submit.label.text = trans('core_submit', lang=language)
            self.back.label.text = trans('core_back', lang=language)

            self.first_name.render_kw['placeholder'] = trans('core_first_name_placeholder', lang=language)
            self.first_name.render_kw['title'] = trans('core_first_name_tooltip', lang=language)
            self.email.render_kw['placeholder'] = trans('core_email_placeholder', lang=language)
            self.email.render_kw['title'] = trans('core_email_tooltip', lang=language)
            self.send_email.render_kw['title'] = trans('core_send_email_tooltip', lang=language)
        else:
            # Reinitialize language and send_email to ensure they are WTForms fields
            if 'language' not in self._fields:
                self.language = SelectField(
                    trans('core_language', lang=language),
                    choices=[('en', 'English'), ('ha', 'Hausa')],
                    default=language,
                    render_kw={'aria-label': 'Select Language'}
                )
                self.language.bind(self, 'language')
                self._fields['language'] = self.language
            if 'send_email' not in self._fields:
                self.send_email = BooleanField(
                    trans('core_send_email', lang=language),
                    default=False,
                    render_kw={'title': trans('core_send_email_tooltip', lang=language), 'aria-label': 'Send Email Checkbox'}
                )
                self.send_email.bind(self, 'send_email')
                self._fields['send_email'] = self.send_email
            self.language.process(formdata, self.data.get('language', language))
            self.send_email.process(formdata, self.data.get('send_email', False))

        # Add dynamic question fields
        if not personal_info:
            for q in self.questions:
                field_name = q['id']
                if field_name in self._fields:
                    continue  # Prevent overwriting existing fields
                question_key = q.get('key', '')
                label_key = f"quiz_{question_key}_label"
                tooltip_key = f"quiz_{question_key}_tooltip"
                placeholder_key = f"quiz_{question_key}_placeholder"
                label = trans(label_key, lang=language)
                tooltip = trans(tooltip_key, lang=language)
                placeholder = trans(placeholder_key, lang=language)
                choices = [(trans(opt, lang=language), trans(opt, lang=language)) for opt in q['options']]
                field = RadioField(
                    label,
                    validators=[DataRequired() if q.get('required', True) else Optional()],
                    choices=choices,
                    id=field_name,
                    default=trans(q['options'][0], lang=language) if q['options'] else None,
                    render_kw={
                        'title': tooltip,
                        'placeholder': placeholder,
                        'aria-label': f"{label} question"
                    }
                )
                bound_field = field.bind(self, field_name)
                bound_field.process(formdata, self.data.get(field_name, trans(q['options'][0], lang=language)) if formdata and q['options'] else None)
                self._fields[field_name] = bound_field
                with current_app.app_context():
                    current_app.logger.debug(f"Added field {field_name} with label '{label}' (key: {label_key})")

        with current_app.app_context():
            current_app.logger.debug(f"Form fields initialized: {list(self._fields.keys())}")

    def validate(self, extra_validators=None):
        with current_app.app_context():
            current_app.logger.debug(f"Validating QuizForm: fields={list(self._fields.keys())}")
        rv = super().validate(extra_validators)
        if not rv:
            with current_app.app_context():
                current_app.logger.error(f"Validation errors: {self.errors}")
        return rv

# Helper Functions
def calculate_score(answers, language='en'):
    score = 0
    for q, a in answers:
        positive = [trans(opt, lang=language) for opt in q.get('positive_answers', ['Yes'])]
        negative = [trans(opt, lang=language) for opt in q.get('negative_answers', ['No'])]
        if a in positive:
            score += 3
        elif a in negative:
            score -= 1
    return max(0, score)

def assign_personality(answers, language='en'):
    trans_dict = get_translations(language)
    score = 0
    for q, a in answers:
        weight = q.get('weight', 1)
        positive = [trans(opt, lang=language) for opt in q.get('positive_answers', ['Yes'])]
        negative = [trans(opt, lang=language) for opt in q.get('negative_answers', ['No'])]
        if a in positive:
            score += weight
        elif a in negative:
            score -= weight
    if score >= 6:
        return 'Planner', trans_dict.get('quiz_planner_description', 'You plan well.'), trans_dict.get('quiz_planner_tip', 'Save regularly.')
    elif score >= 2:
        return 'Saver', trans_dict.get('quiz_saver_description', 'You save consistently.'), trans_dict.get('quiz_saver_tip', 'Increase savings.')
    elif score >= 0:
        return 'Balanced', trans_dict.get('quiz_balanced_description', 'Balanced approach.'), trans_dict.get('quiz_balanced_tip', 'Use a budget.')
    elif score >= -2:
        return 'Spender', trans_dict.get('quiz_spender_description', 'You enjoy spending.'), trans_dict.get('quiz_spender_tip', 'Track expenses.')
    else:
        return 'Avoider', trans_dict.get('quiz_avoider_description', 'You avoid planning.'), trans_dict.get('quiz_avoider_tip', 'Start simple.')

def assign_badges_quiz(user_df, all_users_df, language='en'):
    badges = []
    with open('badges.json', 'r', encoding='utf-8') as f:
        badge_configs = json.load(f)
    
    if user_df.empty:
        current_app.logger.warning("Empty user_df in assign_badges_quiz.")
        return badges

    user_row = user_df.iloc[0]
    for badge in badge_configs:
        criteria = badge['criteria']
        if (criteria.get('personality') == user_row['personality'] and
                user_row['score'] >= criteria.get('min_score', 0)):
            badges.append(trans(badge['translation_key'], lang=language))
        elif badge['name'] == 'First Quiz Completed!' and len(user_df) >= 1:
            badges.append(trans(badge['translation_key'], lang=language))
        elif badge['name'] == 'Needs Guidance!' and user_row['personality'] == 'Avoider' and len(all_users_df) > 10:
            badges.append(trans(badge['translation_key'], lang=language))
    
    return badges

def generate_quiz_summary_chart(answers, language='en'):
    labels = [trans(f"quiz_{q.get('key', '')}_label", lang=language) for q, _ in answers]
    scores = [3 if a in q.get('positive_answers', ['Yes']) else -1 if a in q.get('negative_answers', ['No']) else 0 for q, a in answers]
    return {
        "labels": labels,
        "datasets": [{
            "label": trans('quiz_your_answers', lang=language),
            "data": scores,
            "backgroundColor": "rgba(30, 127, 113, 0.2)",
            "borderColor": "#1E7F71",
            "pointBackgroundColor": "#1E7F71",
            "pointBorderColor": "#fff",
            "pointHoverBackgroundColor": "#fff",
            "pointHoverBorderColor": "#1E7F71"
        }]
    }

def generate_insights_and_tips(personality, language='en'):
    trans_dict = get_translations(language)
    insights = []
    tips = []
    if personality == 'Planner':
        insights.append(trans_dict.get('quiz_planner_insight', 'Strong financial planning.'))
        tips.append(trans_dict.get('quiz_planner_tip', 'Set long-term goals.'))
    elif personality == 'Saver':
        insights.append(trans_dict.get('quiz_saver_insight', 'Excellent at saving.'))
        tips.append(trans_dict.get('quiz_saver_tip', 'Consider investing.'))
    elif personality == 'Balanced':
        insights.append(trans_dict.get('quiz_balanced_insight', 'Balanced saving/spending.'))
        tips.append(trans_dict.get('quiz_balanced_tip', 'Optimize with a budgeting app.'))
    elif personality == 'Spender':
        insights.append(trans_dict.get('quiz_spender_insight', 'Enjoy spending.'))
        tips.append(trans_dict.get('quiz_spender_tip', 'Track expenses.'))
    elif personality == 'Avoider':
        insights.append(trans_dict.get('quiz_avoider_insight', 'Planning is challenging.'))
        tips.append(trans_dict.get('quiz_avoider_tip', 'Start with a budget.'))
    return insights, tips

def append_to_google_sheet(data, headers, worksheet_name='Quiz'):
    try:
        storage_managers = current_app.config['STORAGE_MANAGERS']
        if storage_managers['sheets'].append_to_sheet(data, headers, worksheet_name):
            return True
        else:
            flash(trans('google_sheets_error', lang=session.get('language', 'en')), 'error')
            return False
    except Exception as e:
        current_app.logger.error(f"Google Sheets append error: {e}")
        flash(trans('google_sheets_error', lang=session.get('language', 'en')), 'error')
        return False

def send_quiz_email(to_email, user_name, personality, personality_desc, tip, language, chart_data=None):
    try:
        msg = Message(
            subject=trans('quiz_report_subject', lang=language),
            recipients=[to_email],
            html=render_template(
                'quiz_email.html',
                trans=lambda key: trans(key, lang=language),
                user_name=user_name or 'User',
                personality=personality,
                personality_desc=personality_desc,
                tip=tip,
                data={'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'), 'score': calculate_score([(QUIZ_QUESTIONS[int(k.split('_')[1]) - 1], v) for k, v in session.get('quiz_data', {}).items() if k.startswith('question_')], language), 'badges': session.get('quiz_results', {}).get('latest_record', {}).get('badges', [])},
                base_url=current_app.config.get('BASE_URL', ''),
                language=language
            )
        )
        current_app.extensions['mail'].send(msg)
        current_app.logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        current_app.logger.error(f"Email error to {to_email}: {e}")
        return False

def send_quiz_email_async(app, to_email, user_name, personality, personality_desc, tip, language, chart_data):
    with app.app_context():
        send_quiz_email(to_email, user_name, personality, personality_desc, tip, language, chart_data)

def partition_questions(questions, per_step=5):
    return [questions[i:i + per_step] for i in range(0, len(questions), per_step)]

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
        flash(trans('quiz_config_error', lang=session.get('language', 'en')), 'error')
        return redirect(url_for('index'))

    language = session.get('language', 'en')
    trans_dict = get_translations(language)
    course_id = request.args.get('course_id', 'financial_quiz')

    form = QuizForm(language=language, personal_info=True, formdata=request.form if request.method == 'POST' else None)
    form.submit.label.text = trans('core_start_quiz', lang=language)

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
                    'progress_percentage': (1 / (len(partition_questions(QUIZ_QUESTIONS)) + 1)) * 100,
                    'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                progress_storage.append(progress_data, session_id=session['sid'])
            else:
                if 0 not in course_progress['data'].get('completed_lessons', []):
                    course_progress['data']['completed_lessons'].append(0)
                    course_progress['data']['progress_percentage'] = (len(course_progress['data']['completed_lessons']) / (len(partition_questions(QUIZ_QUESTIONS)) + 1)) * 100
                    course_progress['data']['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    progress_storage.update_by_id(course_progress['id'], course_progress['data'])
            current_app.logger.info(f"Lesson 0 (step1) completed for course {course_id}")

            return redirect(url_for('quiz.quiz_step', step_num=1, course_id=course_id))
        else:
            current_app.logger.error(f"Validation failed: {form.errors}")
            flash(trans('form_errors', lang=language), 'error')

    return render_template(
        'quiz_step1.html',
        form=form,
        course_id=course_id,
        translations=trans_dict,
        base_url=current_app.config.get('BASE_URL', ''),
        language=language
    )

@quiz_bp.route('/step/<int:step_num>', methods=['GET', 'POST'])
def quiz_step(step_num):
    if not QUIZ_QUESTIONS:
        flash(trans('quiz_config_error', lang=session.get('language', 'en')), 'error')
        return redirect(url_for('index'))

    if 'sid' not in session or 'quiz_data' not in session:
        flash(trans('session_expired', lang=session.get('language', 'en')), 'error')
        return redirect(url_for('quiz.step1', course_id=request.args.get('course_id', 'financial_quiz')))

    language = session.get('language', 'en')
    steps = partition_questions(QUIZ_QUESTIONS, per_step=5)
    if step_num < 1 or step_num > len(steps):
        flash(trans('invalid_step', lang=language), 'error')
        return redirect(url_for('quiz.step1', course_id=request.args.get('course_id', 'financial_quiz')))

    questions = steps[step_num - 1]
    preprocessed_questions = [
        {
            'id': q['id'],
            'key': q.get('key', ''),
            'label': trans(f"quiz_{q.get('key', '')}_label", lang=language),
            'text': trans(q['text_key'], lang=language),
            'type': q['type'],
            'options': [trans(opt, lang=language) for opt in q['options']],
            'required': q.get('required', True),
            'positive_answers': [trans(opt, lang=language) for opt in q.get('positive_answers', ['Yes'])],
            'negative_answers': [trans(opt, lang=language) for opt in q.get('negative_answers', ['No'])],
            'weight': q.get('weight', 1),
            'tooltip': trans(f"quiz_{q.get('key', '')}_tooltip", lang=language),
            'placeholder': trans(f"quiz_{q.get('key', '')}_placeholder", lang=language)
        } for q in questions
    ]

    current_app.logger.debug(f"Session quiz_data: {session.get('quiz_data', {})}")
    form = QuizForm(questions=preprocessed_questions, language=language, personal_info=False, formdata=request.form if request.method == 'POST' else None)
    form.submit.label.text = trans('core_see_results' if step_num == len(steps) else 'core_continue', lang=language)
    form.back.label.text = trans('core_back', lang=language)

    if request.method == 'POST' and form.validate_on_submit():
        session['quiz_data'].update({q['id']: form[q['id']].data for q in preprocessed_questions})
        session['language'] = form.language.data
        session['quiz_data']['send_email'] = form.send_email.data
        session.modified = True

        course_id = request.args.get('course_id', 'financial_quiz')
        progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
        progress = progress_storage.filter_by_session(session['sid'])
        course_progress = next((p for p in progress if p['data'].get('course_id') == course_id), None)
        if course_progress and step_num not in course_progress['data'].get('completed_lessons', []):
            course_progress['data']['completed_lessons'].append(step_num)
            course_progress['data']['progress_percentage'] = (len(course_progress['data']['completed_lessons']) / (len(steps) + 1)) * 100
            progress_storage.update_by_id(course_progress['id'], course_progress['data'])

        if step_num < len(steps):
            return redirect(url_for('quiz.quiz_step', step_num=step_num + 1, course_id=course_id))
        
        answers = [(QUIZ_QUESTIONS[int(k.split('_')[1]) - 1], v) for k, v in session['quiz_data'].items() if k.startswith('question_')]
        personality, personality_desc, tip = assign_personality(answers, language)
        score = calculate_score(answers, language)
        chart_data = generate_quiz_summary_chart(answers, language)
        user_df = pd.DataFrame([{
            'Timestamp': datetime.utcnow(),
            'first_name': session['quiz_data'].get('first_name', ''),
            'email': session['quiz_data'].get('email', ''),
            'language': session['quiz_data'].get('language', 'en'),
            'personality': personality,
            'score': score,
            **{f'question_{i}': trans(QUIZ_QUESTIONS[i-1]['text_key'], lang=language) for i in range(1, 11)},
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
            *[trans(QUIZ_QUESTIONS[i-1]['text_key'], lang=language) for i in range(1, 11)],
            *[session['quiz_data'].get(f'question_{i}', '') for i in range(1, 11)],
            personality,
            str(score),
            ','.join(badges),
            str(session['quiz_data'].get('send_email', False)).lower()
        ]

        if not append_to_google_sheet(data, storage_managers['PREDETERMINED_HEADERS_QUIZ'], 'Quiz'):
            flash(trans('google_sheets_error', lang=language), 'error')
            return redirect(url_for('quiz.quiz_step', step_num=step_num, course_id=course_id))

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
            'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
            'chart_data': chart_data
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
                args=(current_app._get_current_object(), session['quiz_data']['email'], session['quiz_data']['first_name'], 
                      personality, personality_desc, tip, language, chart_data)
            ).start()
            flash(trans('check_inbox', lang=language), 'success')

        flash(trans('submission_success', lang=language))
        return redirect(url_for('quiz.results', course_id=course_id))

    if 'quiz_data' in session:
        current_app.logger.debug(f"Prepopulating form with session quiz_data: {session['quiz_data']}")
        for q in preprocessed_questions:
            if q['id'] in session['quiz_data']:
                try:
                    if isinstance(session['quiz_data'][q['id']], str):
                        form[q['id']].data = session['quiz_data'][q['id']]
                    else:
                        current_app.logger.warning(f"Invalid data type for {q['id']} in session: {type(session['quiz_data'][q['id']])}")
                except AttributeError:
                    current_app.logger.warning(f"Field {q['id']} not found in form for pre-population")
        try:
            if 'language' in session['quiz_data']:
                form.language.data = session['quiz_data']['language'] if session['quiz_data']['language'] in ['en', 'ha'] else 'en'
            if 'send_email' in session['quiz_data']:
                form.send_email.data = bool(session['quiz_data']['send_email'])
        except AttributeError as e:
            current_app.logger.error(f"Error prepopulating language/send_email: {e}")

    response = make_response(render_template(
        'quiz_step.html',
        form=form,
        questions=preprocessed_questions,
        step_num=step_num,
        total_steps=len(steps),
        course_id=course_id,
        translations=get_translations(language),
        base_url=current_app.config.get('BASE_URL', ''),
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
        flash(trans('session_expired', lang=language), 'error')
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
        chart_data=results.get('latest_record', {}).get('chart_data', {}),
        course_id=course_id,
        translations=trans_dict,
        base_url=current_app.config.get('BASE_URL', ''),
        language=language
    ))
    return response
