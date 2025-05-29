from flask import Blueprint, current_app, session, has_request_context, request, redirect, url_for, render_template, flash
from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField, RadioField
from wtforms.validators import DataRequired, Email
import uuid
from datetime import datetime
import pandas as pd
import threading
import logging
from json_store import JsonStorage
from mailersend_email import send_email
from translations import trans

quiz_bp = Blueprint('quiz', __name__, template_folder='templates', static_folder='static', url_prefix='/quiz')

def init_storage(app, logger: logging.LoggerAdapter) -> JsonStorage:
    """Initialize storage with app context."""
    with app.app_context():
        storage = JsonStorage('data/financial_health.json', logger_instance=logger)
        logger.debug("Initialized JsonStorage for financial_health")
        return storage

QUESTIONS = [
    {
        'id': 'question_1',
        'key': 'track_expenses',
        'text_key': 'quiz_track_expenses_label',
        'options': ['quiz_yes', 'quiz_sometimes', 'quiz_no'],
        'positive_answers': ['quiz_yes'],
        'negative_answers': ['quiz_no'],
        'weight': 3
    },
    {
        'id': 'question_2',
        'key': 'save_regularly',
        'text_key': 'quiz_save_regularly_label',
        'options': ['quiz_yes', 'quiz_sometimes', 'quiz_no'],
        'positive_answers': ['quiz_yes'],
        'negative_answers': ['quiz_no'],
        'weight': 3
    },
    {
        'id': 'question_3',
        'key': 'spend_non_essentials',
        'text_key': 'quiz_spend_non_essentials_label',
        'options': ['quiz_yes', 'quiz_sometimes', 'quiz_no'],
        'positive_answers': ['quiz_no'],
        'negative_answers': ['quiz_yes'],
        'weight': 3
    },
    {
        'id': 'question_4',
        'key': 'plan_spending',
        'text_key': 'quiz_plan_spending_label',
        'options': ['quiz_yes', 'quiz_sometimes', 'quiz_no'],
        'positive_answers': ['quiz_yes'],
        'negative_answers': ['quiz_no'],
        'weight': 3
    },
    {
        'id': 'question_5',
        'key': 'impulse_purchases',
        'text_key': 'quiz_impulse_purchases_label',
        'options': ['quiz_yes', 'quiz_sometimes', 'quiz_no'],
        'positive_answers': ['quiz_no'],
        'negative_answers': ['quiz_yes'],
        'weight': 3
    },
    {
        'id': 'question_6',
        'key': 'use_budget',
        'text_key': 'quiz_use_budget_label',
        'options': ['quiz_yes', 'quiz_sometimes', 'quiz_no'],
        'positive_answers': ['quiz_yes'],
        'negative_answers': ['quiz_no'],
        'weight': 3
    },
    {
        'id': 'question_7',
        'key': 'invest_money',
        'text_key': 'quiz_invest_money_label',
        'options': ['quiz_yes', 'quiz_sometimes', 'quiz_no'],
        'positive_answers': ['quiz_yes'],
        'negative_answers': ['quiz_no'],
        'weight': 3
    },
    {
        'id': 'question_8',
        'key': 'emergency_fund',
        'text_key': 'quiz_emergency_fund_label',
        'options': ['quiz_yes', 'quiz_no'],
        'positive_answers': ['quiz_yes'],
        'negative_answers': ['quiz_no'],
        'weight': 3
    },
    {
        'id': 'question_9',
        'key': 'set_financial_goals',
        'text_key': 'quiz_set_financial_goals_label',
        'options': ['quiz_yes', 'quiz_sometimes', 'quiz_no'],
        'positive_answers': ['quiz_yes'],
        'negative_answers': ['quiz_no'],
        'weight': 3
    },
    {
        'id': 'question_10',
        'key': 'seek_financial_advice',
        'text_key': 'quiz_seek_financial_advice_label',
        'options': ['quiz_yes', 'quiz_sometimes', 'quiz_no'],
        'positive_answers': ['quiz_yes'],
        'negative_answers': ['quiz_no'],
        'weight': 3
    }
]

