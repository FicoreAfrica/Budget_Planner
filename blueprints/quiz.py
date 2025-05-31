from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, BooleanField, SubmitField, RadioField
from wtforms.validators import DataRequired, Email, Optional
import uuid
from datetime import datetime
import pandas as pd
import logging
from translations import trans

# Configure logging
logger = logging.getLogger('ficore_app')

# Define the quiz blueprint
quiz_bp = Blueprint('quiz', __name__, template_folder='templates', static_folder='static', url_prefix='/quiz')

# Form for Step 1: Personal Information
class QuizStep1Form(FlaskForm):
    first_name = StringField(validators=[DataRequired()], render_kw={
        'placeholder': trans('core_first_name_placeholder', default='e.g., Muhammad, Bashir, Umar'),
        'title': trans('core_first_name_title', default='Enter your first name to personalize your quiz results')
    })
    email = StringField(validators=[DataRequired(), Email()], render_kw={
        'placeholder': trans('core_email_placeholder', default='e.g., muhammad@example.com'),
        'title': trans('core_email_title', default='Enter your email to receive quiz results')
    })
    language = SelectField(choices=[('en', 'English'), ('ha', 'Hausa')], default='en', validators=[Optional()])
    send_email = BooleanField(default=False, validators=[Optional()], render_kw={
        'title': trans('core_send_email_title', default='Check to receive an email with your quiz results')
    })
    submit = SubmitField()

    def __init__(self, language='en', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.first_name.label.text = trans('core_first_name', default='First Name', lang=language)
        self.email.label.text = trans('core_email', default='Email', lang=language)
        self.language.label.text = trans('core_language', default='Language', lang=language)
        self.send_email.label.text = trans('core_send_email', default='Send Email', lang=language)
        self.submit.label.text = trans('quiz_start_quiz', default='Start Quiz', lang=language)
        self.language.choices = [
            ('en', trans('core_language_en', default='English', lang=language)),
            ('ha', trans('core_language_ha', default='Hausa', lang=language))
        ]

# Form for Step 2a: Questions 1-5
class QuizStep2aForm(FlaskForm):
    question_1 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_1')
    question_2 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_2')
    question_3 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_3')
    question_4 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_4')
    question_5 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_5')
    submit = SubmitField()
    back = SubmitField()

    def __init__(self, language='en', *args, **kwargs):
        super().__init__(*args, **kwargs)
        questions = [
            {'id': 'question_1', 'text_key': 'quiz_track_expenses_label', 'text': 'Do you track your expenses regularly?', 'tooltip_key': 'quiz_track_expenses_tooltip'},
            {'id': 'question_2', 'text_key': 'quiz_save_regularly_label', 'text': 'Do you save a portion of your income regularly?', 'tooltip_key': 'quiz_save_regularly_tooltip'},
            {'id': 'question_3', 'text_key': 'quiz_budget_monthly_label', 'text': 'Do you set a monthly budget?', 'tooltip_key': 'quiz_budget_monthly_tooltip'},
            {'id': 'question_4', 'text_key': 'quiz_emergency_fund_label', 'text': 'Do you have an emergency fund?', 'tooltip_key': 'quiz_emergency_fund_tooltip'},
            {'id': 'question_5', 'text_key': 'quiz_invest_regularly_label', 'text': 'Do you invest your money regularly?', 'tooltip_key': 'quiz_invest_regularly_tooltip'},
        ]
        for q in questions:
            field = getattr(self, q['id'])
            field.label.text = trans(q['text_key'], default=q['text'], lang=language)
            field.description = trans(q['tooltip_key'], default='', lang=language)
            field.choices = [(opt, trans(opt, default=opt, lang=language)) for opt in ['Yes', 'No']]
        self.submit.label.text = trans('core_continue', default='Continue', lang=language)
        self.back.label.text = trans('core_back', default='Back', lang=language)

# Form for Step 2b: Questions 6-10
class QuizStep2bForm(FlaskForm):
    question_6 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_6')
    question_7 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_7')
    question_8 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_8')
    question_9 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_9')
    question_10 = RadioField(validators=[DataRequired()], choices=[('Yes', 'Yes'), ('No', 'No')], id='question_10')
    submit = SubmitField()
    back = SubmitField()

    def __init__(self, language='en', *args, **kwargs):
        super().__init__(*args, **kwargs)
        questions = [
            {'id': 'question_6', 'text_key': 'quiz_spend_impulse_label', 'text': 'Do you often spend money on impulse?', 'tooltip_key': 'quiz_spend_impulse_tooltip'},
            {'id': 'question_7', 'text_key': 'quiz_financial_goals_label', 'text': 'Do you set financial goals?', 'tooltip_key': 'quiz_financial_goals_tooltip'},
            {'id': 'question_8', 'text_key': 'quiz_review_spending_label', 'text': 'Do you review your spending habits regularly?', 'tooltip_key': 'quiz_review_spending_tooltip'},
            {'id': 'question_9', 'text_key': 'quiz_multiple_income_label', 'text': 'Do you have multiple sources of income?', 'tooltip_key': 'quiz_multiple_income_tooltip'},
            {'id': 'question_10', 'text_key': 'quiz_retirement_plan_label', 'text': 'Do you have a retirement savings plan?', 'tooltip_key': 'quiz_retirement_plan_tooltip'},
        ]
        for q in questions:
            field = getattr(self, q['id'])
            field.label.text = trans(q['text_key'], default=q['text'], lang=language)
            field.description = trans(q['tooltip_key'], default='', lang=language)
            field.choices = [(opt, trans(opt, default=opt, lang=language)) for opt in ['Yes', 'No']]
        self.submit.label.text = trans('quiz_see_results', default='See Results', lang=language)
        self.back.label.text = trans('core_back', default='Back', lang=language)

# Helper Functions
def calculate_score(answers):
    score = 0
    positive_questions = ['question_1', 'question_2', 'question_3', 'question_4', 'question_5', 'question_7', 'question_8', 'question_9', 'question_10']
    negative_questions = ['question_6']
    for i, answer in enumerate(answers, 1):
        qid = f'question_{i}'
        if qid in positive_questions and answer == 'Yes':
            score += 3
        elif qid in positive_questions and answer == 'No':
            score -= 1
        elif qid in negative_questions and answer == 'No':
            score += 3
        elif qid in negative_questions and answer == 'Yes':
            score -= 1
    return max(0, score)

def assign_personality(score, language='en'):
    if score >= 21:
        return {
            'name': 'Planner',
            'description': trans('quiz_planner_description', default='You plan your finances meticulously.', lang=language),
            'insights': [trans('quiz_insight_planner_1', default='You have a strong grasp of financial planning.', lang=language)],
            'tips': [trans('quiz_tip_planner_1', default='Continue setting long-term goals.', lang=language)]
        }
    elif score >= 13:
        return {
            'name': 'Saver',
            'description': trans('quiz_saver_description', default='You prioritize saving consistently.', lang=language),
            'insights': [trans('quiz_insight_saver_1', default='You excel at saving regularly.', lang=language)],
            'tips': [trans('quiz_tip_saver_1', default='Consider investing to grow your savings.', lang=language)]
        }
    elif score >= 7:
        return {
            'name': 'Balanced',
            'description': trans('quiz_balanced_description', default='You maintain a balanced financial approach.', lang=language),
            'insights': [trans('quiz_insight_balanced_1', default='You balance saving and spending well.', lang=language)],
            'tips': [trans('quiz_tip_balanced_1', default='Try a budgeting app to optimize habits.', lang=language)]
        }
    elif score >= 3:
        return {
            'name': 'Spender',
            'description': trans('quiz_spender_description', default='You enjoy spending freely.', lang=language),
            'insights': [trans('quiz_insight_spender_1', default='Spending is a strength, but can be controlled.', lang=language)],
            'tips': [trans('quiz_tip_spender_1', default='Track expenses to avoid overspending.', lang=language)]
        }
    else:
        return {
            'name': 'Avoider',
            'description': trans('quiz_avoider_description', default='You avoid financial planning.', lang=language),
            'insights': [trans('quiz_insight_avoider_1', default='Planning feels challenging but is learnable.', lang=language)],
            'tips': [trans('quiz_tip_avoider_1', default='Start with a simple monthly budget.', lang=language)]
        }

def assign_badges(score, language='en'):
    badges = []
    if score >= 21:
        badges.append({
            'name': trans('badge_financial_guru', default='Financial Guru', lang=language),
            'color_class': 'bg-primary',
            'description': trans('badge_financial_guru_desc', default='Awarded for excellent financial planning.', lang=language)
        })
    elif score >= 13:
        badges.append({
            'name': trans('badge_savings_star', default='Savings Star', lang=language),
            'color_class': 'bg-success',
            'description': trans('badge_savings_star_desc', default='Recognized for consistent saving habits.', lang=language)
        })
    badges.append({
        'name': trans('badge_first_quiz', default='First Quiz Completed', lang=language),
        'color_class': 'bg-info',
        'description': trans('badge_first_quiz_desc', default='Completed your first financial quiz.', lang=language)
    })
    return badges

# Routes
@quiz_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.modified = True
        logger.debug(f"New session created with sid: {session['sid']}")
    language = session.get('language', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')
    form = QuizStep1Form(language=language, formdata=request.form if request.method == 'POST' else None)
    
    if request.method == 'POST' and form.validate_on_submit():
        session['quiz_data'] = {
            'first_name': form.first_name.data,
            'email': form.email.data,
            'language': form.language.data or 'en',
            'send_email': form.send_email.data
        }
        session['language'] = form.language.data or 'en'
        session.modified = True
        logger.info(f"Quiz step 1 validated successfully, session updated: {session['quiz_data']}")
        return redirect(url_for('quiz.step2a', course_id=course_id))
    elif form.errors:
        logger.error(f"Form validation failed: {form.errors}")
        flash(trans('quiz_form_errors', default='Please correct the errors in the form.'), 'danger')

    return render_template(
        'quiz_step1.html',
        form=form,
        course_id=course_id,
        language=language,
        total_steps=3
    )

@quiz_bp.route('/step2a', methods=['GET', 'POST'])
def step2a():
    if 'sid' not in session or 'quiz_data' not in session:
        flash(trans('session_expired', default='Session expired. Please start again.'), 'danger')
        return redirect(url_for('quiz.step1', course_id=request.args.get('course_id', 'financial_quiz')))
    
    language = session['quiz_data'].get('language', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')
    form = QuizStep2aForm(language=language, formdata=request.form if request.method == 'POST' else None)
    
    # Preprocessed questions for template (hardcoded to match form fields)
    questions = [
        {'id': 'question_1', 'text_key': 'quiz_track_expenses_label', 'text': 'Do you track your expenses regularly?', 'tooltip': 'quiz_track_expenses_tooltip'},
        {'id': 'question_2', 'text_key': 'quiz_save_regularly_label', 'text': 'Do you save a portion of your income regularly?', 'tooltip': 'quiz_save_regularly_tooltip'},
        {'id': 'question_3', 'text_key': 'quiz_budget_monthly_label', 'text': 'Do you set a monthly budget?', 'tooltip': 'quiz_budget_monthly_tooltip'},
        {'id': 'question_4', 'text_key': 'quiz_emergency_fund_label', 'text': 'Do you have an emergency fund?', 'tooltip': 'quiz_emergency_fund_tooltip'},
        {'id': 'question_5', 'text_key': 'quiz_invest_regularly_label', 'text': 'Do you invest your money regularly?', 'tooltip': 'quiz_invest_regularly_tooltip'},
    ]
    
    if request.method == 'POST':
        if form.back.data:
            return redirect(url_for('quiz.step1', course_id=course_id))
        if form.validate_on_submit():
            session['quiz_data'].update({
                'question_1': form.question_1.data,
                'question_2': form.question_2.data,
                'question_3': form.question_3.data,
                'question_4': form.question_4.data,
                'question_5': form.question_5.data,
            })
            session.modified = True
            logger.info(f"Quiz step 2a validated successfully, session updated: {session['quiz_data']}")
            return redirect(url_for('quiz.step2b', course_id=course_id))
        else:
            logger.error(f"Form validation failed in step2a: {form.errors}")
            flash(trans('quiz_form_errors', default='Please correct the errors in the form.'), 'danger')
    
    # Pre-fill form with session data if available
    for q in questions:
        if q['id'] in session.get('quiz_data', {}):
            getattr(form, q['id']).data = session['quiz_data'][q['id']]
    
    return render_template(
        'quiz_step.html',
        form=form,
        questions=questions,
        course_id=course_id,
        language=language,
        step_num=2,
        total_steps=3
    )

@quiz_bp.route('/step2b', methods=['GET', 'POST'])
def step2b():
    if 'sid' not in session or 'quiz_data' not in session:
        flash(trans('session_expired', default='Session expired. Please start again.'), 'danger')
        return redirect(url_for('quiz.step1', course_id=request.args.get('course_id', 'financial_quiz')))
    
    language = session['quiz_data'].get('language', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')
    form = QuizStep2bForm(language=language, formdata=request.form if request.method == 'POST' else None)
    
    # Preprocessed questions for template (hardcoded to match form fields)
    questions = [
        {'id': 'question_6', 'text_key': 'quiz_spend_impulse_label', 'text': 'Do you often spend money on impulse?', 'tooltip': 'quiz_spend_impulse_tooltip'},
        {'id': 'question_7', 'text_key': 'quiz_financial_goals_label', 'text': 'Do you set financial goals?', 'tooltip': 'quiz_financial_goals_tooltip'},
        {'id': 'question_8', 'text_key': 'quiz_review_spending_label', 'text': 'Do you review your spending habits regularly?', 'tooltip': 'quiz_review_spending_tooltip'},
        {'id': 'question_9', 'text_key': 'quiz_multiple_income_label', 'text': 'Do you have multiple sources of income?', 'tooltip': 'quiz_multiple_income_tooltip'},
        {'id': 'question_10', 'text_key': 'quiz_retirement_plan_label', 'text': 'Do you have a retirement savings plan?', 'tooltip': 'quiz_retirement_plan_tooltip'},
    ]
    
    if request.method == 'POST':
        if form.back.data:
            return redirect(url_for('quiz.step2a', course_id=course_id))
        if form.validate_on_submit():
            session['quiz_data'].update({
                'question_6': form.question_6.data,
                'question_7': form.question_7.data,
                'question_8': form.question_8.data,
                'question_9': form.question_9.data,
                'question_10': form.question_10.data,
            })
            session.modified = True
            logger.info(f"Quiz step 2b validated successfully, session updated: {session['quiz_data']}")
            
            # Calculate results
            answers = [session['quiz_data'].get(f'question_{i}') for i in range(1, 11)]
            score = calculate_score(answers)
            personality = assign_personality(score, language)
            badges = assign_badges(score, language)
            
            # Store results in session
            session['quiz_results'] = {
                'first_name': session['quiz_data'].get('first_name', ''),
                'personality': personality['name'],
                'score': score,
                'badges': badges,
                'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
                'insights': personality['insights'],
                'tips': personality['tips']
            }
            session.modified = True
            
            return redirect(url_for('quiz.results', course_id=course_id))
        else:
            logger.error(f"Form validation failed in step2b: {form.errors}")
            flash(trans('quiz_form_errors', default='Please correct the errors in the form.'), 'danger')
    
    # Pre-fill form with session data if available
    for q in questions:
        if q['id'] in session.get('quiz_data', {}):
            getattr(form, q['id']).data = session['quiz_data'][q['id']]
    
    return render_template(
        'quiz_step.html',
        form=form,
        questions=questions,
        course_id=course_id,
        language=language,
        step_num=3,
        total_steps=3
    )

@quiz_bp.route('/results', methods=['GET'])
def results():
    if 'sid' not in session or 'quiz_results' not in session:
        flash(trans('session_expired', default='Session expired. Please start again.'), 'danger')
        return redirect(url_for('quiz.step1', course_id=request.args.get('course_id', 'financial_quiz')))
    
    language = session.get('language', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')
    results = session['quiz_results']
    
    # Clear session data
    session.pop('quiz_data', None)
    session.pop('quiz_results', None)
    session.modified = True
    
    return render_template(
        'quiz_results.html',
        latest_record=results,
        insights=results.get('insights', []),
        tips=results.get('tips', []),
        course_id=course_id,
        language=language
    )
