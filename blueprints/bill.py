from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from json_store import JsonStorageManager
from mailersend_email import send_email
from datetime import datetime

bill_bp = Blueprint('bill', __name__)
bill_storage = JsonStorageManager('data/bills.json')

@bill_bp.route('/form', methods=['GET', 'POST'])
def form():
    if request.method == 'POST':
        try:
            data = request.form.to_dict()
            amount = float(data.get('amount', 0))
            if amount > 10000000000:
                flash(t("Amount cannot exceed ₦10 billion."))
                return redirect(url_for('bill.form'))
            due_date = data.get('due_date')
            # Validate due date format (YYYY-MM-DD)
            try:
                datetime.strptime(due_date, '%Y-%m-%d')
            except ValueError:
                flash(t("Invalid due date format. Use YYYY-MM-DD."))
                return redirect(url_for('bill.form'))
            email = data.get('email')
            send_email_flag = data.get('send_email') == 'on'
            record = {
                "data": {
                    "bill_name": data.get('bill_name'),
                    "amount": amount,
                    "due_date": due_date,
                    "category": data.get('category'),
                    "status": "unpaid"
                }
            }
            bill_storage.append(record, user_email=email, session_id=session.sid)
            if send_email_flag and email:
                send_email(
                    to_email=email,
                    subject="Bill Reminder",
                    template_name="bill_reminder.html",
                    data=record["data"],
                    lang=session.get('lang', 'en')
                )
            flash(t("Bill added successfully."))
            return redirect(url_for('bill.dashboard'))
        except ValueError:
            flash(t("Invalid numeric input for amount."))
            return redirect(url_for('bill.form'))
    return render_template('bill_form.html')

@bill_bp.route('/dashboard')
def dashboard():
    user_data = bill_storage.filter_by_session(session.sid)
    bills = [record["data"] for record in user_data]
    return render_template('bill_dashboard.html', bills=bills)

@bill_bp.route('/view_edit', methods=['GET', 'POST'])
def view_edit():
    user_data = bill_storage.filter_by_session(session.sid)
    bills = [(record["id"], record["data"]) for record in user_data]
    
    if request.method == 'POST':
        action = request.form.get('action')
        bill_id = request.form.get('bill_id')
        
        if action == "edit":
            try:
                data = request.form.to_dict()
                amount = float(data.get('amount', 0))
                if amount > 10000000000:
                    flash(t("Amount cannot exceed ₦10 billion."))
                    return redirect(url_for('bill.view_edit'))
                due_date = data.get('due_date')
                try:
                    datetime.strptime(due_date, '%Y-%m-%d')
                except ValueError:
                    flash(t("Invalid due date format. Use YYYY-MM-DD."))
                    return redirect(url_for('bill.view_edit'))
                updated_record = {
                    "data": {
                        "bill_name": data.get('bill_name'),
                        "amount": amount,
                        "due_date": due_date,
                        "category": data.get('category'),
                        "status": data.get('status', 'unpaid')
                    }
                }
                if bill_storage.update_by_id(bill_id, updated_record):
                    flash(t("Bill updated successfully."))
                else:
                    flash(t("Failed to update bill."))
            except ValueError:
                flash(t("Invalid numeric input for amount."))
            return redirect(url_for('bill.view_edit'))
        
        elif action == "delete":
            if bill_storage.delete_by_id(bill_id):
                flash(t("Bill deleted successfully."))
            else:
                flash(t("Failed to delete bill."))
            return redirect(url_for('bill.view_edit'))
        
        elif action == "mark_paid":
            record = bill_storage.get_by_id(bill_id)
            if record:
                record["data"]["status"] = "paid"
                if bill_storage.update_by_id(bill_id, record):
                    flash(t("Bill marked as paid."))
                else:
                    flash(t("Failed to mark bill as paid."))
            else:
                flash(t("Bill not found."))
            return redirect(url_for('bill.view_edit'))

    return render_template('view_edit_bills.html', bills=bills)
