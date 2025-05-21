from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Optional, Email
from json_store import JsonStorage
from mailersend_email import send_email
from translations import trans
from datetime import datetime
import logging
import uuid
import random

# Configure logging
logging.basicConfig(filename='data/storage.txt', level=logging.DEBUG)

quiz_bp = Blueprint('quiz', __name__)
quiz_storage = JsonStorage('data/quiz_data.json')

# Question pool with Nigeria-contextual questions
QUESTION_POOL = [
    {
        'key': 'track_expenses',
        'label': 'Do you track your expenses regularly?',
        'tooltip': 'E.g., recording daily spending on food, transport, or data subscriptions using apps like Flowdiary or notebooks.'
    },
    {
        'key': 'save_regularly',
        'label': 'Do you save money regularly?',
        'tooltip': 'E.g., contributing to Ajo/Esusu/Adashe or using savings platforms like PiggyVest or Cowrywise.'
    },
    {
        'key': 'spend_non_essentials',
        'label': 'Do you spend on non-essential items?',
        'tooltip': 'E.g., buying luxury clothing, gadgets, or outings to restaurants or events.'
    },
    {
        'key': 'plan_expenses',
        'label': 'Do you plan your expenses before spending?',
        'tooltip': 'E.g., budgeting for rent, food, or dependents’ needs before making purchases.'
    },
    {
        'key': 'impulse_purchases',
        'label': 'Do you make impulse purchases?',
        'tooltip': 'E.g., buying items like airtime or snacks without prior planning.'
    },
    {
        'key': 'use_budgeting_tools',
        'label': 'Do you use budgeting tools or apps?',
        'tooltip': 'E.g., apps like PiggyVest, Moniepoint, or spreadsheets for tracking income and expenses.'
    },
    {
        'key': 'invest_money',
        'label': 'Do you invest your money?',
        'tooltip': 'E.g., investing in farming, real estate, stocks, or cooperative schemes.'
    },
    {
        'key': 'emergency_fund',
        'label': 'Do you have an emergency fund?',
        'tooltip': 'E.g., savings set aside for unexpected expenses like medical bills or vehicle repairs.'
    },
    {
        'key': 'set_financial_goals',
        'label': 'Do you set financial goals?',
        'tooltip': 'E.g., saving for a house, business startup, or children’s education.'
    },
    {
        'key': 'seek_financial_advice',
        'label': 'Do you seek financial advice?',
        'tooltip': 'E.g., consulting family, friends, or financial advisors, or learning from platforms like Coursera or Flowdiary.'
    },
    {
        'key': 'use_mobile_money',
        'label': 'Do you use mobile money apps for transactions?',
        'tooltip': 'E.g., paying bills or transferring money via OPay, Moniepoint, or PalmPay.'
    },
    {
        'key': 'pay_bills_early',
        'label': 'Do you pay your bills on time?',
        'tooltip': 'E.g., settling electricity, rent, or data subscriptions before due dates.'
    },
    {
        'key': 'learn_financial_skills',
        'label': 'Do you actively learn financial skills?',
        'tooltip': 'E.g., taking courses on budgeting or investing via Flowdiary, Coursera, or local workshops.'
    },
    {
        'key': 'avoid_debt',
        'label': 'Do you avoid taking loans or debt?',
        'tooltip': 'E.g., minimizing borrowings from friends, banks, or mobile money apps like OPay.'
    },
    {
        'key': 'diversify_income',
        'label': 'Do you have multiple sources of income?',
        'tooltip': 'E.g., combining salary with side businesses, farming, or gig work.'
    }
]

# Form for Step 1 (Personal Info)
class Step1Form(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(message='First name is required')])
    email = StringField('Email', validators=[Optional(), Email(message='Valid email is required')])
    send_email = BooleanField('Send Email')
    submit = SubmitField('Start Quiz')

# Form for Step 2 (Quiz Questions)
class Step2Form(FlaskForm):
    def __init__(self, questions, *args, **kwargs):
        super(Step2Form, self).__init__(*args, **kwargs)
        for q in questions:
            setattr(self, q['key'], SelectField(
                q['label'],
                choices=[('', 'Select your answer'), ('always', 'Always'), ('often', 'Often'), ('sometimes', 'Sometimes'), ('never', 'Never')],
                validators=[DataRequired(message=f"{q['label']} is required")]
            ))
    submit = SubmitField('Submit Answers')

