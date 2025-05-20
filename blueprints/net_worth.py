from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Email
from json_store import JsonStorage
from mailersend_email import send_email
from translations import trans
import logging
import uuid

# Configure logging
logging.basicConfig(filename='data/storage.txt', level=logging.DEBUG)

net_worth_bp = Blueprint('net_worth', __name__)
net_worth_storage = JsonStorage('data/networth.json')

# Forms for net worth steps
class Step1Form(FlaskForm):
    cash = FloatField('Cash', validators=[DataRequired(), NumberRange(min=0)])
    investments = FloatField('Investments', validators=[DataRequired(), NumberRange(min=0)])
    property = FloatField('Property', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Next')

class Step2Form(FlaskForm):
    loans = FloatField('Loans', validators=[DataRequired(), NumberRange(min=0)])
    credit_cards = FloatField('Credit Cards', validators=[DataRequired(), NumberRange(min=0)])
    email = StringField('Email', validators=[Optional(), Email()])
    send_email = BooleanField('Send Email')
    submit = SubmitField('Submit')

@net_worth_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    """Handle net worth step 1 form."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step1Form()
    t = trans('t')
    if request.method == 'POST' and form.validate_on_submit():
        try:
            session['net_worth_step1'] = form.data
            return redirect(url_for('net_worth.step2'))
        except Exception as e:
            logging.exception(f"Error in net_worth.step1: {str(e)}")
            flash(trans("Error processing step 1."), "danger")
            return redirect(url_for('net_worth.step1'))
    return render_template('net_worth_step1.html', form=form, t=t)

@net_worth_bp.route('/step2', methods=['GET', 'POST'])
def step2():
    """Handle net worth step 2 form and calculate net worth."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = Step2Form()
    t = trans('t')
    if request.method == 'POST' and form.validate_on_submit():
        try:
            data = form.data
            step1_data = session.get('net_worth_step1', {})
            assets = sum([
                step1_data.get('cash', 0),
                step1_data.get('investments', 0),
                step1_data.get('property', 0)
            ])
            liabilities = sum([
                data.get('loans', 0),
                data.get('credit_cards', 0)
            ])
            net_worth = assets - liabilities
            record = {
                "data": {
                    "cash": step1_data.get('cash', 0),
                    "investments": step1_data.get('investments', 0),
                    "property": step1_data.get('property', 0),
                    "loans": data.get('loans', 0),
                    "credit_cards": data.get('credit_cards', 0),
                    "total_assets": assets,
                    "total_liabilities": liabilities,
                    "net_worth": net_worth
                }
            }
            email = data.get('email')
            send_email_flag = data.get('send_email', False)
            net_worth_storage.append(record, user_email=email, session_id=session['sid'])
            if send_email_flag and email:
                send_email(
                    to_email=email,
                    subject=trans("Net Worth Summary"),
                    template_name="net_worth_email.html",
                    data=record["data"],
                    lang=session.get('lang', 'en')
                )
            session.pop('net_worth_step1', None)
            flash(trans("Net worth calculation completed."), "success")
            return redirect(url_for('net_worth.dashboard'))
        except Exception as e:
            logging.exception(f"Error in net_worth.step2: {str(e)}")
            flash(trans("Error processing net worth."), "danger")
            return redirect(url_for('net_worth.step2'))
    return render_template('net_worth_step2.html', form=form, t=t)

@net_worth_bp.route('/dashboard')
def dashboard():
    """Display net worth dashboard."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    t = trans('t')
    try:
        user_data = net_worth_storage.filter_by_session(session['sid'])
        return render_template('net_worth_dashboard.html', data=user_data[-1]["data"] if user_data else {}, t=t)
    except Exception as e:
        logging.exception(f"Error in net_worth.dashboard: {str(e)}")
        flash(trans("Error loading dashboard."), "danger")
        return render_template('net_worth_dashboard.html', data={}, t=t)
