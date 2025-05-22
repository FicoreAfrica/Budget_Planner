from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app
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

quiz_bp = Blueprint('quiz', __name__)

QUESTION_POOL = [
    {
        'key': 'track_expenses',
        'label': trans('question_track_expenses'),
        'tooltip': trans('tooltip_track_expenses')
    },
    {
        'key': 'save_regularly',
        'label': trans('question_save_regularly'),
        'tooltip': trans('tooltip_save_regularly')
    },
    {
        'key': 'spend_non_essentials',
        'label': trans('question_spend_non_essentials'),
        'tooltip': trans('tooltip_spend_non_essentials')
    },
    {
        'key': 'plan_expenses',
        'label': trans('question_plan_expenses'),
        'tooltip': trans('tooltip_plan_expenses')
    },
    {
        'key': 'impulse_purchases',
        'label': trans('question_impulse_purchases'),
        'tooltip': trans('tooltip_impulse_purchases')
    },
    {
        'key': 'use_budgeting_tools',
        'label': trans('question_use_budgeting_tools'),
        'tooltip': trans('tooltip_use_budgeting_tools')
    },
    {
        'key': 'invest_money',
        'label': trans('question_invest_money'),
        'tooltip': trans('tooltip_invest_money')
    },
    {
        'key': 'emergency_fund',
        'label': trans('question_emergency_fund'),
        'tooltip': trans('tooltip_emergency_fund')
    },
    {
        'key': 'set_financial_goals',
        'label': trans('question_set_financial_goals'),
        'tooltip': trans('tooltip_set_financial_goals')
    },
    {
        'key': 'seek_financial_advice',
        'label': trans('question_seek_financial_advice'),
        'tooltip': trans('tooltip_seek_financial_advice')
    },
    {
        'key': 'use_mobile_money',
        'label': trans('question_use_mobile_money'),
        'tooltip': trans('tooltip_use_mobile_money')
    },
    {
        'key': 'pay_bills_early',
        'label': trans('question_pay_bills_early'),
        'tooltip': trans('tooltip_pay_bills_early')
    },
    {
        'key': 'learn_financial_skills',
        'label': trans('question_learn_financial_skills'),
        'tooltip': trans('tooltip_learn_financial_skills')
    },
    {
        'key': 'avoid_debt',
        'label': trans('question_avoid_debt'),
        'tooltip': trans('tooltip_avoid_debt')
    },
    {
        'key': 'diversify_income',
        'label': trans('question_diversify_income'),
        'tooltip': trans('tooltip_diversify_income')
    }
]

class Step1Form(FlaskForm):
    first_name = StringField(trans('first_name'), validators=[DataRequired(message=trans('first_name_required'))])
    email = StringField(trans('email'), validators=[Optional(), Email(message=trans('email_invalid'))])
    send_email = BooleanField(trans('send_email'))
    submit = SubmitField(trans('start_quiz'))

class Step2Form(FlaskForm):
    def __init__(self, questions, *args, **kwargs):
        super(Step2Form, self).__init__(*args, **kwargs)
        for q in questions:
            setattr(self, q['key'], SelectField(
                q['label'],
                choices=[
                    ('', trans('select_answer')),
                    ('always', trans('always')),
                    ('often', trans('often')),
                    ('sometimes', trans('sometimes')),
                    ('never', trans('never'))
                ],
                validators=[DataRequired(message=trans('answer_required', question=q['label']))]
            ))
    submit = SubmitField(trans('submit_answers'))

