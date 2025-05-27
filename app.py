import logging
import os
import json
import uuid
from datetime import datetime, timedelta
from flask import Flask, render_template, request, session, redirect, url_for, flash, send_from_directory, has_request_context, g, jsonify
from flask_session import Session
from flask_wtf.csrf import CSRFProtect, CSRFError
from translations import trans, get_translations
from blueprints.financial_health import financial_health_bp
from blueprints.budget import budget_bp, init_budget_storage
from blueprints.quiz import quiz_bp, init_quiz_questions
from blueprints.bill import bill_bp, init_bill_storage
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
file_handler = logging.FileHandler('data/storage.txt')
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

log = SessionAdapter(root_logger, {})

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a_fallback_secret_key_for_dev_only_change_me')
    if not app.secret_key:
        log.critical("FLASK_SECRET_KEY not set. Using insecure default!")

    # Configure session directory
    session_dir = os.environ.get('SESSION_DIR', 'data/sessions')
    if os.environ.get('RENDER'):
        session_dir = '/opt/render/project/src/data/sessions'

    try:
        if os.path.exists(session_dir):
            if not os.path.isdir(session_dir):
                log.error(f"Session path {session_dir} exists but is not a directory. Attempting to remove and recreate.")
                os.remove(session_dir)
                os.makedirs(session_dir, exist_ok=True)
                log.info(f"Created session directory at {session_dir}")
        else:
            os.makedirs(session_dir, exist_ok=True)
            log.info(f"Created session directory at {session_dir}")
    except Exception as e:
        log.error(f"Failed to create session directory {session_dir}: {str(e)}")
        raise RuntimeError(f"Cannot proceed without session directory: {str(e)}")

    app.config['SESSION_FILE_DIR'] = session_dir
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_SERIALIZER'] = 'json'
    Session(app)
    CSRFProtect(app)

    # Initialize Google Sheets client
    def init_gspread_client():
        try:
            creds_json = os.environ.get('GOOGLE_CREDENTIALS')
            if not creds_json:
                log.warning("GOOGLE_CREDENTIALS not set. Google Sheets integration disabled.")  # Changed to warning
                return None
            creds = Credentials.from_service_account_info(
                json.loads(creds_json),
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            client = gspread.authorize(creds
            log.info("Successfully initialized gspread client")
            return client
        except Exception as e:
            log.error(f"Failed to initialize gspread client: {str(e)}")
            return None

    app.config['GSPREAD_CLIENT'] = init_gspread_client()

    # Initialize storage managers
    with app.app_context():
        app.config['STORAGE_MANAGERS'] = {
            'financial_health': JsonStorage('data/financial_health.json', logger_instance=log),
            'budget': init_budget_storage(app),
            'quiz': JsonStorage('data/quiz_data.json', logger_instance=log),
            'bills': init_bill_storage(app),
            'net_worth': JsonStorage('data/netsworth.json', logger_instance=log),
            'emergency_fund': JsonStorage('data/emergency_fund.json', logger_instance=log),
            'user_progress': JsonStorage('data/user_progress.json', logger_instance=log),
            'courses': JsonStorage('data/courses.json', logger_instance=log),
        }

    # Initialize courses.json if empty or missing
    courses_storage = app.config['STORAGE_MANAGERS']['courses']
    try:
        courses = courses.read_all()
        if not courses:
            log.info("Courses storage is empty. Initializing with default courses.")
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
                log.error("Failed to initialize courses.json with default courses")
                raise RuntimeError("Course initialization failed")
            log.info(f"Initialized courses.json with {len(default_courses)} default courses")
            # Verify write
            courses = courses_storage.read_all()
            if len(courses) != len(default_courses):
                log.error(f"Failed to verify courses.json initialization. Expected {len(default_courses)} courses, got {len(courses)}.")
    except PermissionError as e:
            log.error(f"Permission error initializing courses.json: {str(e)}")
            raise RuntimeError("Cannot write to courses.json due to permissions.")
    except Exception as e:
            log.error(f"Error initializing courses storage: {str(e)}")
            raise

    # Initialize quiz questions
    with app.app_context():
        init_quiz_questions(app)

    # Template filter for number formatting
    @app.template_filter('format_number')
    def format_number(value):
        try:
            if isinstance(value, (int, float)):
                return f"{float(value):,.2f}"
            return str(value)
        except (ValueError, TypeError) as e:
            log.warning(f"Error formatting number {value}: {str(e)}")
            return str(value)

    # Session required decorator
    def session_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'sid' not in session:
                session['sid'] = str(uuid.uuid4())
                log.info(f"New session ID generated: {session['sid']}")
            return f(*args, **kwargs)
        return decorated_function

    # Before request setup
    @app.before_request
    def before_request_setup():
        if 'sid' not in session:
            session['sid'] = str(uuid.uuid4())
            log.info(f"New session ID generated: {session['sid']}")
        if 'lang' not in session:
            session['lang'] = 'en'
        g.log = log
        g.log.info(f"Request started for path: {request.path}")
        if not os.path.exists('data/storage.txt'):
            g.log.warning("data/storage.txt not found")

    # Context processor for translations
    @app.context_processor
    def inject_translations():
        lang = session.get('lang', 'en')
        def context_trans(key, **kwargs):
            translated = trans(key, lang=lang, **kwargs)
            return translated
        return {
            'trans': context_trans,
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
        lang = session.get('lang', 'en')
        log.info("Serving index page")
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
                'id': 'savings_basics',  # Fixed typo: 'savings_bas' -> 'savings_basics'
                'title_key': 'learning_hub_course_savings_basics_title',
                'title_en': 'Savings Basics',
                'title_ha': 'Asalin Tattara Kudi',
                'description_en': 'Understand how to save effectively.',
                'description_ha': 'Fahimci yadda ake tattara kudi yadda ya kamata.'
            }
        ]
        try:
            courses = courses_storage.read_all() if courses_storage else []
            log.info(f"Retrieved {len(courses)} courses from storage")
            if not courses:
                log.warning("No courses found in storage. Using sample_courses.")
                courses = sample_courses
            else:
                # Add title_key to courses from courses.json to match sample_courses
                title_key_map = {c['id']: c['title_key'] for c in sample_courses}
                courses = [
                    {**course, 'title_key': title_key_map.get(course['id'], f"learning_hub_course_{course['id']}_title")}
                    for course in courses
                ]
        except Exception as e:
            log.error(f"Error retrieving courses: {str(e)}")
            courses = sample_courses
            flash(trans('learning_hub_error_message', default='An error occurred'), 'danger')
        return render_template(
            'index.html',
            t=trans,
            courses=courses,
            lang=lang,
            sample_courses=sample_courses
        )

    @app.route('/set_language/<lang>')
    @session_required
    def set_language(lang):
        valid_langs = ['en', 'ha']
        session['lang'] = lang if lang in valid_langs else 'en'
        log.info(f"Language set to {session['lang']}")
        flash(trans('learning_hub_language_changed', default='Language changed') if session['lang'] in valid_langs else trans('learning_hub_invalid_language', default='Invalid language'))
        return redirect(request.referrer or url_for('index'))

    @app.route('/favicon.ico')
    def favicon():
        log.info("Serving favicon.ico")
        return send_from_directory(os.path.join(app.root_path, 'static', 'img'), 'favicon-32x32.png', mimetype='image/png')

    @app.route('/general_dashboard')
    @session_required
    def general_dashboard():
        lang = session.get('lang', 'en')
        log.info("Serving general dashboard")
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
                    log.error(f"Storage for {tool} was not initialized")
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
                log.info(f"Retrieved {len(records)} records for {tool}")
            except Exception as e:
                log.error(f"Error fetching data for {tool}: {str(e)}")
                data[tool] = [] if tool == 'courses' else expected_keys.copy()
        learning_progress = session.get('learning_progress', {})
        data['learning_progress'] = learning_progress if isinstance(learning_progress, dict) else {}
        return render_template('general_dashboard.html', data=data, t=trans, lang=lang)

    @app.route('/logout')
    @session_required
    def logout():
        log.info("Logging out user")
        lang = session.get('lang', 'en')
        session.clear()
        session['lang'] = lang
        flash(trans('learning_hub_logged_out', default='Successfully logged out'))
        return redirect(url_for('index'))

    @app.route('/health')
    @session_required
    def health():
        log.info("Health check requested")
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
            log.error(f"Health check failed: {str(e)}")
            status["status"] = "unhealthy"
            status["details"] = str(e)
            return jsonify(status), 500
        return jsonify(status), 200

    # Error handlers
    @app.errorhandler(Exception)
    def handle_global_error(e):
        lang = session.get('lang', 'en')
        log.error(f"Global error: {str(e)}")
        flash(trans('global_error_message', default='An error occurred'), 'danger')
        return render_template('index.html', error=trans('global_error_message', default='An error occurred'), t=trans, lang=lang), 500

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        lang = session.get('lang', 'en')
        log.error(f"CSRF error: {str(e)}")
        flash(trans('csrf_error', default='Invalid CSRF token'), 'danger')
        return render_template('index.html', error=trans('csrf_error', default='Invalid CSRF token'), t=trans, lang=lang), 400

    @app.errorhandler(404)
    def page_not_found(e):
        lang = session.get('lang', 'en')
        log.error(f"404 error: {str(e)}")
        return render_template('404.html', error=trans('page_not_found', default='Page not found'), t=trans, lang=lang), 404

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
    app.run(debug=True, host='0.0.0.0', port=10000)
