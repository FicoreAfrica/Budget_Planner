from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, BooleanField, SubmitField, IntegerField
from wtforms.validators import DataRequired, NumberRange, Email
from json_store import JsonStorage
from mailersend_email import send_email, EMAIL_CONFIG
from datetime import datetime, date, timedelta
import uuid

try:
    from app import trans
except ImportError:
    def trans(key, lang=None):
        return key

bill_bp = Blueprint('bill', __name__, url_prefix='/bill')

def init_bill_storage(app):
    """Initialize bill_storage within app context."""
    with app.app_context():
        app.logger.info("Initializing bill storage")
        return JsonStorage('data/bills.json', logger_instance=app.logger)

def strip_commas(value):
    if isinstance(value, str):
        return value.replace(',', '')
    return value

class BillForm(FlaskForm):
    first_name = StringField('First Name')
    email = StringField('Email')
    bill_name = StringField('Bill Name')
    amount = FloatField('Amount', filters=[strip_commas])
    due_date = StringField('Due Date (YYYY-MM-DD)')
    frequency = SelectField('Frequency')
    category = SelectField('Category')
    send_email = BooleanField('Send Email Reminders')
    reminder_days = IntegerField('Reminder Days', default=7)
    status = SelectField('Status')
    submit = SubmitField('Save Bill')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = session.get('lang', 'en')

        self.first_name.validators = [DataRequired(message=trans('bill_first_name_required', lang))]
        self.email.validators = [DataRequired(message=trans('bill_email_required', lang)), Email()]
        self.bill_name.validators = [DataRequired(message=trans('bill_bill_name_required', lang))]
        self.amount.validators = [DataRequired(message=trans('bill_amount_required', lang)), NumberRange(min=0, max=10000000000)]
        self.due_date.validators = [DataRequired(message=trans('bill_due_date_required', lang))]
        self.category.validators = [DataRequired(message=trans('bill_category_required', lang))]
        self.reminder_days.validators = [DataRequired(message=trans('bill_reminder_days_required', lang)), NumberRange(min=1, max=30)]

        self.frequency.choices = [
            ('one-time', trans('bill_frequency_one_time', lang)),
            ('weekly', trans('bill_frequency_weekly', lang)),
            ('monthly', trans('bill_frequency_monthly', lang)),
            ('quarterly', trans('bill_frequency_quarterly', lang))
        ]
        self.frequency.default = 'one-time'

        self.category.choices = [
            ('utilities', trans('bill_category_utilities', lang)),
            ('rent', trans('bill_category_rent', lang)),
            ('data_internet', trans('bill_category_data_internet', lang)),
            ('ajo_esusu_adashe', trans('bill_category_ajo_esusu_adashe', lang)),
            ('food', trans('bill_category_food', lang)),
            ('transport', trans('bill_category_transport', lang)),
            ('clothing', trans('bill_category_clothing', lang)),
            ('education', trans('bill_category_education', lang)),
            ('healthcare', trans('bill_category_healthcare', lang)),
            ('entertainment', trans('bill_category_entertainment', lang)),
            ('airtime', trans('bill_category_airtime', lang)),
            ('school_fees', trans('bill_category_school_fees', lang)),
            ('savings_investments', trans('bill_category_savings_investments', lang)),
            ('other', trans('bill_category_other', lang))
        ]

        self.status.choices = [
            ('unpaid', trans('bill_status_unpaid', lang)),
            ('paid', trans('bill_status_paid', lang)),
            ('pending', trans('bill_status_pending', lang)),
            ('overdue', trans('bill_status_overdue', lang))
        ]
        self.status.default = 'unpaid'

        self.send_email.label.text = trans('bill_send_email_reminders', lang)
        self.reminder_days.label.text = trans('bill_reminder_days', lang)
        self.submit.label.text = trans('bill_save_bill', lang)

        self.process()