BADGES = [
    {
        'key': 'badge_starter',
        'min_score': 0,
        'max_score': 5,
        'description_key': 'badge_starter_description',
        'color_class': 'badge-bronze',
        'resources': [
            {'url': '/tools/budget', 'label_key': 'resource_budget_tool'},
            {'url': '/courses/financial-planning', 'label_key': 'resource_financial_planning'}
        ]
    },
    {
        'key': 'badge_resilient_earner',
        'min_score': 6,
        'max_score': 15,
        'description_key': 'badge_resilient_earner_description',
        'color_class': 'badge-silver',
        'resources': [
            {'url': '/tools/budget', 'label_key': 'resource_budget_tool'},
            {'url': '/courses/emergency-fund', 'label_key': 'resource_emergency_fund_course'}
        ]
    },
    {
        'key': 'badge_money_mover',
        'min_score': 16,
        'max_score': 25,
        'description_key': 'badge_money_mover_description',
        'color_class': 'badge-gold',
        'resources': [
            {'url': '/courses/emergency-fund', 'label_key': 'resource_emergency_fund_course'},
            {'url': '/guides/investment', 'label_key': 'resource_investment_guide'}
        ]
    },
    {
        'key': 'badge_financial_guru',
        'min_score': 26,
        'max_score': 30,
        'description_key': 'badge_financial_guru_description',
        'color_class': 'badge-platinum',
        'resources': [
            {'url': '/guides/investment', 'label_key': 'resource_investment_guide'},
            {'url': '/courses/financial-planning', 'label_key': 'resource_financial_planning'}
        ]
    },
    {
        'key': 'badge_first_quiz_completed',
        'min_score': 0,
        'max_score': 30,
        'description_key': 'badge_first_quiz_completed_description',
        'color_class': 'badge-blue',
        'resources': [
            {'url': '/tools/budget', 'label_key': 'resource_budget_tool'}
        ]
    },
    {
        'key': 'badge_unranked',
        'min_score': None,
        'max_score': None,
        'description_key': 'badge_unranked_description',
        'color_class': 'badge-gray',
        'resources': []
    }
]

class QuizAnalytics:
    def __init__(self, storage: JsonStorage, logger: logging.LoggerAdapter):
        self.storage = storage
        self.logger = logger
        self.headers = ['Timestamp', 'Started', 'Completed', 'Completion_Rate', 'Avg_Score_Planner',
                        'Avg_Score_Saver', 'Avg_Score_Balanced', 'Avg_Score_Spender', 'Avg_Score_Avoider',
                        'Badge_Starter', 'Badge_Resilient_Earner', 'Badge_Money_Mover', 'Badge_Financial_Guru',
                        'Badge_First_Quiz_Completed', 'Badge_Unranked']

    def update_analytics(self, user_df: pd.DataFrame, all_users_df: pd.DataFrame) -> None:
        session_id = session.get('sid', 'no-session-id') if has_request_context() else 'no-session-id'
        try:
            started = len(set(all_users_df['email'].dropna()))
            completed = len(all_users_df[all_users_df['score'].notnull()])
            completion_rate = (completed / started * 100) if started > 0 else 0

            avg_scores = {
                'Planner': all_users_df[all_users_df['personality'] == 'Planner']['score'].mean(),
                'Saver': all_users_df[all_users_df['personality'] == 'Saver']['score'].mean(),
                'Balanced': all_users_df[all_users_df['personality'] == 'Balanced']['score'].mean(),
                'Spender': all_users_df[all_users_df['personality'] == 'Spender']['score'].mean(),
                'Avoider': all_users_df[all_users_df['personality'] == 'Avoider']['score'].mean()
            }

            badge_counts = {badge['key'].replace('badge_', ''): 0 for badge in BADGES}
            for badge_list in all_users_df['badges'].dropna():
                for badge in badge_list:
                    badge_key = badge['key'].replace('badge_', '')
                    if badge_key in badge_counts:
                        badge_counts[badge_key] += 1

            data = {
                'Timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'Started': started,
                'Completed': completed,
                'Completion_Rate': round(completion_rate, 2),
                'Avg_Score_Planner': round(avg_scores.get('Planner', 0), 2),
                'Avg_Score_Saver': round(avg_scores.get('Saver', 0), 2),
                'Avg_Score_Balanced': round(avg_scores.get('Balanced', 0), 2),
                'Avg_Score_Spender': round(avg_scores.get('Spender', 0), 2),
                'Avg_Score_Avoider': round(avg_scores.get('Avoider', 0), 2),
                **{f'Badge_{k.capitalize()}': v for k, v in badge_counts.items()}
            }

            self.storage.append({'id': str(uuid.uuid4()), 'data': data})
            self.logger.info("Updated quiz analytics", extra={'session_id': session_id})
        except Exception as e:
            self.logger.error(f"Analytics update error: {str(e)}", extra={'session_id': session_id})

