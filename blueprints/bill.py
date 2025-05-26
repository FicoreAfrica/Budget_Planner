from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Email
from json_store import JsonStorage
from mailersend_email import send_email
from datetime import datetime, date, timedelta
import logging
import uuid
try:
    from app import trans
except ImportError:
    def trans(key, lang=None):
        return key

# Configure logging
logging.basicConfig(filename='data/storage.txt', level=logging.DEBUG)

bill_bp = Blueprint('bill', __name__, url_prefix='/bill')

def init_bill_storage(app):
    """Initialize bill_storage within app context."""
    with app.app_context():
        return JsonStorage('data/bills.json', logger_instance=app.logger)

def strip_commas(value):
    if isinstance(value, str):
        return value.replace(',', '')
    return value

class BillForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(message=trans('bill_first_name_required'))])
    email = StringField('Email', validators=[DataRequired(message=trans('bill_email_required')), Email()])
    bill_name = StringField('Bill Name', validators=[DataRequired(message=trans('bill_bill_name_required'))])
    amount = FloatField('Amount', validators=[DataRequired(message=trans('bill_amount_required')), NumberRange(min=0, max=10000000000)], filters=[strip_commas])
    due_date = StringField('Due Date (YYYY-MM-DD)', validators=[DataRequired(message=trans('bill_due_date_required'))])
    frequency = SelectField('Frequency', choices=[
        ('one-time', trans('bill_frequency_one_time')),
        ('weekly', trans('bill_frequency_weekly')),
        ('monthly', trans('bill_frequency_monthly')),
        ('quarterly', trans('bill_frequency_quarterly'))
    ], default='one-time')
    category = SelectField('Category', choices=[
        ('utilities', trans('bill_category_utilities')),
        ('rent', trans('bill_category_rent')),
        ('data_internet', trans('bill_category_data_internet')),
        ('ajo_esusu_adashe', trans('bill_category_ajo_esusu_adashe')),
        ('food', trans('bill_category_food')),
        ('transport', trans('bill_category_transport')),
        ('clothing', trans('bill_category_clothing')),
        ('education', trans('bill_category_education')),
        ('healthcare', trans('bill_category_healthcare')),
        ('entertainment', trans('bill_category_entertainment')),
        ('airtime', trans('bill_category_airtime')),
        ('school_fees', trans('bill_category_school_fees')),
        ('savings_investments', trans('bill_category_savings_investments')),
        ('other', trans('bill_category_other'))
    ], validators=[DataRequired(message=trans('bill_category_required'))])
    send_email = BooleanField(trans('bill_send_email_reminders'))
    status = SelectField('Status', choices=[
        ('unpaid', trans('bill_status_unpaid')),
        ('paid', trans('bill_status_paid')),
        ('pending', trans('bill_status_pending')),
        ('overdue', trans('bill_status_overdue'))
    ], default='unpaid')
    submit = SubmitField(trans('bill_save_bill'))