@quiz_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = Step1Form()
    course_id = request.args.get('course_id', 'financial_quiz')
    try:
        if request.method == 'POST' and form.validate_on_submit():
            session['quiz_step1'] = form.data
            current_app.logger.debug(f"Quiz step1 form data: {form.data}")
            progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
            progress = progress_storage.filter_by_session(session['sid'])
            course_progress = next((p for p in progress if p['data']['course_id'] == course_id), None)
            if not course_progress:
                progress_data = {
                    'course_id': course_id,
                    'completed_lessons': [0],
                    'progress_percentage': (1/3) * 100,
                    'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                progress_storage.append(progress_data, session_id=session['sid'])
            else:
                if 0 not in course_progress['data']['completed_lessons']:
                    course_progress['data']['completed_lessons'].append(0)
                    course_progress['data']['progress_percentage'] = (len(course_progress['data']['completed_lessons']) / 3) * 100
                    course_progress['data']['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    progress_storage.update_by_id(course_progress['id'], course_progress['data'])
            current_app.logger.info(f"Quiz lesson 0 (step1) completed for course {course_id} by session {session['sid']}")
            return redirect(url_for('quiz.step2', course_id=course_id))
        return render_template('quiz_step1.html', form=form, trans=trans, lang=lang, course_id=course_id)
    except Exception as e:
        current_app.logger.exception(f"Error in quiz.step1: {str(e)}")
        flash(trans("error_personal_info", lang=lang), "danger")
        return render_template('quiz_step1.html', form=form, trans=trans, lang=lang, course_id=course_id)

@quiz_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')
    selected_questions = random.sample(QUESTION_POOL, 10)
    form = Step2Form(questions=selected_questions)
    try:
        if request.method == 'POST' and form.validate_on_submit():
            answers = {q['key']: getattr(form, q['key']).data for q in selected_questions}
            score = sum(
                3 if v == 'always' else 2 if v == 'often' else 1 if v == 'sometimes' else 0
                for v in answers.values()
            )
            personality = (
                trans("personality_planner", lang=lang) if score >= 24 else
                trans("personality_saver", lang=lang) if score >= 18 else
                trans("personality_balanced", lang=lang) if score >= 12 else
                trans("personality_spender", lang=lang)
            )
            badges = []
            if score >= 24:
                badges.append(trans("badge_financial_guru", lang=lang))
            if score >= 18:
                badges.append(trans("badge_savings_star", lang=lang))
            if answers.get('avoid_debt') in ['always', 'often']:
                badges.append(trans("badge_debt_dodger", lang=lang))
            if answers.get('set_financial_goals') in ['always', 'often']:
                badges.append(trans("badge_goal_setter", lang=lang))
            
            quiz_storage = current_app.config['STORAGE_MANAGERS']['quiz']
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
            
            if send_email_flag and email:
                send_email(
                    to_email=email,
                    subject=trans("quiz_results_subject", lang=lang),
                    template_name="quiz_email.html",
                    data={
                        "first_name": record["data"]["first_name"],
                        "score": score,
                        "personality": personality,
                        "badges": badges,
                        "created_at": record["data"]["created_at"],
                        "cta_url": url_for('quiz.results', _external=True)
                    },
                    lang=lang
                )
            
            progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
            progress = progress_storage.filter_by_session(session['sid'])
            course_progress = next((p for p in progress if p['data']['course_id'] == course_id), None)
            if not course_progress:
                progress_data = {
                    'course_id': course_id,
                    'completed_lessons': [0, 1],
                    'progress_percentage': (2/3) * 100,
                    'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                progress_storage.append(progress_data, session_id=session['sid'])
            else:
                if 1 not in course_progress['data']['completed_lessons']:
                    course_progress['data']['completed_lessons'].append(1)
                    course_progress['data']['progress_percentage'] = (len(course_progress['data']['completed_lessons']) / 3) * 100
                    course_progress['data']['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    progress_storage.update_by_id(course_progress['id'], course_progress['data'])
            
            current_app.logger.info(f"Quiz lesson 1 (step2) completed for course {course_id} by session {session['sid']}")
            session.pop('quiz_step1', None)
            flash(trans("quiz_completed_success", lang=lang), "success")
            return redirect(url_for('quiz.results', course_id=course_id))
        return render_template('quiz_step2.html', form=form, questions=selected_questions, trans=trans, lang=lang, course_id=course_id)
    except Exception as e:
        current_app.logger.exception(f"Error in quiz.step2: {str(e)}")
        flash(trans("error_quiz_answers", lang=lang), "danger")
        return render_template('quiz_step2.html', form=form, questions=selected_questions, trans=trans, lang=lang, course_id=course_id)

@quiz_bp.route('/results', methods=['GET', 'POST'])
def results():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')
    try:
        quiz_storage = current_app.config['STORAGE_MANAGERS']['quiz']
        user_data = quiz_storage.filter_by_session(session['sid'])
        records = [(record["id"], record["data"]) for record in user_data]
        latest_record = records[-1][1] if records else {}
        
        insights = []
        tips = [
            trans("tip_automate_savings", lang=lang),
            trans("tip_ajo_savings", lang=lang),
            trans("tip_learn_skills", lang=lang),
            trans("tip_track_expenses", lang=lang)
        ]
        if latest_record:
            if latest_record.get('personality') == trans("personality_spender", lang=lang):
                insights.append(trans("insight_high_spending", lang=lang))
                tips.append(trans("tip_use_budgeting_app", lang=lang))
            if latest_record.get('score', 0) < 18:
                insights.append(trans("insight_low_discipline", lang=lang))
            if latest_record.get('answers', {}).get('emergency_fund') in ['never', 'sometimes']:
                insights.append(trans("insight_no_emergency_fund", lang=lang))
                tips.append(trans("tip_emergency_fund", lang=lang))
            if latest_record.get('answers', {}).get('invest_money') in ['always', 'often']:
                insights.append(trans("insight_good_investment", lang=lang))
        
        return render_template(
            'quiz_results.html',
            records=records,
            latest_record=latest_record,
            insights=insights,
            tips=tips,
            trans=trans,
            lang=lang,
            course_id=course_id
        )
    except Exception as e:
        current_app.logger.exception(f"Error in quiz.results: {str(e)}")
        flash(trans("error_loading_results", lang=lang), "danger")
        return render_template(
            'quiz_results.html',
            records=[],
            latest_record={},
            insights=[],
            tips=[
                trans("tip_automate_savings", lang=lang),
                trans("tip_ajo_savings", lang=lang),
                trans("tip_learn_skills", lang=lang),
                trans("tip_track_expenses", lang=lang)
            ],
            trans=trans,
            lang=lang,
            course_id=course_id
        )
