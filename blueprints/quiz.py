```python
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, make_response
from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField, RadioField
from wtforms.validators import DataRequired, Email, Optional
import json
import uuid
from datetime import datetime
import pandas as pd
import threading
from flask_mail import Message

# Define the quiz blueprint
quiz_bp = Blueprint('quiz', __name__, template_folder='templates', static_folder='static', url_prefix='/quiz')

# Hardcoded questions (10 questions, localized for Nigerian users)
QUESTIONS = [
    {
        "id": "question_1",
        "key": "track_expenses",
        "question": "How often do you track your spending?",
        "choices": [("many_times", "Many Times"), ("once_in_a_while", "Once in a while"), ("never", "Never")],
        "positive_answers": ["many_times"],
        "negative_answers": ["never"],
        "weight": 1
    },
    {
        "id": "question_2",
        "key": "save_regularly",
        "question": "Do you save money regularly?",
        "choices": [("many_times", "Many Times"), ("once_in_a_while", "Once in a while"), ("never", "Never")],
        "positive_answers": ["many_times"],
        "negative_answers": ["never"],
        "weight": 1
    },
    {
        "id": "question_3",
        "key": "spend_non_essentials",
        "question": "Do you spend money on things you don’t really need?",
        "choices": [("many_times", "Many Times"), ("once_in_a_while", "Once in a while"), ("never", "Never")],
        "positive_answers": ["never"],
        "negative_answers": ["many_times"],
        "weight": 1
    },
    {
        "id": "question_4",
        "key": "plan_spending",
        "question": "Do you plan how you will spend your money?",
        "choices": [("many_times", "Many Times"), ("once_in_a_while", "Once in a while"), ("never", "Never")],
        "positive_answers": ["many_times"],
        "negative_answers": ["never"],
        "weight": 1
    },
    {
        "id": "question_5",
        "key": "impulse_purchases",
        "question": "Do you buy things without thinking much about it?",
        "choices": [("many_times", "Many Times"), ("once_in_a_while", "Once in a while"), ("never", "Never")],
        "positive_answers": ["never"],
        "negative_answers": ["many_times"],
        "weight": 1
    },
    {
        "id": "question_6",
        "key": "use_budget",
        "question": "Do you use a budget to manage your money?",
        "choices": [("many_times", "Many Times"), ("once_in_a_while", "Once in a while"), ("never", "Never")],
        "positive_answers": ["many_times"],
        "negative_answers": ["never"],
        "weight": 1
    },
    {
        "id": "question_7",
        "key": "invest_money",
        "question": "Do you invest your money to grow it?",
        "choices": [("many_times", "Many Times"), ("once_in_a_while", "Once in a while"), ("never", "Never")],
        "positive_answers": ["many_times"],
        "negative_answers": ["never"],
        "weight": 1
    },
    {
        "id": "question_8",
        "key": "emergency_fund",
        "question": "Do you have an emergency fund for unexpected expenses?",
        "choices": [("yes", "Yes"), ("no", "No")],
        "positive_answers": ["yes"],
        "negative_answers": ["no"],
        "weight": 1
    },
    {
        "id": "question_9",
        "key": "set_financial_goals",
        "question": "Do you set financial goals for yourself?",
        "choices": [("many_times", "Many Times"), ("once_in_a_while", "Once in a while"), ("never", "Never")],
        "positive_answers": ["many_times"],
        "negative_answers": ["never"],
        "weight": 1
    },
    {
        "id": "question_10",
        "key": "seek_financial_advice",
        "question": "Do you seek advice from financial experts?",
        "choices": [("many_times", "Many Times"), ("once_in_a_while", "Once in a while"), ("never", "Never")],
        "positive_answers": ["many_times"],
        "negative_answers": ["never"],
        "weight": 1
    }
]

# Hardcoded translations (minimal set for quiz functionality)
TRANSLATIONS = {
    'en': {
        'core_first_name': 'First Name',
        'core_email': 'Email',
        'core_send_email': 'Send Email',
        'core_send_email_tooltip': 'Check to receive your quiz results via email',
        'core_start_quiz': 'Start Quiz',
        'core_continue': 'Continue',
        'core_see_results': 'See Results',
        'core_back': 'Back',
        'core_submit': 'Submit',
        'core_first_name_placeholder': 'e.g., Muhammad, Bashir, Umar',
        'core_email_placeholder': 'e.g., muhammad@example.com',
        'core_first_name_tooltip': 'Enter your first name',
        'core_email_tooltip': 'Enter your email to receive quiz results',
        'quiz_financial_personality_quiz': 'Financial Personality Quiz',
        'quiz_enter_personal_information': 'Enter your personal information',
        'quiz_step_progress': 'Step {step} of {total}',
        'quiz_config_error': 'Quiz configuration error. Please try again later.',
        'session_expired': 'Your session has expired. Please start again.',
        'invalid_step': 'Invalid quiz step. Please start again.',
        'form_errors': 'Please correct the errors in the form.',
        'submission_success': 'Quiz submitted successfully!',
        'check_inbox': 'Check your inbox for quiz results.',
        'google_sheets_error': 'Error saving quiz results. Please try again.',
        'quiz_your_answers': 'Your Answers',
        'quiz_financial_behavior': 'Financial Behavior Breakdown',
        'quiz_financial_personality_dashboard': 'Financial Personality Dashboard',
        'quiz_your_financial_personality_results': 'Your financial personality results',
        'core_hello': 'Hello',
        'core_user': 'User',
        'quiz_your_personality': 'Your Personality',
        'quiz_score': 'Score',
        'core_created_at': 'Created At',
        'quiz_planner_description': 'You are disciplined and plan your finances carefully, using tools like PiggyVest and setting clear goals.',
        'quiz_saver_description': 'You prioritize saving, often using Ajo/Esusu/Adashe, and are cautious with spending.',
        'quiz_balanced_description': 'You balance spending and saving, occasionally planning but open to impulse purchases.',
        'quiz_spender_description': 'You enjoy spending and may need to focus on budgeting and saving with apps like Moniepoint.',
        'quiz_avoider_description': 'You avoid financial planning and may benefit from starting with a simple budget.',
        'quiz_planner_tip': 'Set long-term financial goals.',
        'quiz_saver_tip': 'Consider investing to grow your savings.',
        'quiz_balanced_tip': 'Optimize with a budgeting app.',
        'quiz_spender_tip': 'Track your expenses daily.',
        'quiz_avoider_tip': 'Start with a simple budget.',
        'quiz_quiz_metrics': 'Quiz Metrics',
        'quiz_badges': 'Badges',
        'quiz_no_badges_earned_yet': 'No badges earned yet',
        'quiz_insights': 'Insights',
        'quiz_no_insights_available': 'No insights available',
        'quiz_tips_for_improving_financial_habits': 'Tips for Improving Financial Habits',
        'quiz_call_to_actions': 'Call to Actions',
        'quiz_retake_quiz': 'Retake Quiz',
        'quiz_create_budget': 'Create Budget',
        'quiz_calculate_net_worth': 'Calculate Net Worth',
        'quiz_no_previous_quizzes': 'No previous quizzes',
        'core_date': 'Date',
        'quiz_personality': 'Personality',
        'courses_back_to_courses': 'Back to Courses',
        'courses_complete_course': 'Complete Course',
        'quiz_no_quiz_data_available': 'No quiz data available'
    }
}

# Mock translation function (since translations.py is updated)
def trans(key, lang='en', **kwargs):
    translation = TRANSLATIONS.get(lang, {}).get(key, key)
    if translation == key:
        current_app.logger.warning(f"Missing translation for key={key} in lang={lang}, session: {session.get('sid', 'unknown')}")
    return translation.format(**kwargs) if kwargs else translation

def get_translations(lang='en'):
    return TRANSLATIONS.get(lang, {})

# Define the QuizForm
class QuizForm(FlaskForm):
    first_name = StringField(
        'First Name',
        validators=[DataRequired()],
        render_kw={'placeholder': 'e.g., Muhammad, Bashir, Umar', 'title': 'Enter your first name', 'aria-label': 'First Name'}
    )
    email = StringField(
        validators=[DataRequired(), Email()],
        render_kw={'placeholder': 'e.g., muhammad@example.com', 'title': 'Enter your email', 'aria-label': 'Email'}
    )
    send_email = BooleanField(
        default=False,
        render_kw={'title': 'Receive email results', 'aria-label': 'Send Email Checkbox'}
    )
    submit = SubmitField('Next', render_kw={'aria-label': 'Submit Form'})
    back = SubmitField('Back', render_kw={'aria-label': 'Go Back'})
    
    # Hardcoded question fields for steps 2+
    question_1 = RadioField(
        'How often do you track your spending?',
        choices=[('many_times', 'Many Times'), ('once_in_a_while', 'Once in a while'), ('never', 'Never')],
        validators=[DataRequired()],
        render_kw={'aria-label': 'Track spending question'}
    )
    question_2 = RadioField(
        'Do you save money regularly?',
        choices=[('many_times', 'Many Times'), ('once_in_a_while', 'Once in a while'), ('never', 'Never')],
        validators=[DataRequired()],
        render_kw={'aria-label': 'Save regularly question'}
    )
    question_3 = RadioField(
        'Do you spend money on things you don’t really need?',
        choices=[('many_times', 'Many Times'), ('once_in_a_while', 'Once in a while'), ('never', 'Never')],
        validators=[DataRequired()],
        render_kw={'aria-label': 'Spend non-essentials question'}
    )
    question_4 = RadioField(
        'Do you plan how you will spend your money?',
        choices=[('many_times', 'Many Times'), ('once_in_a_while', 'Once in a while'), ('never', 'Never')],
        validators=[DataRequired()],
        render_kw={'aria-label': 'Plan spending question'}
    )
    question_5 = RadioField(
        'Do you buy things without thinking much about it?',
        choices=[('many_times', 'Many Times'), ('once_in_a_while', 'Once in a while'), ('never', 'Never')],
        validators=[DataRequired()],
        render_kw={'aria-label': 'Impulse purchases question'}
    )
    question_6 = RadioField(
        'Do you use a budget to manage your money?',
        choices=[('many_times', 'Many Times'), ('once_in_a_while', 'Once in a while'), ('never', 'Never')],
        validators=[DataRequired()],
        render_kw={'aria-label': 'Use budget question'}
    )
    question_7 = RadioField(
        'Do you invest your money to grow it?',
        choices=[('many_times', 'Many Times'), ('once_in_a_while', 'Once in a while'), ('never', 'Never')],
        validators=[DataRequired()],
        render_kw={'aria-label': 'Invest money question'}
    )
    question_8 = RadioField(
        'Do you have an emergency fund for unexpected expenses?',
        choices=[('yes', 'Yes'), ('no', 'No')],
        validators=[DataRequired()],
        render_kw={'aria-label': 'Emergency fund question'}
    )
    question_9 = RadioField(
        'Do you set financial goals for yourself?',
        choices=[('many_times', 'Many Times'), ('once_in_a_while', 'Once in a while'), ('never', 'Never')],
        validators=[DataRequired()],
        render_kw={'aria-label': 'Set financial goals question'}
    )
    question_10 = RadioField(
        'Do you seek advice from financial experts?',
        choices=[('many_times', 'Many Times'), ('once_in_a_while', 'Once in a while'), ('never', 'Never')],
        validators=[DataRequired()],
        render_kw={'aria-label': 'Seek financial advice question'}
    )

    def __init__(self, personal_info=True, step_num=1, **kwargs):
        super().__init__(**kwargs)
        self.personal_info = personal_info
        self.step_num = step_num
        # Only include personal info fields in step 1
        if not personal_info:
            del self.first_name
            del self.email
            # Only include relevant question fields for the current step
            if step_num == 2:
                fields_to_keep = ['question_1', 'question_2', 'question_3', 'question_4', 'question_5']
            else:
                fields_to_keep = ['question_6', 'question_7', 'question_8', 'question_9', 'question_10']
            for field_name in list(self._fields.keys()):
                if field_name not in fields_to_keep + ['send_email', 'submit', 'back']:
                    del self._fields[field_name]
        current_app.logger.debug(f"Initialized QuizForm: personal_info={personal_info}, step_num={step_num}, fields={list(self._fields.keys())}")

    def validate(self, extra_validators=None):
        current_app.logger.debug(f"Validating QuizForm: fields={list(self._fields.keys())}")
        rv = super().validate(extra_validators)
        if not rv:
            current_app.logger.error(f"Validation errors: {self.errors}")
        return rv

# Helper Functions
def calculate_score(answers):
    score = 0
    for q, a in answers:
        if a in q.get('positive_answers', []):
            score += 3
        elif a in q.get('negative_answers', []):
            score -= 1
    return max(0, score)

def assign_personality(answers):
    score = 0
    for q, a in answers:
        weight = q.get('weight', 1)
        if a in q.get('positive_answers', []):
            score += weight
        elif a in q.get('negative_answers', []):
            score -= weight
    if score >= 6:
        return 'Planner', TRANSLATIONS['en']['quiz_planner_description'], TRANSLATIONS['en']['quiz_planner_tip']
    elif score >= 2:
        return 'Saver', TRANSLATIONS['en']['quiz_saver_description'], TRANSLATIONS['en']['quiz_saver_tip']
    elif score >= 0:
        return 'Balanced', TRANSLATIONS['en']['quiz_balanced_description'], TRANSLATIONS['en']['quiz_balanced_tip']
    elif score >= -2:
        return 'Spender', TRANSLATIONS['en']['quiz_spender_description'], TRANSLATIONS['en']['quiz_spender_tip']
    else:
        return 'Avoider', TRANSLATIONS['en']['quiz_avoider_description'], TRANSLATIONS['en']['quiz_avoider_tip']

def assign_badges_quiz(user_df, all_users_df):
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
            badges.append(badge['name'])
        elif badge['name'] == 'First Quiz Completed!' and len(user_df) >= 1:
            badges.append(badge['name'])
        elif badge['name'] == 'Needs Guidance!' and user_row['personality'] == 'Avoider' and len(all_users_df) > 10:
            badges.append(badge['name'])
    
    return badges

def generate_quiz_summary_chart(answers):
    labels = [q['question'] for q, _ in answers]
    scores = [3 if a in q.get('positive_answers', []) else -1 if a in q.get('negative_answers', []) else 0 for q, a in answers]
    return {
        "labels": labels,
        "datasets": [{
            "label": TRANSLATIONS['en']['quiz_your_answers'],
            "data": scores,
            "backgroundColor": "rgba(30, 127, 113, 0.2)",
            "borderColor": "#1E7F71",
            "pointBackgroundColor": "#1E7F71",
            "pointBorderColor": "#fff",
            "pointHoverBackgroundColor": "#fff",
            "pointHoverBorderColor": "#1E7F71"
        }]
    }

def generate_insights_and_tips(personality):
    insights = []
    tips = []
    if personality == 'Planner':
        insights.append(TRANSLATIONS['en']['quiz_planner_description'])
        tips.append(TRANSLATIONS['en']['quiz_planner_tip'])
    elif personality == 'Saver':
        insights.append(TRANSLATIONS['en']['quiz_saver_description'])
        tips.append(TRANSLATIONS['en']['quiz_saver_tip'])
    elif personality == 'Balanced':
        insights.append(TRANSLATIONS['en']['quiz_balanced_description'])
        tips.append(TRANSLATIONS['en']['quiz_balanced_tip'])
    elif personality == 'Spender':
        insights.append(TRANSLATIONS['en']['quiz_spender_description'])
        tips.append(TRANSLATIONS['en']['quiz_spender_tip'])
    elif personality == 'Avoider':
        insights.append(TRANSLATIONS['en']['quiz_avoider_description'])
        tips.append(TRANSLATIONS['en']['quiz_avoider_tip'])
    return insights, tips

def append_to_google_sheet(data, headers, worksheet_name='Quiz'):
    try:
        storage_managers = current_app.config['STORAGE_MANAGERS']
        if storage_managers['sheets'].append_to_sheet(data, headers, worksheet_name):
            return True
        else:
            flash(TRANSLATIONS['en']['google_sheets_error'], 'error')
            return False
    except Exception as e:
        current_app.logger.error(f"Google Sheets append error: {e}")
        flash(TRANSLATIONS['en']['google_sheets_error'], 'error')
        return False

def send_quiz_email(to_email, user_name, personality, personality_desc, tip, chart_data=None):
    try:
        msg = Message(
            subject=TRANSLATIONS['en']['quiz_financial_personality_quiz'],
            recipients=[to_email],
            html=render_template(
                'quiz_email.html',
                trans=trans,
                user_name=user_name or 'User',
                personality=personality,
                personality_desc=personality_desc,
                tip=tip,
                data={'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'), 'score': calculate_score([(QUESTIONS[int(k.split('_')[1]) - 1], v) for k, v in session.get('quiz_data', {}).items() if k.startswith('question_')]), 'badges': session.get('quiz_results', {}).get('latest_record', {}).get('badges', [])},
                base_url=current_app.config.get('BASE_URL', ''),
                language='en'
            )
        )
        current_app.extensions['mail'].send(msg)
        current_app.logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        current_app.logger.error(f"Email error to {to_email}: {e}")
        return False

def send_quiz_email_async(app, to_email, user_name, personality, personality_desc, tip, chart_data):
    with app.app_context():
        send_quiz_email(to_email, user_name, personality, personality_desc, tip, chart_data)

def partition_questions(questions, per_step=5):
    return [questions[i:i + per_step] for i in range(0, len(questions), per_step)]

# Setup session before every request
@quiz_bp.before_request
def setup_session():
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
    language = session.get('language', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')

    if request.method == 'GET' and 'quiz_data' in session:
        session.pop('quiz_data', None)
        current_app.logger.debug(f"Cleared quiz_data for session: {session['sid']}")

    form = QuizForm(personal_info=True, step_num=1, formdata=request.form if request.method == 'POST' else None)
    form.submit.label.text = TRANSLATIONS['en']['core_start_quiz']

    if request.method == 'POST':
        if form.validate_on_submit():
            session['quiz_data'] = {
                'first_name': form.first_name.data,
                'email': form.email.data,
                'send_email': form.send_email.data
            }
            session.modified = True
            current_app.logger.info(f"Step 1 validated, session: {session['quiz_data']}")

            progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
            progress = progress_storage.filter_by_session(session['sid'])
            course_progress = next((p for p in progress if p['data'].get('course_id') == course_id), None)
            if not course_progress:
                progress_data = {
                    'course_id': course_id,
                    'completed_lessons': [0],
                    'progress_percentage': (1 / (len(partition_questions(QUESTIONS)) + 1)) * 100,
                    'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                progress_storage.append(progress_data, session_id=session['sid'])
            else:
                if 0 not in course_progress['data'].get('completed_lessons', []):
                    course_progress['data']['completed_lessons'].append(0)
                    course_progress['data']['progress_percentage'] = (len(course_progress['data']['completed_lessons']) / (len(partition_questions(QUESTIONS)) + 1)) * 100
                    course_progress['data']['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    progress_storage.update_by_id(course_progress['id'], course_progress['data'])
            current_app.logger.info(f"Lesson 0 (step1) completed for course {course_id}")

            return redirect(url_for('quiz.quiz_step', step_num=1, course_id=course_id))
        else:
            current_app.logger.error(f"Validation failed: {form.errors}")
            flash(TRANSLATIONS['en']['form_errors'], 'error')

    return render_template(
        'quiz_step1.html',
        form=form,
        course_id=course_id,
        translations=TRANSLATIONS['en'],
        base_url=current_app.config.get('BASE_URL', ''),
        language=language
    )

@quiz_bp.route('/step/<int:step_num>', methods=['GET', 'POST'])
def quiz_step(step_num):
    if 'sid' not in session or 'quiz_data' not in session:
        flash(TRANSLATIONS['en']['session_expired'], 'error')
        return redirect(url_for('quiz.step1', course_id=request.args.get('course_id', 'financial_quiz')))

    language = session.get('language', 'en')
    steps = partition_questions(QUESTIONS, per_step=5)
    if step_num < 1 or step_num > len(steps):
        flash(TRANSLATIONS['en']['invalid_step'], 'error')
        return redirect(url_for('quiz.step1', course_id=request.args.get('course_id', 'financial_quiz')))

    questions = steps[step_num - 1]
    form = QuizForm(personal_info=False, step_num=step_num + 1, formdata=request.form if request.method == 'POST' else None)
    form.submit.label.text = TRANSLATIONS['en']['core_see_results'] if step_num == len(steps) else TRANSLATIONS['en']['core_continue']
    form.back.label.text = TRANSLATIONS['en']['core_back']

    if request.method == 'POST' and form.validate_on_submit():
        session['quiz_data'].update({f['id']: form[f['id']].data for f in questions})
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
        
        answers = [(QUESTIONS[int(k.split('_')[1]) - 1], v) for k, v in session['quiz_data'].items() if k.startswith('question_')]
        personality, personality_desc, tip = assign_personality(answers)
        score = calculate_score(answers)
        chart_data = generate_quiz_summary_chart(answers)
        user_df = pd.DataFrame([{
            'Timestamp': datetime.utcnow(),
            'first_name': session['quiz_data'].get('first_name', ''),
            'email': session['quiz_data'].get('email', ''),
            'language': language,
            'personality': personality,
            'score': score,
            **{f'question_{i}': QUESTIONS[i-1]['question'] for i in range(1, 11)},
            **{f'answer_{i}': session['quiz_data'].get(f'question_{i}', '') for i in range(1, 11)}
        }])

        storage_managers = current_app.config['STORAGE_MANAGERS']
        all_users_df = storage_managers['sheets'].fetch_data_from_sheet(
            headers=storage_managers['PREDETERMINED_HEADERS_QUIZ'],
            worksheet_name='Quiz'
        )

        badges = assign_badges_quiz(user_df, all_users_df)
        data = [
            datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
            session['quiz_data'].get('first_name', ''),
            session['quiz_data'].get('email', ''),
            language,
            *[QUESTIONS[i-1]['question'] for i in range(1, 11)],
            *[session['quiz_data'].get(f'question_{i}', '') for i in range(1, 11)],
            personality,
            str(score),
            ','.join(badges),
            str(session['quiz_data'].get('send_email', False)).lower()
        ]

        if not append_to_google_sheet(data, storage_managers['PREDETERMINED_HEADERS_QUIZ'], 'Quiz'):
            flash(TRANSLATIONS['en']['google_sheets_error'], 'error')
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
        insights, tips = generate_insights_and_tips(personality)
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
                      personality, personality_desc, tip, chart_data)
            ).start()
            flash(TRANSLATIONS['en']['check_inbox'], 'success')

        flash(TRANSLATIONS['en']['submission_success'])
        return redirect(url_for('quiz.results', course_id=course_id))

    if 'quiz_data' in session:
        current_app.logger.debug(f"Prepopulating form with session quiz_data: {session['quiz_data']}")
        for q in questions:
            if q['id'] in session['quiz_data']:
                try:
                    form[q['id']].data = session['quiz_data'][q['id']]
                except AttributeError:
                    current_app.logger.warning(f"Field {q['id']} not found in form for pre-population")
        try:
            form.send_email.data = bool(session['quiz_data'].get('send_email', False))
        except AttributeError as e:
            current_app.logger.error(f"Error prepopulating send_email: {e}")

    response = make_response(render_template(
        'quiz_step.html',
        form=form,
        questions=questions,
        step_num=step_num,
        total_steps=len(steps),
        course_id=course_id,
        translations=TRANSLATIONS['en'],
        base_url=current_app.config.get('BASE_URL', ''),
        language=language
    ))
    return response

@quiz_bp.route('/results', methods=['GET'])
def results():
    language = session.get('language', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')
    results = session.get('quiz_results', {})

    if not results:
        flash(TRANSLATIONS['en']['session_expired'], 'error')
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
        translations=TRANSLATIONS['en'],
        base_url=current_app.config.get('BASE_URL', ''),
        language=language
    ))
    return response

@quiz_bp.errorhandler(Exception)
def handle_error(e):
    current_app.logger.error(f"Global error: {str(e)} [session: {session.get('sid', 'unknown')}]", exc_info=True)
    flash(TRANSLATIONS['en']['quiz_config_error'], 'error')
    return redirect(url_for('quiz.step1'))
```
