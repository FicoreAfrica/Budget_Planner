from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange
from json_store import JsonStorage
from mailersend_email import send_email
from ..translations import trans
from datetime import datetime
import logging
import uuid

# Configure logging
logging.basicConfig(filename='data/storage.txt', level=logging.DEBUG)

bill_bp = Blueprint('bill', __name__)
bill_storage = JsonStorage('data/bills.json')

# Form for bill creation and editing
class BillForm(FlaskForm):
    bill_name = StringField('Bill Name', validators=[DataRequired()])
    amount = FloatField('Amount', validators=[DataRequired(), NumberRange(min=0, max=10000000000)])
    due_date = StringField('Due Date (YYYY-MM-DD)', validators=[DataRequired()])
    category = SelectField('Category', choices=[('utility', 'Utility'), ('rent', 'Rent'), ('other', 'Other')])
    email = StringField('Email')
    send_email = SelectField('Send Email', choices=[('on', 'Yes'), ('off', 'No')])
    status = SelectField('Status', choices=[('unpaid', 'Unpaid'), ('paid', 'Paid')], default='unpaid')
    submit = SubmitField('Submit')

@bill_bp.route('/form', methods=['GET', 'POST'])
def form():
    """Handle bill creation form."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    form = BillForm()
    t = trans('t')  # Get translation dictionary
    if request.method == 'POST' and form.validate_on_submit():
        try:
            data = form.data
            try:
                datetime.strptime(data['due_date'], '%Y-%m-%d')
            except ValueError:
                flash(trans("Invalid due date format. Use YYYY-MM-DD."))
                logging.error("Invalid due date format in bill.form")
                return redirect(url_for('bill.form'))
            record = {
                "data": {
                    "bill_name": data['bill_name'],
                    "amount": data['amount'],
                    "due_date": data['due_date'],
                    "category": data['category'],
                    "status": data['status']
                }
            }
            bill_storage.append(record, user_email=data['email'], session_id=session['sid'])
            if data['send_email'] == 'on' and data['email']:
                send_email(
                    to_email=data['email'],
                    subject=trans("Bill Reminder"),
                    template_name="bill_reminder.html",
                    data=record["data"],
                    lang=session.get('lang', 'en')
                )
            flash(trans("Bill added successfully."))
            return redirect(url_for('bill.dashboard'))
        except Exception as e:
            logging.exception(f"Error in bill.form: {str(e)}")
            flash(trans("An error occurred while adding the bill."))
            return redirect(url_for('bill.form'))
    return render_template('bill_form.html', form=form, t=t)

@bill_bp.route('/dashboard')
def dashboard():
    """Display user's bills."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    t = trans('t')
    try:
        user_data = bill_storage.filter_by_session(session['sid'])
        bills = [record["data"] for record in user_data]
        return render_template('bill_dashboard.html', bills=bills, t=t)
    except Exception as e:
        logging.exception(f"Error in bill.dashboard: {str(e)}")
        flash(trans("Error loading dashboard."))
        return render_template('bill_dashboard.html', bills=[], t=t)

@bill_bp.route('/view_edit', methods=['GET', 'POST'])
def view_edit():
    """Handle bill viewing, editing, and deletion."""
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    t = trans('t')
    try:
        user_data = bill_storage.filter_by_session(session['sid'])
        bills = [(record["id"], record["data"]) for record in user_data]
        
        if request.method == 'POST':
            action = request.form.get('action')
            bill_id = request.form.get('bill_id')
            
            if action == "edit":
                form = BillForm()
                if form.validate_on_submit():
                    try:
                        data = form.data
                        try:
                            datetime.strptime(data['due_date'], '%Y-%m-%d')
                        except ValueError:
                            flash(trans("Invalid due date format. Use YYYY-MM-DD."))
                            logging.error("Invalid due date format in bill.view_edit")
                            return redirect(url_for('bill.view_edit'))
                        updated_record = {
                            "data": {
                                "bill_name": data['bill_name'],
                                "amount": data['amount'],
                                "due_date": data['due_date'],
                                "category": data['category'],
                                "status": data['status']
                            }
                        }
                        if bill_storage.update_by_id(bill_id, updated_record):
                            flash(trans("Bill updated successfully."))
                        else:
                            flash(trans("Failed to update bill."))
                            logging.error(f"Failed to update bill ID {bill_id}")
                    except Exception as e:
                        logging.exception(f"Error in bill.view_edit (edit): {str(e)}")
                        flash(trans("Error updating bill."))
                    return redirect(url_for('bill.view_edit'))
                
            elif action == "delete":
                try:
                    if bill_storage.delete_by_id(bill_id):
                        flash(trans("Bill deleted successfully."))
                    else:
                        flash(trans("Failed to delete bill."))
                        logging.error(f"Failed to delete bill ID {bill_id}")
                    return redirect(url_for('bill.view_edit'))
                except Exception as e:
                    logging.exception(f"Error in bill.view_edit (delete): {str(e)}")
                    flash(trans("Error deleting bill."))
                    return redirect(url_for('bill.view_edit'))
                
            elif action == "toggle_status":
                try:
                    record = bill_storage.get_by_id(bill_id)
                    if record:
                        record["data"]["status"] = "paid" if record["data"]["status"] == "unpaid" else "unpaid"
                        if bill_storage.update_by_id(bill_id, record):
                            flash(trans("Bill status toggled successfully."))
                        else:
                            flash(trans("Failed to toggle bill status."))
                            logging.error(f"Failed to toggle status for bill ID {bill_id}")
                    else:
                        flash(trans("Bill not found."))
                        logging.error(f"Bill ID {bill_id} not found")
                    return redirect(url_for('bill.view_edit'))
                except Exception as e:
                    logging.exception(f"Error in bill.view_edit (toggle_status): {str(e)}")
                    flash(trans("Error toggling bill status."))
                    return redirect(url_for('bill.view_edit'))
        
        return render_template('view_edit_bills.html', bills=bills, form=BillForm(), t=t)
    except Exception as e:
        logging.exception(f"Error in bill.view_edit: {str(e)}")
        flash(trans("Error loading bills."))
        return render_template('view_edit_bills.html', bills=[], form=BillForm(), t=t)
