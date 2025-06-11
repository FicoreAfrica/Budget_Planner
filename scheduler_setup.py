from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from datetime import datetime, date, timedelta
from flask import current_app
from mailersend_email import send_email, trans, EMAIL_CONFIG

def update_overdue_status():
    """Update status to overdue for past-due bills."""
    with current_app.app_context():
        try:
            mongo = current_app.extensions['mongo']
            db = mongo.db
            bills_collection = db.bills
            today = date.today()
            bills = bills_collection.find({'status': {'$in': ['pending', 'unpaid']}})
            updated_count = 0
            for bill in bills:
                bill_due_date = bill['due_date']
                if isinstance(bill_due_date, str):
                    bill_due_date = datetime.strptime(bill_due_date, '%Y-%m-%d').date()
                if bill_due_date < today:
                    bills_collection.update_one(
                        {'_id': bill['_id']},
                        {'$set': {'status': 'overdue'}}
                    )
                    updated_count += 1
            current_app.logger.info(f"Updated {updated_count} overdue bill statuses")
        except Exception as e:
            current_app.logger.exception(f"Error in update_overdue_status: {str(e)}")

def send_bill_reminders():
    """Send reminders for upcoming and overdue bills."""
    with current_app.app_context():
        try:
            mongo = current_app.extensions['mongo']
            db = mongo.db
            bills_collection = db.bills
            bill_reminders_collection = db.bill_reminders
            users_collection = db.users
            today = date.today()
            user_bills = {}
            bills = bills_collection.find()
            for bill in bills:
                email = bill['user_email']
                user = users_collection.find_one({'email': email}, {'lang': 1})
                lang = user.get('lang', 'en') if user else 'en'
                if bill.get('send_email') and email:
                    reminder_window = today + timedelta(days=bill.get('reminder_days', 7))
                    bill_due_date = bill['due_date']
                    if isinstance(bill_due_date, str):
                        bill_due_date = datetime.strptime(bill_due_date, '%Y-%m-%d').date()
                    if (bill['status'] in ['pending', 'overdue'] or 
                        (today <= bill_due_date <= reminder_window)):
                        if email not in user_bills:
                            user_bills[email] = {
                                'first_name': bill.get('first_name', 'User'),
                                'bills': [],
                                'lang': lang
                            }
                        user_bills[email]['bills'].append({
                            'bill_name': bill['bill_name'],
                            'amount': bill['amount'],
                            'due_date': bill_due_date.strftime('%Y-%m-%d'),
                            'category': trans(f"bill_category_{bill['category']}", lang=lang),
                            'status': trans(f"bill_status_{bill['status']}", lang=lang)
                        })

            for email, data in user_bills.items():
                try:
                    config = EMAIL_CONFIG["bill_reminder"]
                    subject = trans(config["subject_key"], lang=data['lang'])
                    reminder_data = {
                        'email': email,
                        'first_name': data['first_name'],
                        'bills': data['bills'],
                        'lang': data['lang'],
                        'sent_at': datetime.utcnow(),
                        'cta_url': url_for('bill.dashboard', _external=True),
                        'unsubscribe_url': url_for('bill.unsubscribe', email=email, _external=True)
                    }
                    send_email(
                        app=current_app,
                        logger=current_app.logger,
                        to_email=email,
                        subject=subject,
                        template_name=config["template"],
                        data=reminder_data,
                        lang=data['lang']
                    )
                    bill_reminders_collection.insert_one(reminder_data)
                    current_app.logger.info(f"Sent bill reminder email to {email} and saved to bill_reminders")
                except Exception as e:
                    current_app.logger.error(f"Failed to send reminder email to {email}: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error in send_bill_reminders: {str(e)}", exc_info=True)

def init_scheduler(app, mongo):
    """Initialize the background scheduler."""
    with app.app_context():
        try:
            jobstores = {
                'mongodb': MongoDBJobStore(
                    database=mongo.db.name,
                    collection='scheduler_jobs',
                    client=mongo.cx
                )
            }
            scheduler = BackgroundScheduler(jobstores=jobstores)
            scheduler.add_job(
                func=update_overdue_status,
                trigger='interval',
                days=1,
                id='overdue_status',
                name='Update overdue bill statuses daily',
                replace_existing=True
            )
            scheduler.add_job(
                func=send_bill_reminders,
                trigger='interval',
                days=1,
                id='bill_reminders',
                name='Send bill reminders daily',
                replace_existing=True
            )
            scheduler.start()
            app.config['SCHEDULER'] = scheduler
            app.logger.info("Bill reminder and overdue status scheduler started successfully")
            return scheduler
        except Exception as e:
            app.logger.error(f"Failed to initialize scheduler: {str(e)}", exc_info=True)
            raise RuntimeError(f"Scheduler initialization failed: {str(e)}")