@bill_bp.route('/form', methods=['GET', 'POST'])
def form():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True  # Ensure session persists
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
                        "status": status,
                        "send_email": data['send_email'],
                        "reminder_days": data['reminder_days']
                    }
                }
                bill_storage = current_app.config['STORAGE_MANAGERS']['bills']
                bill_storage.append(record, user_email=data['email'], session_id=session['sid'], lang=lang)
                
                if data['send_email'] and data['email']:
                    try:
                        config = EMAIL_CONFIG["bill_reminder"]
                        subject = trans(config["subject_key"], lang=lang)
                        template = config["template"]
                        send_email(
                            app=current_app,
                            logger=current_app.logger,
                            to_email=data['email'],
                            subject=subject,
                            template_name=template,
                            data={
                                "first_name": data['first_name'],
                                "bills": [{
                                    "bill_name": data['bill_name'],
                                    "amount": data['amount'],
                                    "due_date": data['due_date'],
                                    "category": trans(f"bill_category_{data['category']}", lang=lang),
                                    "status": trans(f"bill_status_{status}", lang=lang)
                                }],
                                "cta_url": url_for('bill.dashboard', _external=True),
                                "unsubscribe_url": url_for('bill.unsubscribe', email=data['email'], _external=True)
                            },
                            lang=lang
                        )
                    except Exception as e:
                        current_app.logger.error(f"Failed to send email: {str(e)}")
                        flash(trans("email_send_failed", lang=lang), UU"warning")
                
                flash(trans("bill_bill_added_dynamic_dashboard").format(
                    bill_name=data['bill_name'],
                    dashboard_url=url_for('bill.dashboard')
                ), "success")
                return redirect(url_for('bill.dashboard'))
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
        session.permanent = True
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
        session.permanent = True
    lang = session.get('lang', 'en')
    bill_storage = current_app.config['STORAGE_MANAGERS']['bills']
    user_data = bill_storage.filter_by_session(session['sid'])
    bills = [(record["id"], record["data"]) for record in user_data]
    form = BillForm()

    if request.method == 'POST':
        action = request.form.get('action')
        bill_id = request.form.get('bill_id')

        if action == "edit":
            try:
                if form.validate_on_submit():
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
                            "status": status,
                            "send_email": data['send_email'],
                            "reminder_days": data['reminder_days']
                        }
                    }
                    if bill_storage.update_by_id(bill_id, updated_record):
                        flash(trans("bill_bill_updated_success"), "success")
                    else:
                        flash(trans("bill_bill_update_failed"), "danger")
                        current_app.logger.error(f"Failed to update bill ID {bill_id}")
                return redirect(url_for('bill.dashboard'))
            except Exception as e:
                current_app.logger.exception(f"Error in bill.view_edit (edit): {str(e)}")
                flash(trans("bill_bill_update_error"), "danger")
                return redirect(url_for('bill.dashboard'))

        elif action == "delete":
            try:
                if bill_storage.delete_by_id(bill_id):
                    flash(trans("bill_bill_deleted_success"), "success")
                else:
                    flash(trans("bill_bill_delete_failed"), "danger")
                    current_app.logger.error(f"Failed to delete bill ID {bill_id}")
                return redirect(url_for('bill.dashboard'))
            except Exception as e:
                current_app.logger.exception(f"Error in bill.view_edit (delete): {str(e)}")
                flash(trans("bill_bill_delete_error"), "danger")
                return redirect(url_for('bill.dashboard'))

        elif action == "toggle_status":
            try:
                record = bill_storage.get_by_id(bill_id)
                if record:
                    current_status = record["data"]["status"]
                    new_status = 'paid' if current_status == 'unpaid' else 'unpaid'
                    record["data"]["status"] = new_status
                    if bill_storage.update_by_id(bill_id, record):
                        flash(trans("bill_bill_status_toggled"), "success")
                        if new_status == 'paid' and record["data"]["frequency"] != 'one-time':
                            try:
                                old_due_date = datetime.strptime(record["data"]["due_date"], '%Y-%m-%d').date()
                                frequency = record["data"]["frequency"]
                                if frequency == 'weekly':
                                    new_due_date = old_due_date + timedelta(days=7)
                                elif frequency == 'monthly':
                                    new_due_date = old_due_date + timedelta(days=30)
                                elif frequency == 'quarterly':
                                    new_due_date = old_due_date + timedelta(days=90)
                                new_record = {
                                    "data": {
                                        "first_name": record["data"]["first_name"],
                                        "bill_name": record["data"]["bill_name"],
                                        "amount": record["data"]["amount"],
                                        "due_date": new_due_date.strftime('%Y-%m-%d'),
                                        "frequency": frequency,
                                        "category": record["data"]["category"],
                                        "status": "unpaid",
                                        "send_email": record["data"]["send_email"],
                                        "reminder_days": record["data"]["reminder_days"]
                                    }
                                }
                                bill_storage.append(new_record, user_email=record["user_email"], session_id=session['sid'], lang=lang)
                                flash(trans("bill_new_recurring_bill_added").format(bill_name=record["data"]["bill_name"]), "success")
                            except Exception as e:
                                current_app.logger.exception(f"Error creating recurring bill: {str(e)}")
                                flash(trans("bill_recurring_bill_error"), "warning")
                    else:
                        flash(trans("bill_bill_status_toggle_failed"), "danger")
                        current_app.logger.error(f"Failed to toggle status for bill ID {bill_id}")
                else:
                    flash(trans("bill_bill_not_found"), "danger")
                    current_app.logger.error(f"Bill ID {bill_id} not found")
                return redirect(url_for('bill.dashboard'))
            except Exception as e:
                current_app.logger.exception(f"Error in bill.view_edit (toggle_status): {str(e)}")
                flash(trans("bill_bill_status_toggle_error"), "danger")
                return redirect(url_for('bill.dashboard'))

    try:
        return render_template('view_edit_bills.html', bills=bills, form=form, trans=trans, lang=lang, category=request.args.get('category', 'all'))
    except Exception as e:
        current_app.logger.exception(f"Template rendering error in bill.view_edit: {str(e)}")
        flash(trans("bill_view_edit_template_error"), "danger")
        return redirect(url_for('index'))

@bill_bp.route('/unsubscribe/<email>')
def unsubscribe(email):
    try:
        bill_storage = current_app.config['STORAGE_MANAGERS']['bills']
        user_data = bill_storage.get_all()
        updated = False
        for record in user_data:
            if record.get('user_email') == email:
                record['data']['send_email'] = False
                if bill_storage.update_by_id(record['id'], record):
                    updated = True
        if updated:
            flash(trans("bill_unsubscribed_success"), "success")
        else:
            flash(trans("bill_unsubscribe_failed"), "danger")
            current_app.logger.error(f"Failed to unsubscribe email {email}")
        return redirect(url_for('index'))
    except Exception as e:
        current_app.logger.exception(f"Error in bill.unsubscribe: {str(e)}")
        flash(trans("bill_unsubscribe_error"), "danger")
        return redirect(url_for('index'))