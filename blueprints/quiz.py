from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import Email, Optional
from json_store import JsonStorageManager
from mailersend_email import send_email
import logging
import uuid

# Configure logging
logging.basicConfig(filename='data/storage.txt', level=logging.DEBUG)

quiz_bp = Blueprint('quiz', __name__)
quiz_storage = JsonStorageManager('data/quiz_data.json')

# Form for quiz step 3
class QuizStep3Form(FlaskForm):
    email = StringField('Email', validators=[Optional(), Email()])
    send_email = SelectField('Send Email', choices=[('on', 'Yes'), ('off', 'No')])
    submit = SubmitField('Submit')

@quiz_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    """Handle quiz step 1 form."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    if request.method == 'POST':
        try:
            session['quiz_step1'] = request.form.to_dict()
            return redirect(url_for('quiz.step2'))
        except Exception as e:
            logging.exception(f"Error in quiz.step1: {str(e)}")
            flash("Error processing step 1.")
            return redirect(url_for('quiz.step1'))
    return render_template('quiz_step1.html')

@quiz_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    """Handle quiz step 2 form."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    if request.method == 'POST':
        try:
            session['quiz_step2'] = request.form.to_dict()
            return redirect(url_for('quiz.step3'))
        except Exception as e:
            logging.exception(f"Error in quiz.step2: {str(e)}")
            flash("Error processing step 2.")
            return redirect(url_for('quiz.step2'))
    return render_template('quiz_step2.html')

@quiz_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    """Handle quiz step 3 form and calculate results."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = QuizStep3Form()
    if request.method == 'POST' and form.validate_on_submit():
        try:
            email = form.email.data
            send_email_flag = form.send_email.data == 'on'
            quiz_data = {**session.get('quiz_step1', {}), **session.get('quiz_step2', {})}
            score = sum(1 for k, v in quiz_data.items() if v in ['always', 'yes', 'often'])
            personality = "Planner" if score >= 8 else "Saver" if score >= 6 else "Spender"
            record = {
                "data": {
                    "personality": personality,
                    "score": score,
                    "answers": quiz_data
                }
            }
            quiz_storage.append(record, user_email=email, session_id=session['sid'])
            if send_email_flag and email:
                send_email(
                    to_email=email,
                    subject="Financial Personality Quiz Results",
                    template_name="quiz_email.html",
                    data={"personality": personality, "score": score},
                    lang=session.get('lang', 'en')
                )
            session.pop('quiz_step1', None)
            session.pop('quiz_step2', None)
            flash("Quiz completed successfully.")
            return redirect(url_for('quiz.results'))
        except Exception as e:
            logging.exception(f"Error in quiz.step3: {str(e)}")
            flash("Error processing quiz results.")
            return redirect(url_for('quiz.step3'))
    return render_template('quiz_step3.html', form=form)

@quiz_bp.route('/results')
def results():
    """Display quiz results."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    try:
        user_data = quiz_storage.filter_by_session(session['sid'])
        return render_template('quiz_results.html', data=user_data[-1] if user_data else {})
    except Exception as e:
        logging.exception(f"Error in quiz.results: {str(e)}")
        flash("Error loading quiz results.")
        return render_template('quiz_results.html', data={})
