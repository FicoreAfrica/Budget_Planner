from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Email
from json_store import JsonStorage
from mailersend_email import send_email
from translations import trans
from datetime import datetime, date, timedelta
import logging
import uuid

# Configure logging
logging.basicConfig(filename='data/storage.txt', level=logging.DEBUG)

bill_bp = Blueprint('bill', __name__)
bill_storage = JsonStorage('data/bills.json')

class BillForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(message='First name is required')])
    email = StringField('Email', validators=[DataRequired(message='Valid email is required'), Email()])
    bill_name = StringField('Bill Name', validators=[DataRequired(message='Bill name is required')])
    amount = FloatField('Amount', validators=[DataRequired(message='Valid amount is required'), NumberRange(min=0, max=10000000000)])
    due_date = StringField('Due Date (YYYY-MM-DD)', validators=[DataRequired(message='Valid due date is required')])
    frequency = SelectField('Frequency', choices=[
        ('one-time', 'One-time'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly')
    ], default='one-time')
    category = SelectField('Category', choices=[
        ('utilities', 'Utilities'),
        ('rent', 'Rent'),
        ('data_internet', 'Data/Internet'),
        ('ajo_esusu_adashe', 'Ajo/Esusu/Adashe'),
        ('food', 'Food'),
        ('transport', 'Transport'),
        ('clothing', 'Clothing'),
        ('education', 'Education'),
        ('healthcare', 'Healthcare'),
        ('entertainment', 'Entertainment'),
        ('airtime', 'Airtime'),
        ('school_fees', 'School Fees'),
        ('savings_investments', 'Savings/Investments'),
        ('other', 'Other')
    ], validators=[DataRequired(message='Category is required')])
    send_email = BooleanField('Send Email Reminders')
    status = SelectField('Status', choices=[
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('overdue', 'Overdue')
    ], default='unpaid')
    submit = SubmitField('Save Bill')

@bill_bp.route('/form', methods=['GET', 'POST'])
def form():
    """Handle bill creation form."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = BillForm()
    t = trans('t')
    try:
        if request.method == 'POST' and form.validate_on_submit():
            try:
                data = form.data
                # Validate due date
                try:
                    due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
                    if due_date < date.today():
                        flash(t("Due date must be today or in the future"))
                        logging.error("Due date in the past in bill.form")
                        return redirect(url_for('bill.form'))
                except ValueError:
                    flash(t("Invalid due date format. Use YYYY-MM-DD."))
                    logging.error("Invalid due date format in bill.form")
                    return redirect(url_for('bill.form'))

                # Compute dynamic status
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
                bill_storage.append(record, user_email=data['email'], session_id=session['sid'])
                if data['send_email'] and data['email']:
                    send_email(
                        to_email=data['email'],
                        subject=t("Bill Payment Reminder"),
                        template_name="bill_reminder.html",
                        data={
                            "first_name": data['first_name'],
                            "bill_name": data['bill_name'],
                            "amount": data['amount'],
                            "due_date": data['due_date'],
                            "category": t(data['category'].replace('_', '/').title()),
                            "status": t(status.capitalize()),
                            "cta_url": url_for('bill.dashboard', _external=True)
                        },
                        lang=session.get('lang', 'en')
                    )
                flash(t("Bill added successfully."))
                return redirect(url_for('bill.view_edit'))
            except Exception as e:
                logging.exception(f"Error processing bill form: {str(e)}")
                flash(t("An error occurred while adding the bill."))
                return redirect(url_for('bill.form'))
        return render_template('bill_form.html', form=form, t=t)
    except Exception as e:
        logging.exception(f"Template rendering error in bill.form: {str(e)}")
        flash(t("Error loading the bill form."))
        return redirect(url_for('index'))

@bill_bp.route('/dashboard')
def dashboard():
    """Display user's bills with enhanced details."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    t = trans('t')
    try:
        user_data = bill_storage.filter_by_session(session['sid'])
        bills = [record["data"] for record in user_data]
        # Compute statistics
        paid_count = sum(1 for bill in bills if bill['status'] == 'paid')
        unpaid_count = sum(1 for bill in bills if bill['status'] == 'unpaid')
        overdue_count = sum(1 for bill in bills if bill['status'] == 'overdue')
        pending_count = sum(1 for bill in bills if bill['status'] == 'pending')
        total_paid = sum(bill['amount'] for bill in bills if bill['status'] == 'paid')
        total_unpaid = sum(bill['amount'] for bill in bills if bill['status'] == 'unpaid')
        total_overdue = sum(bill['amount'] for bill in bills if bill['status'] == 'overdue')
        total_bills = sum(bill['amount'] for bill in bills)

        # Spending by category
        categories = {}
        for bill in bills:
            cat = bill['category']
            categories[cat] = categories.get(cat, 0) + bill['amount']

        # Bills due
        today = date.today()
        due_today = [b for b in bills if b['due_date'] == today.strftime('%Y-%m-%d')]
        due_week = [b for b in bills if today <= datetime.strptime(b['due_date'], '%Y-%m-%d').date() <= (today + timedelta(days=7))]
        due_month = [b for b in bills if today <= datetime.strptime(b['due_date'], '%Y-%m-%d').date() <= (today + timedelta(days=30))]
        upcoming_bills = [b for b in bills if today < datetime.strptime(b['due_date'], '%Y-%m-%d').date()]

        # Nigeria-specific tips
        tips = [
            t("Pay bills early to avoid late fees. Use mobile money for quick payments."),
            t("Switch to energy-efficient utilities to save money."),
            t("Plan monthly bills to manage your budget better."),
            t("Set reminders for Ajo/Esusu/Adashe contributions to stay on track."),
            t("Top up data plans early to avoid service interruptions.")
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
            t=t
        )
    except Exception as e:
        logging.exception(f"Error in bill.dashboard: {str(e)}")
        flash(t("Error loading dashboard."))
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
                tips=[],
                t=t
            )
        except Exception as render_e:
            logging.exception(f"Template rendering error in bill.dashboard: {str(render_e)}")
            flash(t("Error loading the dashboard template."))
            return redirect(url_for('index'))