# Route for Step 1
@quiz_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    """Handle quiz step 1 form (personal info)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step1Form()
    t = trans('t')
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['quiz_step1'] = form.data
            logging.debug(f"Quiz step1 form data: {form.data}")
            return redirect(url_for('quiz.step2'))
        return render_template('quiz_step1.html', form=form, t=t)
    except Exception as e:
        logging.exception(f"Error in quiz.step1: {str(e)}")
        flash(t("Error processing personal information."), "danger")
        return render_template('quiz_step1.html', form=form, t=t)

# Route for Step 2
@quiz_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    """Handle quiz step 2 form (quiz questions)."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    t = trans('t')
    # Select 10 random questions
    selected_questions = random.sample(QUESTION_POOL, 10)
    form = Step2Form(questions=selected_questions)
    try:
        if request.method == 'POST' and form.validate_on_submit():
            # Calculate score
            answers = {q['key']: getattr(form, q['key']).data for q in selected_questions}
            score = sum(
                3 if v == 'always' else 2 if v == 'often' else 1 if v == 'sometimes' else 0
                for v in answers.values()
            )
            # Assign personality
            personality = (
                "Planner" if score >= 24 else
                "Saver" if score >= 18 else
                "Balanced" if score >= 12 else
                "Spender"
            )
            # Assign badges
            badges = []
            if score >= 24:
                badges.append("Financial Guru")
            if score >= 18:
                badges.append("Savings Star")
            if answers.get('avoid_debt') in ['always', 'often']:
                badges.append("Debt Dodger")
            if answers.get('set_financial_goals') in ['always', 'often']:
                badges.append("Goal Setter")
            
            # Store results
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
            
            # Send email if requested
            if send_email_flag and email:
                send_email(
                    to_email=email,
                    subject=t("Your Financial Personality Quiz Results"),
                    template_name="quiz_email.html",
                    data={
                        "first_name": record["data"]["first_name"],
                        "score": score,
                        "personality": personality,
                        "badges": badges,
                        "created_at": record["data"]["created_at"],
                        "cta_url": url_for('quiz.results', _external=True)
                    },
                    lang=session.get('lang', 'en')
                )
            
            # Clear session
            session.pop('quiz_step1', None)
            flash(t("Quiz completed successfully."), "success")
            return redirect(url_for('quiz.results'))
        return render_template('quiz_step2.html', form=form, questions=selected_questions, t=t)
    except Exception as e:
        logging.exception(f"Error in quiz.step2: {str(e)}")
        flash(t("Error processing quiz answers."), "danger")
        return render_template('quiz_step2.html', form=form, questions=selected_questions, t=t)

# Route for Results
@quiz_bp.route('/results', methods=['GET', 'POST'])
def results():
    """Display quiz results."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    t = trans('t')
    try:
        user_data = quiz_storage.filter_by_session(session['sid'])
        records = [(record["id"], record["data"]) for record in user_data]
        latest_record = records[-1][1] if records else {}
        
        # Generate insights and tips
        insights = []
        tips = [
            t("Use apps like PiggyVest or Cowrywise to automate savings."),
            t("Join Ajo/Esusu/Adashe groups for disciplined saving habits."),
            t("Learn financial skills through Flowdiary or Coursera courses."),
            t("Track expenses weekly using Moniepoint or Flowdiary.")
        ]
        if latest_record:
            if latest_record.get('personality') == "Spender":
                insights.append(t("High spending habits detected. Try budgeting with PiggyVest to control expenses."))
            if latest_record.get('score', 0) < 18:
                insights.append(t("Low financial discipline. Set small goals, like saving ₦10,000 monthly."))
            if latest_record.get('answers', {}).get('emergency_fund') in ['never', 'sometimes']:
                insights.append(t("No emergency fund. Start saving with Cowrywise for unexpected expenses."))
            if latest_record.get('answers', {}).get('invest_money') in ['always', 'often']:
                insights.append(t("Great investment habits! Explore cooperative schemes or real estate."))
        
        return render_template(
            'quiz_results.html',
            records=records,
            latest_record=latest_record,
            insights=insights,
            tips=tips,
            t=t
        )
    except Exception as e:
        logging.exception(f"Error in quiz.results: {str(e)}")
        flash(t("Error loading quiz results."), "danger")
        return render_template(
            'quiz_results.html',
            records=[],
            latest_record={},
            insights=[],
            tips=[],
            t=t
        )