@bill_bp.route('/form', methods=['GET', 'POST'])
def form():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    form = BillForm()
    try:
        if request.method == 'POST' and form.validate_on_submit():
            try:
                data = form.data
                try:
                    due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
                    if due_date < date.today():
                        flash(trans("bill_due_date_future_validation"), "danger")
                        current_app.logger.error("Due date in the past in bill.form")
                        return redirect(url_for('bill.form'))
                except ValueError:
                    flash(trans("bill_due_date_format_invalid"), "danger")
                    current_app.logger.error("Invalid due date format in bill.form")
                    return redirect(url_for('bill.form'))

                status = data['status']
                if status not in ['paid', 'pending'] and due_date < date.today():
                    status = 'overdue'

                record = {
                    "data": {
                        "first_name": data['first_name'],
                        "bill_name": data['bill_name'],
                        "amount": data['amount'],
                        "due_date": data['due_date'],
                        "frequency": data['frequency'],
                        "category": data['category'],
                        "status": status
                    }
                }
                bill_storage = current_app.config['STORAGE_MANAGERS']['bills']
                bill_storage.append(record, user_email=data['email'], session_id=session['sid'])
                if data['send_email'] and data['email']:
                    send_email(
                        to_email=data['email'],
                        subject=trans("bill_payment_reminder"),
                        template_name="bill_reminder.html",
                        data={
                            "first_name": data['first_name'],
                            "bill_name": data['bill_name'],
                            "amount": data['amount'],
                            "due_date": data['due_date'],
                            "category": trans(f"bill_category_{data['category']}"),
                            "status": trans(f"bill_status_{status}"),
                            "cta_url": url_for('bill.dashboard', _external=True)
                        },
                        lang=lang
                    )
                flash(trans("bill_bill_added_success"), "success")
                return redirect(url_for('bill.view_edit'))
            except Exception as e:
                current_app.logger.exception(f"Error processing bill form: {str(e)}")
                flash(trans("bill_bill_add_error"), "danger")
                return redirect(url_for('bill.form'))
        return render_template('bill_form.html', form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Template rendering error in bill.form: {str(e)}")
        flash(trans("bill_bill_form_load_error"), "danger")
        return redirect(url_for('index'))

@bill_bp.route('/dashboard')
def dashboard():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    try:
        bill_storage = current_app.config['STORAGE_MANAGERS']['bills']
        user_data = bill_storage.filter_by_session(session['sid'])
        bills = [record["data"] for record in user_data]
        paid_count = sum(1 for bill in bills if bill['status'] == 'paid')
        unpaid_count = sum(1 for bill in bills if bill['status'] == 'unpaid')
        overdue_count = sum(1 for bill in bills if bill['status'] == 'overdue')
        pending_count = sum(1 for bill in bills if bill['status'] == 'pending')
        total_paid = sum(bill['amount'] for bill in bills if bill['status'] == 'paid')
        total_unpaid = sum(bill['amount'] for bill in bills if bill['status'] == 'unpaid')
        total_overdue = sum(bill['amount'] for bill in bills if bill['status'] == 'overdue')
        total_bills = sum(bill['amount'] for bill in bills)

        categories = {}
        for bill in bills:
            cat = bill['category']
            categories[cat] = categories.get(cat, 0) + bill['amount']

        today = date.today()
        due_today = [b for b in bills if b['due_date'] == today.strftime('%Y-%m-%d')]
        due_week = [b for b in bills if today <= datetime.strptime(b['due_date'], '%Y-%m-%d').date() <= (today + timedelta(days=7))]
        due_month = [b for b in bills if today <= datetime.strptime(b['due_date'], '%Y-%m-%d').date() <= (today + timedelta(days=30))]
        upcoming_bills = [b for b in bills if today < datetime.strptime(b['due_date'], '%Y-%m-%d').date()]

        tips = [
            trans("bill_tip_pay_early"),
            trans("bill_tip_energy_efficient"),
            trans("bill_tip_plan_monthly"),
            trans("bill_tip_ajo_reminders"),
            trans("bill_tip_data_topup")
        ]

        return render_template(
            'bill_dashboard.html',
            bills=bills,
            paid_count=paid_count,
            unpaid_count=unpaid_count,
            overdue_count=overdue_count,
            pending_count=pending_count,
            total_paid=total_paid,
            total_unpaid=total_unpaid,
            total_overdue=total_overdue,
            total_bills=total_bills,
            categories=categories,
            due_today=due_today,
            due_week=due_week,
            due_month=due_month,
            upcoming_bills=upcoming_bills,
            tips=tips,
            trans=trans,
            lang=lang
        )
    except Exception as e:
        current_app.logger.exception(f"Error in bill.dashboard: {str(e)}")
        flash(trans("bill_dashboard_load_error"), "danger")
        try:
            return render_template(
                'bill_dashboard.html',
                bills=[],
                paid_count=0,
                unpaid_count=0,
                overdue_count=0,
                pending_count=0,
                total_paid=0,
                total_unpaid=0,
                total_overdue=0,
                total_bills=0,
                categories={},
                due_today=[],
                due_week=[],
                due_month=[],
                upcoming_bills=[],
                tips=[
                    trans("bill_tip_pay_early"),
                    trans("bill_tip_energy_efficient"),
                    trans("bill_tip_plan_monthly"),
                    trans("bill_tip_ajo_reminders"),
                    trans("bill_tip_data_topup")
                ],
                trans=trans,
                lang=lang
            )
        except Exception as render_e:
            current_app.logger.exception(f"Template rendering error in bill.dashboard: {str(render_e)}")
            flash(trans("bill_dashboard_template_error"), "danger")
            return redirect(url_for('index'))

@bill_bp.route('/view_edit', methods=['GET', 'POST'])
def view_edit():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    lang = session.get('lang', 'en')
    try:
        bill_storage = current_app.config['STORAGE_MANAGERS']['bills']
        user_data = bill_storage.filter_by_session(session['sid'])
        bills = [(record["id"], record["data"]) for record in user_data]
        form = BillForm()

        if request.method == 'POST':
            action = request.form.get('action')
            bill_id = request.form.get('bill_id')

            if action == "edit":
                if form.validate_on_submit():
                    try:
                        data = form.data
                        try:
                            due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
                            if due_date < date.today():
                                flash(trans("bill_due_date_future_validation"), "danger")
                                current_app.logger.error("Due date in the past in bill.view_edit")
                                return redirect(url_for('bill.view_edit'))
                        except ValueError:
                            flash(trans("bill_due_date_format_invalid"), "danger")
                            current_app.logger.error("Invalid due date format in bill.view_edit")
                            return redirect(url_for('bill.view_edit'))

                        status = data['status']
                        if status not in ['paid', 'pending'] and due_date < date.today():
                            status = 'overdue'

                        updated_record = {
                            "data": {
                                "first_name": data['first_name'],
                                "bill_name": data['bill_name'],
                                "amount": data['amount'],
                                "due_date": data['due_date'],
                                "frequency": data['frequency'],
                                "category": data['category'],
                                "status": status
                            }
                        }
                        if bill_storage.update_by_id(bill_id, updated_record):
                            flash(trans("bill_bill_updated_success"), "success")
                        else:
                            flash(trans("bill_bill_update_failed"), "danger")
                            current_app.logger.error(f"Failed to update bill ID {bill_id}")
                    except Exception as e:
                        current_app.logger.exception(f"Error in bill.view_edit (edit): {str(e)}")
                        flash(trans("bill_bill_update_error"), "danger")
                    return redirect(url_for('bill.view_edit'))

            elif action == "delete":
                try:
                    if bill_storage.delete_by_id(bill_id):
                        flash(trans("bill_bill_deleted_success"), "success")
                    else:
                        flash(trans("bill_bill_delete_failed"), "danger")
                        current_app.logger.error(f"Failed to delete bill ID {bill_id}")
                    return redirect(url_for('bill.view_edit'))
                except Exception as e:
                    current_app.logger.exception(f"Error in bill.view_edit (delete): {str(e)}")
                    flash(trans("bill_bill_delete_error"), "danger")
                    return redirect(url_for('bill.view_edit'))

            elif action == "toggle_status":
                try:
                    record = bill_storage.get_by_id(bill_id)
                    if record:
                        current_status = record["data"]["status"]
                        new_status = 'paid' if current_status == 'unpaid' else 'unpaid'
                        record["data"]["status"] = new_status
                        if bill_storage.update_by_id(bill_id, record):
                            flash(trans("bill_bill_status_toggled"), "success")
                        else:
                            flash(trans("bill_bill_status_toggle_failed"), "danger")
                            current_app.logger.error(f"Failed to toggle status for bill ID {bill_id}")
                    else:
                        flash(trans("bill_bill_not_found"), "danger")
                        current_app.logger.error(f"Bill ID {bill_id} not found")
                    return redirect(url_for('bill.view_edit'))
                except Exception as e:
                    current_app.logger.exception(f"Error in bill.view_edit (toggle_status): {str(e)}")
                    flash(trans("bill_bill_status_toggle_error"), "danger")
                    return redirect(url_for('bill.view_edit'))

        return render_template('view_edit_bills.html', bills=bills, form=form, trans=trans, lang=lang)
    except Exception as e:
        current_app.logger.exception(f"Error in bill.view_edit: {str(e)}")
        flash(trans("bill_bills_load_error"), "danger")
        try:
            return render_template('view_edit_bills.html', bills=[], form=BillForm(), trans=trans, lang=lang)
        except Exception as render_e:
            current_app.logger.exception(f"Template rendering error in bill.view_edit: {str(render_e)}")
            flash(trans("bill_view_edit_template_error"), "danger")
            return redirect(url_for('index'))