class QuizForm(FlaskForm):
    def __init__(self, personal_info: bool = True, step_num: int = 1, language: str = 'en', **kwargs):
        super().__init__(**kwargs)
        self.personal_info = personal_info
        self.step_num = step_num
        self.language = language

        if personal_info:
            self.first_name = StringField(
                validators=[DataRequired()],
                render_kw={'placeholder': trans('core_first_name_placeholder', lang=language), 'title': trans('core_first_name_tooltip', lang=language), 'aria-label': trans('core_first_name', lang=language)}
            )
            self.email = StringField(
                validators=[DataRequired(), Email()],
                render_kw={'placeholder': trans('core_email_placeholder', lang=language), 'title': trans('core_email_tooltip', lang=language), 'aria-label': trans('core_email', lang=language)}
            )
            self.send_email = BooleanField(
                default=False,
                render_kw={'title': trans('core_send_email_tooltip', lang=language), 'aria-label': trans('core_send_email', lang=language)}
            )
            self.submit = SubmitField(render_kw={'aria-label': trans('core_submit', lang=language)})
            self.first_name.label.text = trans('core_first_name', lang=language)
            self.email.label.text = trans('core_email', lang=language)
            self.send_email.label.text = trans('core_send_email', lang=language)
            self.submit.label.text = trans('core_submit', lang=language)
        else:
            self.send_email = BooleanField(
                default=False,
                render_kw={'title': trans('core_send_email_tooltip', lang=language), 'aria-label': trans('core_send_email', lang=language)}
            )
            self.submit = SubmitField(render_kw={'aria-label': trans('core_submit', lang=language)})
            self.back = SubmitField(render_kw={'aria-label': trans('core_back', lang=language)})
            self.send_email.label.text = trans('core_send_email', lang=language)
            self.submit.label.text = trans('core_submit', lang=language)
            self.back.label.text = trans('core_back', lang=language)
            question_indices = range(1, 6) if step_num == 2 else range(6, 11)
            for idx in question_indices:
                q = QUESTIONS[idx - 1]
                choices = [(opt, trans(opt, lang=language)) for opt in q['options']]
                field = RadioField(
                    choices=choices,
                    validators=[DataRequired()],
                    render_kw={'aria-label': trans(q['text_key'], lang=language), 'title': trans(f'{q["key"]}_tooltip', lang=language, default='')}
                )
                field.label.text = trans(q['text_key'], lang=language)
                setattr(self, q['id'], field)
            fields_to_keep = [f'question_{i}' for i in question_indices] + ['send_email', 'submit', 'back']
            for field_name in list(self._fields.keys()):
                if field_name not in fields_to_keep:
                    del self._fields[field_name]
        current_app.logger.debug(f"Initialized QuizForm: personal_info={personal_info}, step_num={step_num}, language={language}, fields={list(self._fields.keys())}")

    def validate(self, extra_validators=None):
        session_id = session.get('sid', 'no-session-id') if has_request_context() else 'no-session-id'
        current_app.logger.debug(f"Validating QuizForm: fields={list(self._fields.keys())}", extra={'session_id': session_id})
        rv = super().validate(extra_validators)
        if not rv:
            current_app.logger.error(f"Validation errors: {self.errors}", extra={'session_id': session_id})
            flash(trans('quiz_form_errors', lang=self.language, default='Please correct the errors in the form.'), 'error')
        return rv

