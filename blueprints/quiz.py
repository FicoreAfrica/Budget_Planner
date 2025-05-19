from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from json_store import JsonStorageManager
from mailersend_email import send_email

quiz_bp = Blueprint('quiz', __name__)
quiz_storage = JsonStorageManager('data/quiz_data.json')

@quiz_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    if request.method == 'POST':
        session['quiz_step1'] = request.form.to_dict()
        return redirect(url_for('quiz.step2'))
    return render_template('quiz_step1.html')

@quiz_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    if request.method == 'POST':
        session['quiz_step2'] = request.form.to_dict()
        return redirect(url_for('quiz.step3'))
    return render_template('quiz_step2.html')

@quiz_bp.route('/step3', methods=['GET', 'POST'])
def step3():
    if request.method == 'POST':
        email = request.form.get('email')
        send_email_flag = request.form.get('send_email') == 'on'
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
        quiz_storage.append(record, user_email=email, session_id=session.sid)
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
        return redirect(url_for('quiz.results'))
    return render_template('quiz_step3.html')

@quiz_bp.route('/results')
def results():
    user_data = quiz_storage.filter_by_session(session.sid)
    return render_template('quiz_results.html', data=user_data[-1] if user_data else {})
