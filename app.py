import logging
import os
import sys
import json
import uuid
from datetime import datetime, timedelta
from flask import Flask, render_template, request, session, redirect, url_for, flash, send_from_directory, has_request_context, g, jsonify, current_app
from flask_session import Session
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_mail import Mail
from translations import trans, get_translations
from translations.translations_quiz import trans as quiz_trans, get_translations as get_quiz_translations
from blueprints.financial_health import financial_health_bp
from blueprints.budget import budget_bp, init_budget_storage
from blueprints.quiz import quiz_bp, init_quiz_questions
from blueprints.bill import bill_bp, init_bill_storage
from blueprints.net_worth import net_worth_bp
from blueprints.emergency_fund import emergency_fund_bp
from blueprints.learning_hub import learning_hub_bp, initialize_courses
from json_store import JsonStorage
import gspread
from google.oauth2.service_account import Credentials
from functools import wraps
import pandas as pd

# Constants
SAMPLE_COURSES = [
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

# Set up logging
root_logger = logging.getLogger('ficore_app')
root_logger.setLevel(logging.DEBUG)

class SessionFormatter(logging.Formatter):
    def format(self, record):
        record.session_id = getattr(record, 'session_id', 'no_session_id')
        return super().format(record)

formatter = SessionFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s [session: %(session_id)s]')

class SessionAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        kwargs['extra'] = kwargs.get('extra', {})
        session_id = kwargs['extra'].get('session_id', 'no-session-id')
        if has_request_context() and 'session_id' not in kwargs['extra']:
            session_id = session.get('sid', 'no-session-id')
        kwargs['extra']['session_id'] = session_id
        return msg, kwargs

logger = SessionAdapter(root_logger, {})

def setup_logging(app):
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    app.logger.handlers = [handler]
    app.logger.setLevel(logging.INFO)
    os.makedirs('data', exist_ok=True)
    file_handler = logging.FileHandler('data/storage.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    app.logger.addHandler(file_handler)
    app.logger = logger  # Replace with SessionAdapter

def setup_session(app):
    session_dir = os.environ.get('SESSION_DIR', 'data/sessions')
    if os.environ.get('RENDER'):
        session_dir = '/opt/render/project/src/data/sessions'
    try:
        if os.path.exists(session_dir):
            if not os.path.isdir(session_dir):
                logger.error(f"Session path {session_dir} exists but is not a directory. Attempting to remove and recreate.", extra={'session_id': 'init'})
                try:
                    os.remove(session_dir)
                except OSError as e:
                    logger.error(f"Failed to remove {session_dir}: {str(e)}", extra={'session_id': 'init'})
                    raise RuntimeError(f"Cannot remove session path: {str(e)}")
                os.makedirs(session_dir, exist_ok=True)
                logger.info(f"Created session directory at {session_dir}", extra={'session_id': 'init'})
        else:
            os.makedirs(session_dir, exist_ok=True)
            logger.info(f"Created session directory at {session_dir}", extra={'session_id': 'init'})
    except (PermissionError, OSError) as e:
        logger.warning(f"Failed to create session directory {session_dir}: {str(e)}. Falling back to in-memory sessions.", extra={'session_id': 'init'})
        app.config['SESSION_TYPE'] = 'null'
    app.config['SESSION_FILE_DIR'] = session_dir
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
    app.config['SESSION_USE_SIGNER'] = True

def init_gspread_client():
    try:
        creds_json = os.environ.get('GOOGLE_CREDENTIALS')
        if not creds_json:
            logger.warning("GOOGLE_CREDENTIALS not set. Google Sheets integration disabled.", extra={'session_id': 'init'})
            return None
        creds_info = json.loads(creds_json)
        creds = Credentials.from_service_account_info(
            creds_info,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(creds)
        logger.info("Successfully initialized gspread client", extra={'session_id': 'init'})
        return client
    except Exception as e:
        logger.error(f"Failed to initialize gspread client: {str(e)}", extra={'session_id': 'init'})
        return None

def init_storage_managers(app):
    storage_managers = {}
    for name, path in [
        ('financial_health', 'data/financial_health.json'),
        ('user_progress', 'data/user_progress.json'),
        ('quiz', 'data/quiz_data.json'),
        ('net_worth', 'data/networth.json'),
        ('emergency_fund', 'data/emergency_fund.json'),
        ('courses', 'data/courses.json')
    ]:
        try:
            logger.info(f"Initializing {name} storage", extra={'session_id': 'init'})
            storage_managers[name] = JsonStorage(path, logger_instance=logger)
        except (PermissionError, OSError) as e:
            logger.error(f"Failed to initialize {name} storage: {str(e)}", extra={'session_id': 'init'}, exc_info=True)
            storage_managers[name] = {}
    try:
        logger.info("Initializing budget storage", extra={'session_id': 'init'})
        storage_managers['budget'] = init_budget_storage(app)
    except (PermissionError, OSError) as e:
        logger.error(f"Failed to initialize budget storage: {str(e)}", extra={'session_id': 'init'}, exc_info=True)
        storage_managers['budget'] = {}
    try:
        logger.info("Initializing bills storage", extra={'session_id': 'init'})
        storage_managers['bills'] = init_bill_storage(app)
    except (PermissionError, OSError) as e:
        logger.error(f"Failed to initialize bills storage: {str(e)}", extra={'session_id': 'init'}, exc_info=True)
        storage_managers['bills'] = {}
    try:
        logger.info("Initializing sheets storage", extra={'session_id': 'init'})
        storage_managers['sheets'] = GoogleSheetsStorage(app.config['GSPREAD_CLIENT']) if app.config['GSPREAD_CLIENT'] else None
    except (PermissionError, OSError) as e:
        logger.error(f"Failed to initialize sheets storage: {str(e)}", extra={'session_id': 'init'}, exc_info=True)
        storage_managers['sheets'] = None
    app.config['STORAGE_MANAGERS'] = storage_managers

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a_fallback-secret-key-for-dev-only-change-me')
    if not os.environ.get('FLASK_SECRET_KEY') and not app.debug:
        raise RuntimeError("FLASK_SECRET_KEY must be set in production")

    setup_logging(app)
    setup_session(app)
    app.config['GSPREAD_CLIENT'] = init_gspread_client()
    init_storage_managers(app)
    app.config.update({
        'MAIL_SERVER': os.environ.get('MAIL_SERVER', 'smtp.gmail.com'),
        'MAIL_PORT': int(os.environ.get('MAIL_PORT', 587)),
        'MAIL_USE_TLS': os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true',
        'MAIL_USERNAME': os.environ.get('MAIL_USERNAME'),
        'MAIL_PASSWORD': os.environ.get('MAIL_PASSWORD'),
        'BASE_URL': os.environ.get('BASE_URL', 'http://localhost:5000'),
        'PREDETERMINED_HEADERS_QUIZ': [
            'Timestamp', 'first_name', 'email', 'language',
            'question_1', 'question_2', 'question_3', 'question_4', 'question_5',
            'question_6', 'question_7', 'question_8', 'question_9', 'question_10',
            'answer_1', 'answer_2', 'answer_3', 'answer_4', 'answer_5',
            'answer_6', 'answer_7', 'answer_8', 'answer_9', 'answer_10',
            'personality', 'score', 'badges', 'send_email'
        ]
    })
    mail = Mail(app)
    app.extensions['mail'] = mail
    Session(app)
    CSRFProtect(app)

    # Initialize storage managers and other context-dependent operations
    with app.app_context():
        logger.info("Starting initialization", extra={'session_id': 'init'})
        try:
            courses_storage = current_app.config['STORAGE_MANAGERS']['courses']
            if not isinstance(courses_storage, dict):
                courses = courses_storage.read_all(session_id='init')
                if not courses:
                    logger.info("Courses storage is empty. Initializing with default courses.", extra={'session_id': 'init'})
                    if not courses_storage.create(SAMPLE_COURSES, session_id='init'):
                        logger.error("Failed to initialize courses.json with default courses", extra={'session_id': 'init'}, exc_info=True)
                        raise RuntimeError("Course initialization failed")
                    logger.info(f"Initialized courses.json with {len(SAMPLE_COURSES)} default courses", extra={'session_id': 'init'})
                    app.config['COURSES'] = courses_storage.read_all(session_id='init')
                else:
                    app.config['COURSES'] = courses
            else:
                app.config['COURSES'] = SAMPLE_COURSES
        except Exception as e:
            logger.error(f"Error initializing courses: {str(e)}", extra={'session_id': 'init'}, exc_info=True)
            app.config['COURSES'] = SAMPLE_COURSES
            raise

        logger.info("Initializing learning hub courses", extra={'session_id': 'init'})
        try:
            initialize_courses(app)
        except PermissionError as e:
            logger.error(f"Permission error initializing learning hub courses: {str(e)}", extra={'session_id': 'init'}, exc_info=True)
            raise RuntimeError("Cannot initialize learning hub courses due to permissions.")
        except Exception as e:
            logger.error(f"Error initializing learning hub courses: {str(e)}", extra={'session_id': 'init'}, exc_info=True)
            raise

        logger.info("Initializing quiz questions", extra={'session_id': 'init'})
        try:
            init_quiz_questions(app)
        except PermissionError as e:
            logger.error(f"Permission error initializing quiz questions: {str(e)}", extra={'session_id': 'init'}, exc_info=True)
            raise RuntimeError("Cannot initialize quiz questions due to permissions.")
        except Exception as e:
            logger.error(f"Error initializing quiz questions: {str(e)}", extra={'session_id': 'init'}, exc_info=True)
            raise

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
            logger.warning(f"Error formatting number {value}: {str(e)}", extra={'session_id': 'no-request-context'})
            return str(value)

    # Before request setup
    @app.before_request
    def setup_session_and_language():
        if 'sid' not in session:
            session['sid'] = str(uuid.uuid4())
            logger.info(f"New session ID generated: {session['sid']}", extra={'session_id': session['sid']})
        if 'language' not in session:
            session['language'] = request.accept_languages.best_match(['en', 'ha'], 'en')
            logger.info(f"Set default language to {session['language']}", extra={'session_id': session['sid']})
        g.logger = logger
        g.logger.info(f"Request started for path: {request.path}", extra={'session_id': session['sid']})
        if not os.path.exists('data/storage.log'):
            g.logger.warning("data/storage.log not found", extra={'session_id': session['sid']})

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
    def index():
        lang = session.get('language', 'en')
        logger.info("Serving index page", extra={'session_id': session.get('sid', 'no-session-id')})
        courses_storage = current_app.config['STORAGE_MANAGERS']['courses']
        try:
            courses = current_app.config['COURSES'] if current_app.config['COURSES'] else SAMPLE_COURSES
            logger.info(f"Retrieved {len(courses)} courses from cache", extra={'session_id': session.get('sid', 'no-session-id')})
            title_key_map = {c['id']: c['title_key'] for c in SAMPLE_COURSES}
            courses = [
                {**course, 'title_key': title_key_map.get(course['id'], f"learning_hub_course_{course['id']}_title")}
                for course in courses
            ]
        except Exception as e:
            logger.error(f"Error retrieving courses: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')}, exc_info=True)
            courses = SAMPLE_COURSES
            flash(quiz_trans('learning_hub_error_message', default='An error occurred', lang=lang), 'danger')
        return render_template(
            'index.html',
            t=quiz_trans,
            courses=courses,
            lang=lang,
            sample_courses=SAMPLE_COURSES
        )

    @app.route('/set_language/<lang>')
    def set_language(lang):
        valid_langs = ['en', 'ha']
        new_lang = lang if lang in valid_langs else 'en'
        session['language'] = new_lang
        logger.info(f"Language set to {session['language']}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(quiz_trans('learning_hub_success_language_updated', default='Language updated successfully', lang=new_lang) if new_lang in valid_langs else quiz_trans('Invalid language', default='Invalid language', lang=new_lang), 'success' if new_lang in valid_langs else 'danger')
        return redirect(request.referrer or url_for('index'))

    @app.route('/favicon.ico')
    def favicon():
        logger.info("Serving favicon.ico", extra={'session_id': 'no-request-context'})
        return send_from_directory(os.path.join(app.root_path, 'static', 'img'), 'favicon-32x32.png', mimetype='image/png')

    @app.route('/general_dashboard')
    def general_dashboard():
        lang = session.get('language', 'en')
        logger.info("Serving general dashboard", extra={'session_id': session.get('sid', 'no-session-id')})
        data = {}
        expected_keys = {
            'score': None,
            'surplus_deficit': None,
            'personality': None,
            'bills': [],
            'net_worth': None,
            'savings_gap': None
        }
        for tool, storage in current_app.config['STORAGE_MANAGERS'].items():
            try:
                if storage is None or isinstance(storage, dict):
                    logger.error(f"Storage for {tool} was not initialized or is in-memory", extra={'session_id': session.get('sid', 'no-session-id')})
                    data[tool] = [] if tool == 'courses' else expected_keys.copy()
                    continue
                records = storage.filter_by_session(session['sid']) if not isinstance(storage, dict) else []
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
                logger.info(f"Retrieved {len(records)} records for {tool}", extra={'session_id': session.get('sid', 'no-session-id')})
            except Exception as e:
                logger.error(f"Error fetching data for {tool}: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')}, exc_info=True)
                data[tool] = [] if tool == 'courses' else expected_keys.copy()
        learning_progress = session.get('learning_progress', {})
        data['learning_progress'] = learning_progress if isinstance(learning_progress, dict) else {}
        return render_template('general_dashboard.html', data=data, t=quiz_trans, lang=lang)

    @app.route('/logout')
    def logout():
        logger.info("Logging out user", extra={'session_id': session.get('sid', 'no-session-id')})
        lang = session.get('language', 'en')
        session.clear()
        session['language'] = lang
        flash(quiz_trans('learning_hub_success_logout', default='Successfully logged out', lang=lang), 'success')
        return redirect(url_for('index'))

    @app.route('/health')
    def health():
        logger.info("Health check requested", extra={'session_id': session.get('sid', 'no-session-id')})
        status = {"status": "healthy"}
        try:
            for tool, storage in current_app.config['STORAGE_MANAGERS'].items():
                if storage is None or isinstance(storage, dict):
                    status["status"] = "unhealthy"
                    status["details"] = f"Storage for {tool} failed to initialize or is in-memory"
                    return jsonify(status), 500
            if current_app.config['GSPREAD_CLIENT'] is None:
                status["status"] = "unhealthy"
                status["details"] = "Google Sheets client not initialized"
                return jsonify(status), 500
            if not os.path.exists('data/storage.log'):
                status["status"] = "warning"
                status["details"] = "Log file data/storage.log not found"
                return jsonify(status), 200
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')}, exc_info=True)
            status["status"] = "unhealthy"
            status["details"] = str(e)
            return jsonify(status), 500
        return jsonify(status), 200

    # Error handlers
    @app.errorhandler(500)
    def internal_error(error):
        lang = session.get('language', 'en')
        logger.error(f"Server error: {str(error)}", exc_info=True, extra={'session_id': session.get('sid', 'no-session-id')})
        flash(quiz_trans('global_error_message', default='An error occurred', lang=lang), 'danger')
        return render_template('500.html', error=str(error), t=quiz_trans, lang=lang), 500

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        lang = session.get('language', 'en')
        logger.warning(f"CSRF error: {str(error)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(quiz_trans('csrf_error', default='Invalid CSRF token', lang=lang), 'danger')
        return render_template('error.html', error="Invalid CSRF token", t=quiz_trans, lang=lang), 400

    @app.errorhandler(404)
    def page_not_found(error):
        lang = session.get('language', 'en')
        logger.error(f"404 error: {str(error)}", extra={'session_id': session.get('sid', 'no-session-id')})
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

class GoogleSheetsStorage:
    def __init__(self, client, worksheet_name='Quiz'):
        self.client = client
        self.worksheet_name = worksheet_name
        self.logger = logger

    def append_to_sheet(self, data, headers, worksheet_name, session_id=None):
        current_session_id = session_id or (session.get('sid', 'no-request-context') if has_request_context() else 'no-request-context')
        try:
            spreadsheet = self.client.open('Financial_Quiz_Results')
            try:
                worksheet = spreadsheet.worksheet(worksheet_name)
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=len(headers))
                worksheet.append_row(headers)
            worksheet.append_row(data)
            self.logger.info(f"Appended data to sheet {worksheet_name} (data length: {len(data)})", extra={'session_id': current_session_id})
            return True
        except Exception as e:
            self.logger.error(f"Error appending to sheet {worksheet_name}: {e}", extra={'session_id': current_session_id})
            return False

    def fetch_data_from_filter(self, headers, worksheet_name, session_id=None):
        current_session_id = session_id or (session.get('sid', 'no-request-context') if has_request_context() else 'no-request-context')
        try:
            spreadsheet = self.client.open('Financial_Quiz_Results')
            worksheet = spreadsheet.worksheet(worksheet_name)
            data = worksheet.get_all_records()
            return pd.DataFrame(data)
        except Exception as e:
            self.logger.error(f"Error fetching data from sheet {worksheet_name}: {e}", extra={'session_id': current_session_id})
            return pd.DataFrame()

# Create app with error handling
try:
    app = create_app()
except Exception as e:
    logger.critical(f"Error creating app: {str(e)}", exc_info=True)
    raise

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