def calculate_score(answers):
    score = 0
    for question, answer in answers:
        if answer in question.get('positive_answers', []):
            score += question['weight']
        elif answer in question.get('negative_answers', []):
            score -= 1
    return max(0, min(30, score))

def assign_personality(score: int, language: str = 'en'):
    if score >= 26:
        return 'Planner', trans('quiz_planner_description', lang=language), trans('quiz_planner_tip', lang=language)
    elif score >= 16:
        return 'Saver', trans('quiz_saver_description', lang=language), trans('quiz_saver_tip', lang=language)
    elif score >= 6:
        return 'Balanced', trans('quiz_balanced_description', lang=language), trans('quiz_balanced_tip', lang=language)
    elif score >= 0:
        return 'Spender', trans('quiz_spender_description', lang=language), trans('quiz_spender_tip', lang=language)
    else:
        return 'Avoider', trans('quiz_avoider_description', lang=language), trans('quiz_avoider_tip', lang=language)

def assign_badges_quiz(user_df: pd.DataFrame, all_users_df: pd.DataFrame, language: str = 'en'):
    session_id = session.get('sid', 'no-session-id') if has_request_context() else 'no-session-id'
    badges = []
    if user_df.empty:
        current_app.logger.warning(f"Empty user_df in assign_badges_quiz", extra={'session_id': session_id})
        return [{'name': trans('badge_unranked', lang=language), 'color_class': 'badge-gray', 'description': trans('badge_unranked_description', lang=language)}]

    user_row = user_df.iloc[0]
    score = user_row.get('score', None)
    
    if score is None:
        current_app.logger.warning(f"No score found for user", extra={'session_id': session_id})
        return [{'name': trans('badge_unranked', lang=language), 'color_class': 'badge-gray', 'description': trans('badge_unranked_description', lang=language)}]

    for badge in BADGES:
        min_score = badge.get('min_score')
        max_score = badge.get('max_score')
        if badge['key'] == 'badge_first_quiz_completed' and len(user_df) >= 1:
            badges.append({
                'key': badge['key'],
                'name': trans(badge['key'], lang=language),
                'color_class': badge.get('color_class', 'badge-gray'),
                'description': trans(badge['description_key'], lang=language)
            })
        elif badge['key'] == 'badge_unranked':
            continue
        elif min_score is not None and max_score is not None and min_score <= score <= max_score:
            badges.append({
                'key': badge['key'],
                'name': trans(badge['key'], lang=language),
                'color_class': badge.get('color_class', 'badge-gray'),
                'description': trans(badge['description_key'], lang=language)
            })
    
    if not badges:
        current_app.logger.warning(f"No matching badge for score={score}", extra={'session_id': session_id})
        badges.append({
            'key': 'badge_unranked',
            'name': trans('badge_unranked', lang=language),
            'color_class': 'badge-gray',
            'description': trans('badge_unranked_description', lang=language)
        })
    
    return badges

def get_badge_resources(badges: list, language: str = 'en'):
    resources = []
    for badge in BADGES:
        if any(b['key'] == badge['key'] for b in badges):
            for resource in badge.get('resources', []):
                resources.append({
                    'url': resource['url'],
                    'label': trans(resource['label_key'], lang=language)
                })
    return resources

def generate_quiz_summary_chart(answers: list, language: str = 'en'):
    labels = [trans(q['text_key'], lang=language)[:30] + '...' if len(trans(q['text_key'], lang=language)) > 30 else trans(q['text_key'], lang=language) for q, _ in answers]
    scores = [q['weight'] if a in q.get('positive_answers', []) else -1 if a in q.get('negative_answers', []) else 0 for q, a in answers]
    return {
        'labels': labels,
        'datasets': [{
            'label': trans('quiz_your_answers', lang=language),
            'data': scores,
            'backgroundColor': 'rgba(30, 127, 113, 0.2)',
            'borderColor': '#1E7F71',
            'pointBackgroundColor': '#1E7F71',
            'pointBorderColor': '#fff',
            'pointHoverBackgroundColor': '#fff',
            'pointHoverBorderColor': '#1E7F71'
        }]
    }

