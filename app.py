import logging
import os
import json
import uuid
from datetime import datetime, timedelta
from flask import Flask, render_template, request, session, redirect, url_for, flash, send_from_directory, has_request_context, g, jsonify
from flask_session import Session
from flask_wtf.csrf import CSRFProtection, CSRFError
from flask_mail import Mail
from translations.translations import trans, get_translations
from translations.translations_quiz import trans as quiz_trans, get_translations as get_quiz_translations
from blueprints.financial_health import financial_health_bp
from blueprints.budget import budget_bp, init_budget_storage
from blueprints.quiz import quiz_bp
from blueprints.bill import bill_bp
from blueprints.net_worth import net_worth_bp
from blueprints.emergency_fund import emergency_fund_bp
from blueprints.learning_hub import learning_hub_bp
from json_store import JsonStorage
import gspread
from google.oauth2.service_account import Credentials
from functools import wraps

# Set up logging
root_logger = logging.getLogger('ficore_app')
root_logger.setLevel(logging.INFO)

class SessionFormatter(logging.Formatter):
    def format(self, record):
        record.session_id = getattr(record, 'session_id', 'no-session-id')
        return super().format(record)

formatter = SessionFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s [session: %(session_id)s]')

os.makedirs('data', exist_ok=True)
file_handler = logging.FileHandler('data/storage.log')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
root_logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

class SessionAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        kwargs['extra'] = kwargs.get('extra', {})
        kwargs['extra']['session_id'] = session.get('sid', 'no-session-id') if has_request_context() else 'no-request-context'
        return msg, kwargs