@bill_bp.route('/view_edit', methods=['GET', 'POST'])
def view_edit():
    """Handle bill viewing, editing, and deletion."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    t = trans('t')
    try:
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
                                flash(t("Due date must be today or in the future"))
                                logging.error("Due date in the past in bill.view_edit")
                                return redirect(url_for('bill.view_edit'))
                        except ValueError:
                            flash(t("Invalid due date format. Use YYYY-MM-DD."))
                            logging.error("Invalid due date format in bill.view_edit")
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
                            flash(t("Bill updated successfully."))
                        else:
                            flash(t("Failed to update bill."))
                            logging.error(f"Failed to update bill ID {bill_id}")
                    except Exception as e:
                        logging.exception(f"Error in bill.view_edit (edit): {str(e)}")
                        flash(t("Error updating bill."))
                    return redirect(url_for('bill.view_edit'))

            elif action == "delete":
                try:
                    if bill_storage.delete_by_id(bill_id):
                        flash(t("Bill deleted successfully."))
                    else:
                        flash(t("Failed to delete bill."))
                        logging.error(f"Failed to delete bill ID {bill_id}")
                    return redirect(url_for('bill.view_edit'))
                except Exception as e:
                    logging.exception(f"Error in bill.view_edit (delete): {str(e)}")
                    flash(t("Error deleting bill."))
                    return redirect(url_for('bill.view_edit'))

            elif action == "toggle_status":
                try:
                    record = bill_storage.get_by_id(bill_id)
                    if record:
                        current_status = record["data"]["status"]
                        new_status = 'paid' if current_status == 'unpaid' else 'unpaid'
                        record["data"]["status"] = new_status
                        if bill_storage.update_by_id(bill_id, record):
                            flash(t("Bill status toggled successfully."))
                        else:
                            flash(t("Failed to toggle bill status."))
                            logging.error(f"Failed to toggle status for bill ID {bill_id}")
                    else:
                        flash(t("Bill not found."))
                        logging.error(f"Bill ID {bill_id} not found")
                    return redirect(url_for('bill.view_edit'))
                except Exception as e:
                    logging.exception(f"Error in bill.view_edit (toggle_status): {str(e)}")
                    flash(t("Error toggling bill status."))
                    return redirect(url_for('bill.view_edit'))

        return render_template('view_edit_bills.html', bills=bills, form=form, t=t)
    except Exception as e:
        logging.exception(f"Error in bill.view_edit: {str(e)}")
        flash(t("Error loading bills."))
        try:
            return render_template('view_edit_bills.html', bills=[], form=BillForm(), t=t)
        except Exception as render_e:
            logging.exception(f"Template rendering error in bill.view_edit: {str(render_e)}")
            flash(t("Error loading the view/edit template."))
            return redirect(url_for('index'))