def generate_insights_and_tips(personality: str, language: str = 'en'):
    insights = [trans(f'quiz_{personality.lower()}_insight', lang=language)]
    tips = [
        trans(f'quiz_{personality.lower()}_tip', lang=language),
        trans('quiz_use_budgeting_app', lang=language),
        trans('quiz_set_emergency_fund', lang=language),
        trans('quiz_review_goals', lang=language)
    ]
    return insights, tips

def store_quiz_data(data: dict, language: str = 'en', logger: logging.LoggerAdapter) -> bool:
    session_id = session.get('sid', 'no-session-id') if has_request_context() else 'no-session-id'
    try:
        storage = current_app.config['STORAGE_MANAGERS']['financial_health']
        storage.append(data)
        logger.info("Stored quiz data", extra={'session_id': session_id})
        return True
    except Exception as e:
        logger.error(f"Storage error: {str(e)}", extra={'session_id': session_id})
        flash(trans('quiz_storage_error', lang=language), 'error')
        return False

def send_quiz_email(to_email: str, user_name: str, personality: str, personality_desc: str, answers: list, badges: list, language: str = 'en', app: 'Flask', logger: logging.LoggerAdapter) -> bool:
    session_id = session.get('sid', 'no-session-id') if has_request_context() else 'no-session-id'
    try:
        send_email(
            app=app,
            logger=logger,
            to_email=to_email,
            subject=trans('quiz_results_subject', lang=language),
            template_name='quiz/email',
            data={
                'user_name': user_name or trans('core_user', lang=language),
                'personality': personality,
                'personality_desc': personality_desc,
                'answers': [(trans(q['text_key'], lang=language), trans(a, lang=language)) for q, a in answers],
                'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
                'score': calculate_score(answers),
                'badges': badges,
                'base_url': app.config.get('BASE_URL', ''),
                'language': language
            },
            lang=language
        )
        logger.info(f"Email sent to {to_email}", extra={'session_id': session_id})
        return True
    except Exception as e:
        logger.error(f"Email error to {to_email}: {str(e)}", extra={'session_id': session_id})
        return False

def send_quiz_email_async(app: 'Flask', to_email: str, user_name: str, personality: str, personality_desc: str, answers: list, badges: list, language: str, logger: logging.LoggerAdapter):
    session_id = session.get('sid', 'no-session-id') if has_request_context() else 'no-session-id'
    with app.app_context():
        try:
            send_quiz_email(to_email, user_name, personality, personality_desc, answers, badges, language, app, logger)
        except Exception as e:
            logger.error(f"Async email error to {to_email}: {str(e)}", extra={'session_id': session_id})

def partition_questions(questions: list, per_step: int = 5) -> list:
    return [questions[i:i + per_step] for i in range(0, len(questions), per_step)]

@quiz_bp.before_request
def setup_session():
    logger = current_app.logger
    session_id = session.get('sid', 'no-session-id')
    try:
        if 'sid' not in session:
            session['sid'] = str(uuid.uuid4())
            session.permanent = True
            logger.debug(f"Initialized new session ID: {session['sid']}", extra={'session_id': session['sid']})
        if 'language' not in session:
            session['language'] = 'en'
            logger.debug("Set default language: en", extra={'session_id': session_id})
        if 'quiz_history' not in session:
            session['quiz_history'] = []
        session.modified = True
    except Exception as e:
        logger.error(f"Session setup error: {str(e)}", extra={'session_id': session_id})