logger = SessionAdapter(root_logger, {})

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a_fallback-secret-key-for-dev-only-change-me')
    if not app.config['SECRET_KEY']:
        logger.critical("FLASK_SECRET_KEY not set. Using insecure default!")

    # Configure Flask-Mail
    app.config.update({
        'MAIL_SERVER': os.environ.get('MAIL_SERVER', 'smtp.gmail.com'),
        'MAIL_PORT': int(os.environ.get('MAIL_PORT', 587)),
        'MAIL_USE_TLS': os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true',
        'MAIL_USERNAME': os.environ.get('MAIL_USERNAME'),
        'MAIL_PASSWORD': os.environ.get('MAIL_PASSWORD'),
        'BASE_URL': os.environ.get('BASE_URL', 'http://localhost:5000')
    })

    mail = Mail(app)
    app.extensions['mail'] = mail

    # Configure session directory
    session_dir = os.environ.get('SESSION_DIR', 'data/sessions')
    if os.environ.get('RENDER'):
        session_dir = '/opt/render/project/src/data/sessions'

    try:
        if os.path.exists(session_dir):
            if not os.path.isdir(session_dir):
                logger.error(f"Session path {session_dir} exists but is not a directory. Attempting to remove and recreate.")
                os.remove(session_dir)
                os.makedirs(session_dir, exist_ok=True)
                logger.info(f"Created session directory at {session_dir}")
        else:
            os.makedirs(session_dir, exist_ok=True)
            logger.info(f"Created session directory at {session_dir}")
    except Exception as e:
        logger.error(f"Failed to create session directory {session_dir}: {str(e)}")
        raise RuntimeError(f"Cannot proceed without session directory: {str(e)}")

    app.config['SESSION_FILE_DIR'] = session_dir
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_SERIALIZER'] = 'json'
    app.config['PREDETERMINED_HEADERS_QUIZ'] = [
        'Timestamp', 'first_name', 'email', 'language',
        'question_1', 'question_2', 'question_3', 'question_4', 'question_5',
        'question_6', 'question_7', 'question_8', 'question_9', 'question_10',
        'answer_1', 'answer_2', 'answer_3', 'answer_4', 'answer_5',
        'answer_6', 'answer_7', 'answer_8', 'answer_9', 'answer_10',
        'personality', 'score', 'badges', 'send_email'
    ]

    Session(app)
    CSRFProtect(app)

    # Initialize Google Sheets client
    def init_gspread_client():
        try:
            creds_json = os.environ.get('GOOGLE_CREDENTIALS')
            if not creds_json:
                logger.warning("GOOGLE_CREDENTIALS not set. Google Sheets integration disabled.")
                return None
            creds = Credentials.from_service_account_info(
                json.loads(creds_json),
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            client = gspread.authorize(creds)
            logger.info("Successfully initialized gspread client")
            return client
        except Exception as e:
            logger.error(f"Failed to initialize gspread client: {str(e)}")
            return None

    app.config['GSPREAD_CLIENT'] = init_gspread_client()

    # Google Sheets storage manager
    class GoogleSheetsStorage:
        def __init__(self, client, worksheet_name='Quiz'):
            self.client = client
            self.worksheet_name = worksheet_name
            self.logger = logger

        def append_to_sheet(self, data, headers, worksheet_name):
            try:
                spreadsheet = self.client.open('Financial_Quiz_Results')
                try:
                    worksheet = spreadsheet.worksheet(worksheet_name)
                except gspread.WorksheetNotFound:
                    worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=len(headers))
                    worksheet.append_row(headers)
                worksheet.append_row(data)
                self.logger.info(f"Appended data to sheet {worksheet_name}")
                return True
            except Exception as e:
                self.logger.error(f"Error appending to sheet {worksheet_name}: {e}")
                return False

        def fetch_data_from_filter(self, headers, worksheet_name):
            try:
                spreadsheet = self.client.open('Financial_Quiz_Results')
                worksheet = spreadsheet.worksheet(worksheet_name)
                data = worksheet.get_all_records()
                import pandas as pd
                return pd.DataFrame(data)
            except Exception as e:
                self.logger.error(f"Error fetching data from sheet {worksheet_name}: {e}")
                return pd.DataFrame()

    # Initialize storage managers
    with app.app_context():
        app.config['STORAGE_MANAGERS'] = {
            'financial_health': JsonStorage('data/financial_health.json', logger_instance=logger),
            'budget': init_budget_storage(app),
            'quiz': JsonStorage('data/quiz_data.json', logger_instance=logger),
            'bills': init_bill_storage(app),
            'net_worth': JsonStorage('data/networth.json', logger_instance=logger),
            'emergency_fund': JsonStorage('data/emergency_fund.json', logger_instance=logger),
            'user_progress': JsonStorage('data/user_progress.json', logger_instance=logger),
            'courses': JsonStorage('data/courses.json', logger_instance=logger),
            'sheets': GoogleSheetsStorage(app.config['GSPREAD_CLIENT']) if app.config['GSPREAD_CLIENT'] else None
        }

        # Initialize courses.json if empty or missing
        courses_storage = app.config['STORAGE_MANAGERS']['courses']
        try:
            courses = courses_storage.read_all()
            if not courses:
                logger.info("Courses storage is empty. Initializing with default courses.")
                default_courses = [
                    {
                        'id': 'budgeting_101',
                        'title_en': 'Budgeting 101',
                        'title_ha': 'Tsarin Kudi 101',
                        'description_en': 'Learn the basics of budgeting.',
                        'description_ha': 'Koyon asalin tsarin kudi.'
                    },
                    {
                        'id': 'financial_quiz',
                        'title_en': 'Financial Quiz',
                        'title_ha': 'Jarabawar Kudi',
                        'description_en': 'Test your financial knowledge.',
                        'description_ha': 'Gwada ilimin ku na kudi.'
                    },
                    {
                        'id': 'savings_basics',
                        'title_en': 'Savings Basics',
                        'title_ha': 'Asalin Tattara Kudi',
                        'description_en': 'Understand how to save effectively.',
                        'description_ha': 'Fahimci yadda ake tattara kudi yadda ya kamata.'
                    }
                ]
                if not courses_storage.create(default_courses):
                    logger.error("Failed to initialize courses.json with default courses")
                    raise RuntimeError("Course initialization failed")
                logger.info(f"Initialized courses.json with {len(default_courses)} default courses")
                courses = courses_storage.read_all()
                if len(courses) != len(default_courses):
                    logger.error(f"Failed to verify courses.json initialization. Expected {len(default_courses)} courses, got {len(courses)}.")
        except PermissionError as e:
            logger.error(f"Permission error initializing courses.json: {str(e)}")
            raise RuntimeError("Cannot write to courses.json due to permissions.")
        except Exception as e:
            logger.error(f"Error initializing courses storage: {str(e)}")
            raise

    # Initialize quiz questions
    with app.app_context():
        init_quiz_questions(app)

    # Add custom Jinja2 filter for translations
    app.jinja_env.filters['trans'] = lambda key, **kwargs: trans(
        key,
        lang=kwargs.get('lang', session.get('language', 'en')),
        logger=g.get('logger', logger) if has_request_context() else logger,
        **{k: v for k, v in kwargs.items() if k != 'lang'}
    )

    # Add quiz-specific translation filter
    app.jinja_env.filters['quiz_trans'] = lambda key, **kwargs: quiz_trans(
        key,
        lang=kwargs.get('lang', session.get('language', 'en')),
        **{k: v for k, v in kwargs.items() if k != 'lang'}
    )

    # Template filter for number formatting
    @app.template_filter('format_number')
    def format_number(value):
        try:
            if isinstance(value, (int, float)):
                return f"{float(value):,.2f}"
            return str(value)
        except (ValueError, TypeError) as e:
            logger.warning(f"Error formatting number {value}: {str(e)}")
            return str(value)

    # Session required decorator
    def session_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'sid' not in session:
                session['sid'] = str(uuid.uuid4())
                logger.info(f"New session ID generated: {session['sid']}")
            return f(*args, **kwargs)
        return decorated_function

    # Before request setup
    @app.before_request
    def before_request_setup():
        if 'sid' not in session:
            session['sid'] = str(uuid.uuid4())
            logger.info(f"New session ID generated: {session['sid']}")
        if 'language' not in session:
            session['language'] = 'en'
            logger.info("Set default language to 'en'")
        g.logger = logger
        g.logger.info(f"Request started for path: {request.path}")
        if not os.path.exists('data/storage.log'):
            g.logger.warning("data/storage.log not found")

    # Context processor for translations
    @app.context_processor
    def inject_translations():
        lang = session.get('language', 'en')
        def context_trans(key, **kwargs):
            translated = trans(key, lang=lang, logger=g.get('logger', logger), **kwargs)
            return translated
        def context_quiz_trans(key, **kwargs):
            translated = quiz_trans(key, lang=lang, **kwargs)
            return translated
        return {
            'trans': context_trans,
            'quiz_trans': context_quiz_trans,
            'current_year': datetime.now().year,
            'LINKEDIN_URL': os.environ.get('LINKEDIN_URL', '#'),
            'TWITTER_URL': os.environ.get('TWITTER_URL', '#'),
            'FACEBOOK_URL': os.environ.get('FACEBOOK_URL', '#'),
            'FEEDBACK_FORM_URL': os.environ.get('FEEDBACK_FORM_URL', '#'),
            'WAITLIST_FORM_URL': os.environ.get('WAITLIST_FORM_URL', '#'),
            'CONSULTANCY_FORM_URL': os.environ.get('CONSULTANCY_FORM_URL', '#'),
            'current_lang': lang
        }

    # Routes
    @app.route('/')
    @session_required
    def index():
        lang = session.get('language', 'en')
        logger.info("Serving index page")
        courses_storage = app.config['STORAGE_MANAGERS']['courses']
        sample_courses = [
            {
                'id': 'budgeting_101',
                'title_key': 'learning_hub_course_budgeting101_title',
                'title_en': 'Budgeting 101',
                'title_ha': 'Tsarin Kudi 101',
                'description_en': 'Learn the basics of budgeting.',
                'description_ha': 'Koyon asalin tsarin kudi.'
            },
            {
                'id': 'financial_quiz',
                'title_key': 'learning_hub_course_financial_quiz_title',
                'title_en': 'Financial Quiz',
                'title_ha': 'Jarabawar Kudi',
                'description_en': 'Test your financial knowledge.',
                'description_ha': 'Gwada ilimin ku na kudi.'
            },
            {
                'id': 'savings_basics',
                'title_key': 'learning_hub_course_savings_basics_title',
                'title_en': 'Savings Basics',
                'title_ha': 'Asalin Tattara Kudi',
                'description_en': 'Understand how to save effectively.',
                'description_ha': 'Fahimci yadda ake tattara kudi yadda ya kamata.'
            }
        ]
        try:
            courses = courses_storage.read_all() if courses_storage else []
            logger.info(f"Retrieved {len(courses)} courses from storage")
            if not courses:
                logger.warning("No courses found in storage. Using sample_courses.")
                courses = sample_courses
            else:
                title_key_map = {c['id']: c['title_key'] for c in sample_courses}
                courses = [
                    {**course, 'title_key': title_key_map.get(course['id'], f"learning_hub_course_{course['id']}_title")}
                    for course in courses
                ]
        except Exception as e:
            logger.error(f"Error retrieving courses: {str(e)}")
            courses = sample_courses
            flash(quiz_trans('learning_hub_error_message', default='An error occurred', lang=lang), 'danger')
        return render_template(
            'index.html',
            t=quiz_trans,
            courses=courses,
            lang=lang,
            sample_courses=sample_courses
        )

    @app.route('/set_language/<lang>')
    @session_required
    def set_language(lang):
        valid_langs = ['en', 'ha']
        new_lang = lang if lang in valid_langs else 'en'
        session['language'] = new_lang
        logger.info(f"Language set to {session['language']}")
        flash(quiz_trans('learning_hub_success_language_updated', default='Language updated successfully', lang=new_lang) if new_lang in valid_langs else quiz_trans('Invalid language', default='Invalid language', lang=new_lang))
        return redirect(request.referrer or url_for('index'))

    @app.route('/favicon.ico')
    def favicon():
        logger.info("Serving favicon.ico")
        return send_from_directory(os.path.join(app.root_path, 'static', 'img'), 'favicon-32x32.png', mimetype='image/png')

    @app.route('/general_dashboard')
    @session_required
    def general_dashboard():
        lang = session.get('language', 'en')
        logger.info("Serving general dashboard")
        data = {}
        expected_keys = {
            'score': None,
            'surplus_deficit': None,
            'personality': None,
            'bills': [],
            'net_worth': None,
            'savings_gap': None
        }
        for tool, storage in app.config['STORAGE_MANAGERS'].items():
            try:
                if storage is None:
                    logger.error(f"Storage for {tool} was not initialized")
                    data[tool] = [] if tool == 'courses' else expected_keys.copy()
                    continue
                records = storage.filter_by_session(session['sid'])
                if tool == 'courses':
                    data[tool] = records
                else:
                    if records:
                        latest_record_raw = records[-1]['data']
                        record_data = latest_record_raw.get('data', latest_record_raw)
                        data[tool] = expected_keys.copy()
                        data[tool].update({k: record_data.get(k, v) for k, v in expected_keys.items()})
                    else:
                        data[tool] = expected_keys.copy()
                logger.info(f"Retrieved {len(records)} records for {tool}")
            except Exception as e:
                logger.error(f"Error fetching data for {tool}: {str(e)}")
                data[tool] = [] if tool == 'courses' else expected_keys.copy()
        learning_progress = session.get('learning_progress', {})
        data['learning_progress'] = learning_progress if isinstance(learning_progress, dict) else {}
        return render_template('general_dashboard.html', data=data, t=quiz_trans, lang=lang)

    @app.route('/logout')
    @session_required
    def logout():
        logger.info("Logging out user")
        lang = session.get('language', 'en')
        session.clear()
        session['language'] = lang
        flash(quiz_trans('learning_hub_success_logout', default='Successfully logged out', lang=lang))
        return redirect(url_for('index'))

    @app.route('/health')
    @session_required
    def health():
        lang = session.get('language', 'en')
        logger.info("Health check requested")
        status = {"status": "healthy"}
        try:
            for tool, storage in app.config['STORAGE_MANAGERS'].items():
                if storage is None:
                    status["status"] = "unhealthy"
                    status["details"] = f"Storage for {tool} failed to initialize"
                    return jsonify(status), 500
            if app.config['GSPREAD_CLIENT'] is None:
                status["status"] = "unhealthy"
                status["details"] = "Google Sheets client not initialized"
                return jsonify(status), 500
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            status["status"] = "unhealthy"
            status["details"] = str(e)
            return jsonify(status), 500
        return jsonify(status), 200

    # Error handlers
    @app.errorhandler(Exception)
    def handle_global_error(e):
        lang = session.get('language', 'en')
        logger.error(f"Global error: {str(e)}")
        flash(quiz_trans('global_error_message', default='An error occurred', lang=lang), 'danger')
        return render_template('index.html', error=quiz_trans('global_error_message', default='An error occurred', lang=lang), t=quiz_trans, lang=lang), 500

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        lang = session.get('language', 'en')
        logger.error(f"CSRF error: {str(e)}")
        flash(quiz_trans('csrf_error', default='Invalid CSRF token', lang=lang), 'danger')
        return render_template('index.html', error=quiz_trans('csrf_error', default='Invalid CSRF token', lang=lang), t=quiz_trans, lang=lang), 400

    @app.errorhandler(404)
    def page_not_found(e):
        lang = session.get('language', 'en')
        logger.error(f"404 error: {str(e)}")
        return render_template('404.html', t=quiz_trans, lang=lang), 404

    # Register blueprints
    app.register_blueprint(financial_health_bp)
    app.register_blueprint(budget_bp)
    app.register_blueprint(quiz_bp)
    app.register_blueprint(bill_bp)
    app.register_blueprint(net_worth_bp)
    app.register_blueprint(emergency_fund_bp)
    app.register_blueprint(learning_hub_bp)

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