@quiz_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    logger = current_app.logger
    session_id = session.get('sid', 'no-session-id')
    language = session.get('language', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')
    form = QuizForm(personal_info=True, language=language)
    form.submit.label.text = trans('quiz_start_quiz', lang=language)

    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['quiz_data'] = {
                'first_name': form.first_name.data,
                'email': form.email.data,
                'send_email': form.send_email.data
            }
            session.modified = True
            logger.info(f"Step 1 validated", extra={'session_id': session_id})

            progress_storage = current_app.config['STORAGE_MANAGERS']['financial_health']
            progress = progress_storage.read_all()
            course_progress = next((p for p in progress if p['data'].get('course_id') == course_id and p['data'].get('session_id') == session_id), None)
            if not course_progress:
                progress_data = {
                    'id': str(uuid.uuid4()),
                    'data': {
                        'course_id': course_id,
                        'session_id': session_id,
                        'completed_tasks': [0],
                        'progress_percentage': (1 / (len(partition_questions(QUESTIONS)) + 1)) * 100,
                        'last_updated': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    }
                }
                progress_storage.append(progress_data)
            else:
                if 0 not in course_progress['data'].get('completed_tasks', []):
                    course_progress['data']['completed_tasks'].append(0)
                    course_progress['data']['progress_percentage'] = (len(course_progress['data']['completed_tasks']) / (len(partition_questions(QUESTIONS)) + 1)) * 100
                    course_progress['data']['last_updated'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    progress_storage.update_by_id(course_progress['id'], course_progress['data'])
            logger.info(f"Task 0 (step1) completed for course {course_id}", extra={'session_id': session_id})

            return redirect(url_for('quiz.quiz_step', step_num=1, course_id=course_id))
        
        return render_template(
            'quiz_step1.html',
            form=form,
            course_id=course_id,
            trans=trans,
            language=language,
            base_url=current_app.config.get('BASE_URL', '')
        )
    except Exception as e:
        logger.error(f"Error in step1: {str(e)}", extra={'session_id': session_id})
        flash(trans('quiz_config_error', lang=language), 'error')
        return render_template(
            'quiz_step1.html',
            form=form,
            course_id=course_id,
            trans=trans,
            language=language,
            base_url=current_app.config.get('BASE_URL', '')
        ),
    500

@quiz_bp.route('/step/<int:step_num>', methods=['GET', 'POST'])
def quiz_step(step_num):
    logger = current_app.logger
    session_id = session.get('sid', 'no-session-id')
    language = session.get('language', 'en')
    if 'sid' not in session or 'quiz_data' not in session:
        logger.warning(f"Session expired", extra={'session_id': session_id})
        flash(trans('quiz_session_expired', lang=language), 'error')
        return redirect(url_for('quiz.step1', course_id=request.args.get('course_id', 'financial_quiz')))

    steps = partition_questions(QUESTIONS)
    if step_num < 1 or step_num > len(steps):
        logger.error(f"Invalid step number: {step_num}", extra={'session_id': session_id})
        flash(trans('quiz_invalid_step', lang=language), 'error')
        return redirect(url_for('quiz.step1', course_id=request.args.get('course_id', 'financial_quiz')))

    questions = steps[step_num - 1]
    form = QuizForm(personal_info=False, step_num=step_num + 1, language=language)
    form.submit.label.text = trans('core_see_results', lang=language) if step_num == len(steps) else trans('core_continue', lang=language)

    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['quiz_data'].update({q['id']: form.data[q['id']] for q in questions})
            session['quiz_data']['send_email'] = form.send_email.data
            session.modified = True

            course_id = request.args.get('course_id', 'financial_quiz')
            progress_storage = current_app.config['STORAGE_MANAGERS']['financial_health']
            progress = progress_storage.read_all()
            course_progress = next((p for p in progress if p['data'].get('course_id') == course_id and p['data'].get('session_id') == session_id), None)
            if course_progress and step_num not in course_progress['data'].get('completed_tasks', []):
                course_progress['data']['completed_tasks'].append(step_num)
                course_progress['data']['progress_percentage'] = (len(course_progress['data'].get('completed_tasks', [])) / (len(partition_questions(QUESTIONS)) + 1)) * 100
                course_progress['data']['last_updated'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                progress_storage.update_by_id(course_progress['id'], course_progress['data'])

            if step_num < len(steps):
                logger.info(f"Completed step {step_num}, proceeding to step {step_num + 1}", extra={'session_id': session_id})
                return redirect(url_for('quiz.quiz_step', step_num=step_num + 1, course_id=course_id))
            
            answers = [(q, session['quiz_data'].get(q['id'], '')) for q in QUESTIONS if q['id'] in session['quiz_data']]
            score = calculate_score(answers)
            personality, personality_desc, tip = assign_personality(score, language)
            chart_data = generate_quiz_summary_chart(answers, language)
            user_df = pd.DataFrame([{
                'Timestamp': datetime.utcnow().isoformat(),
                'first_name': session['quiz_data'].get('first_name', ''),
                'email': session['quiz_data'].get('email', ''),
                'language': language,
                'personality': personality,
                'score': score,
                **{f'question_{i}': trans(q['text_key'], lang=language) for i, q in enumerate(QUESTIONS, 1)},
                **{f'answer_{i}': trans(session['quiz_data'].get(q['id'], ''), lang=language) for i, q in enumerate(QUESTIONS, 1)}
            }])

            storage = current_app.config['STORAGE_MANAGERS']['financial_health']
            all_users_data = storage.read_all()
            all_users_df = pd.DataFrame([record['data'] for record in all_users_data if 'data' in record])

            badges = assign_badges_quiz(user_df, all_users_df, language)
            resources = get_badge_resources(badges, language)
            data = {
                'id': str(uuid.uuid4()),
                'data': {
                    'Timestamp': datetime.utcnow().isoformat(),
                    'first_name': session['quiz_data'].get('first_name', ''),
                    'email': session['quiz_data'].get('email', ''),
                    'language': language,
                    **{f'question_{i}': trans(q['text_key'], lang=language) for i, q in enumerate(QUESTIONS, 1)},
                    **{f'answer_{i}': trans(session['quiz_data'].get(q['id'], ''), lang=language) for i, q in enumerate(QUESTIONS, 1)},
                    'personality': personality,
                    'score': score,
                    'badges': badges,
                    'send_email': session['quiz_data'].get('send_email', False)
                }
            }

            if not store_quiz_data(data, language, logger, storage):
                logger.error(f"Failed to store quiz results", extra={'session_id': session_id})
                return redirect(url_for('quiz.quiz_step', step_num=step_num, course_id=course_id))

            analytics = QuizAnalytics(storage, logger)
            analytics.update_analytics(user_df, all_users_df)

            quiz_record = {
                'created_at': datetime.utcnow().isoformat(),
                'personality': personality,
                'score': score,
                'badges': badges,
                'resources': resources
            }
            session['quiz_history'].append(quiz_record)
            session.modified = True

            records = []
            if not all_users_df.empty:
                user_records = all_users_df[all_users_df['email'] == session['quiz_data'].get('email', '')].sort_values('Timestamp')
                for _, row in user_records.iterrows():
                    records.append({
                        'created_at': row['Timestamp'],
                        'personality': row['personality'],
                        'score': float(row['score']) if pd.notnull(row['score']) else 0,
                        'badges': row['badges'] if pd.notnull(row['badges']) else []
                    })

            insights, tips = generate_insights_and_tips(personality, language)
            session['quiz_results'] = {
                'latest_record': {
                    'first_name': session['quiz_data'].get('first_name', ''),
                    'personality': personality,
                    'score': score,
                    'badges': badges,
                    'resources': resources,
                    'created_at': datetime.utcnow().isoformat(),
                    'chart_data': chart_data,
                    'insights': insights,
                    'tips': tips
                },
                'records': records,
                'insights': insights,
                'tips': tips
            }

            if session['quiz_data'].get('send_email', '') and session['quiz_data'].get('email'):
                threading.Thread(
                    target=send_quiz_email_async,
                    args=(current_app._get_current_object(), 
                          session['quiz_data'].get('email', ''),
                          session['quiz_data'].get('first_name', ''), 
                          personality, 
                          personality_desc, 
                          answers, 
                          badges, 
                          language, 
                          logger)
                ).start()
                logger.info(f"Initiated async email to {session['quiz_data'].get('email']}", extra={'session_id': session_id})
                flash(trans('quiz_check_inbox', lang=language), 'success')

            flash(trans('quiz_submission_success', lang=language), 'success')
            return redirect(url_for('quiz.results', course_id=course_id))

        if 'quiz_data' in session:
            for q in questions:
                if q['id'] in session['quiz_data']:
                    form.form[q['id']].data = session['quiz_data'].get(q['id'])
            form.send_email.form.data = session['quiz_data'].get('send_email', False)

        return render_template(
            'quiz_step.html',
            form=form,
            questions=questions,
            step_num=step_num,
            total_steps=len(steps),
            course_id=course_id,
            trans=trans,
            language=language,
            base_url=current_app.config.get('BASE_URL', '')
        )
    except Exception as e:
        logger.error(f"Error in quiz_step {step_num}: {str(e)}", extra={'session_id': session_id})
        flash(trans('quiz_config_error', lang=language), 'error')
        return render_template(
            'quiz_step.html',
            form=form,
            questions=questions,
            step_num=step_num,
            total_steps=len(steps),
            course_id=course_id,
            trans=trans,
            language=language,
            base_url=current_app.config.get('BASE_URL', '')
        ), 500

@quiz_bp.route('/results', methods=['GET'])
def results():
    logger = current_app.logger
    session_id = session.get('sid', 'no-session-id')
    language = session.get('language', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')
    results = session.get('quiz_results', {}))

    try:
        if not results:
            flash(trans('quiz_session_expired', lang=language), 'error')
            return redirect(url_for('quiz.step1', course_id=course_id))

        return render_template(
            'quiz_results.html',
            latest_record=results.get('latest_record', {}),
            records=results.get('records', []),
            insights=results.get('insights', []),
            tips=results.get('tips', []),
            chart_data=results.get('latest_record', {}).get('chart_data', {}),
            course_id=course_id,
            trans=trans,
            language=language,
            base_url=current_app.config.get('BASE_URL', '')
        )
    except Exception as e:
        logger.error(f"Error in results: {str(e)}", extra={'session_id': session_id})
        flash(trans('quiz_config_error', lang=language), 'error')
        return redirect(url_for('quiz.step1', course_id=course_id))

@quiz_bp.route('/history', methods=['GET'])
def history():
    logger = current_app.logger
    session_id = session.get('sid', 'no-session-id')
    language = session.get('language', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')
    history = session.get('quiz_history', [])

    try:
        if not history:
            flash(trans('quiz_no_history', lang=language), 'info')
            return redirect(url_for('quiz.step1', course_id=course_id))

        return render_template(
            'quiz_history.html',
            history=history,
            course_id=course_id,
            trans=trans,
            language=language,
            base_url=current_app.config.get('BASE_URL', '')
        )

    except Exception as e:
        logger.error(f"Error in history: {str(e)}", extra={'session_id': session_id})
        flash(trans('quiz_config_error', lang=language), 'error')
        return redirect(url_for('quiz.step1', course_id=course_id))

@quiz_bp.route('/analytics', methods=['GET'])
def analytics():
    logger = current_app.logger
    session_id = session.get('sid', 'no-session-id')
    language = session.get('language', 'en')
    storage = current_app.config['STORAGE_MANAGERS']['financial_health']
    analytics_data = storage.read_all()
    analytics_df = pd.DataFrame([record['data'] for record in analytics_data if 'data' in record and 'Started' in record['data']])

    try:
        if analytics_df.empty:
            flash(trans('quiz_no_quiz_data_available', lang=language), 'info')
            return render_template(
                'quiz_analytics.html',
                analytics={},
                trans=trans,
                language=language
            )

        latest_analytics = analytics_df.iloc[-1].to_dict()
        return render_template(
            'quiz_analytics.html',
            analytics=latest_analytics,
            trans=trans,
            language=language
        )
    except Exception as e:
        logger.error(f"Error in analytics: {str(e)}", extra={'session_id': session_id})
        flash(trans('quiz_config_error', lang=language), 'error')
        return render_template(
            'quiz_analytics.html',
            analytics={},
            trans=trans,
            language=language
        ),
    500

@quiz_bp.errorhandler(Exception)
def handle_error(e):
    logger = current_app.logger
    session_id = session.get('sid', 'no-session-id')
    logger.error(f"Global error: {str(e)}", extra={'session_id': session_id}, exc_info=True)
    flash(trans('quiz_config_error', lang=session.get('language', 'en')), 'error')
    return redirect(url_for('quiz.step1', course_id=request.args.get('course_id', 'financial_quiz')))
