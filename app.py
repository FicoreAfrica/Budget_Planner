import logging
import os
import json
import uuid
from datetime import datetime, timedelta
from flask import Flask, render_template, request, session, redirect, url_for, flash, send_from_directory, has_request_context, g, jsonify
from flask_session import Session
from flask_wtf.csrf import CSRFProtect, CSRFError
from functools import wraps
from translations import trans, get_translations
from blueprints.financial_health import financial_health_bp
from blueprints.budget import budget_bp
from blueprints.quiz import quiz_bp
from blueprints.bill import bill_bp
from blueprints.net_worth import net_worth_bp
from blueprints.emergency_fund import emergency_fund_bp
from blueprints.courses import courses_bp
from json_store import JsonStorage
import gspread
from google.oauth2.service_account import Credentials

# Set up logging
root_logger = logging.getLogger('ficore_app')
root_logger.setLevel(logging.DEBUG)

class SessionFormatter(logging.Formatter):
    def format(self, record):
        record.session_id = getattr(record, 'session_id', 'no-session-id')
        return super().format(record)

formatter = SessionFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s [session: %(session_id)s]')

os.makedirs('data', exist_ok=True)
file_handler = logging.FileHandler('data/storage.txt')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
root_logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

class SessionAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        kwargs['extra'] = kwargs.get('extra', {})
        kwargs['extra']['session_id'] = session.get('sid', 'no-session-id') if has_request_context() else 'no-request-context'
        return msg, kwargs

log = SessionAdapter(root_logger, {})

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a_fallback_secret_key_for_dev_only_change_me')
if not app.secret_key:
    log.critical("FLASK_SECRET_KEY not set. Using insecure default!")

# Configure session directory
session_dir = os.environ.get('SESSION_DIR', 'data/sessions')
if os.environ.get('RENDER'):
    session_dir = '/opt/render/project/src/data/sessions'
os.makedirs(session_dir, exist_ok=True)
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
            log.error("GOOGLE_CREDENTIALS not set")
            return None
        creds = Credentials.from_service_account_info(
            json.loads(creds_json),
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(creds)
        log.info("Initialized gspread client")
        return client
    except Exception as e:
        log.error(f"Failed to initialize gspread client: {str(e)}")
        return None

app.config['GSPREAD_CLIENT'] = init_gspread_client()

# Initialize storage managers
def init_storage_managers():
    storage_managers = {}
    tools = [
        ('financial_health', 'data/financial_health.json'),
        ('budget', 'data/budget.json'),
        ('quiz', 'data/quiz_data.json'),
        ('bills', 'data/bills.json'),
        ('net_worth', 'data/networth.json'),
        ('emergency_fund', 'data/emergency_fund.json'),
        ('courses', 'data/courses.json'),
        ('user_progress', 'data/user_progress.json')
    ]
    for tool, path in tools:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            storage = JsonStorage(path, logger_instance=log)
            log.info(f"Initialized JsonStorage for {tool} at {path}")
            storage_managers[tool] = storage
        except Exception as e:
            log.error(f"Failed to initialize JsonStorage for {tool} at {path}: {str(e)}")
            storage_managers[tool] = None
    return storage_managers

app.config['STORAGE_MANAGERS'] = init_storage_managers()

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
    g.log.debug(f"Current directory: {os.getcwd()}")
    g.log.debug(f"Directory contents: {os.listdir('.')}")
    if not os.path.exists('data/storage.txt'):
        g.log.warning("data/storage.txt not found")

# Context processor for translations
@app.context_processor
def inject_translations():
    lang = session.get('lang', 'en')
    def context_trans(key, **kwargs):
        translated = trans(key, lang=lang, **kwargs)
        log.debug(f"Translating key='{key}' in lang='{lang}' to '{translated}'")
        return translated
    log.debug("Injecting translations and context variables")
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
    try:
        courses = courses_storage.read_all() if courses_storage else []
        log.debug(f"Retrieved {len(courses)} courses")
    except Exception as e:
        log.error(f"Error retrieving courses: {str(e)}")
        courses = []
        flash(trans('core_error_message'), 'danger')
        print("Index route accessed")  # Should appear in your console/logs
    # --- FIX: Provide sample_courses for the featured section ---
    sample_courses = [
        {
            'id': 'budgeting_101',
            'title_key': 'course_budgeting_101_title',
            'title_en': 'Budgeting 101'
        },
        {
            'id': 'financial_quiz',
            'title_key': 'course_financial_quiz_title',
            'title_en': 'Financial Personality Quiz'
        },
        {
            'id': 'savings_basics',
            'title_key': 'course_savings_basics_title',
            'title_en': 'Savings Basics'
        }
        # Add more sample courses as needed
    ]
    return render_template(
        'index.html',
        t=trans,
        courses=courses,
        lang=lang,
        sample_courses=sample_courses  # <---- THIS FIXES THE FEATURED SECTION
    )
@app.route('/set_language/<lang>')
@session_required
def set_language(lang):
    valid_langs = ['en', 'ha']
    session['lang'] = lang if lang in valid_langs else 'en'
    log.info(f"Language set to {session['lang']}")
    flash(trans('core_language_changed') if session['lang'] in valid_langs else trans('core_invalid_language'))
    return redirect(request.referrer or url_for('index'))

@app.route('/favicon.ico')
def favicon():
    log.debug("Serving favicon.ico")
    return send_from_directory(os.path.join(app.root_path, 'static', 'img'), 'favicon-32x32.png', mimetype='image/png')

@app.route('/general_dashboard')
@session_required
def general_dashboard():
    lang = session.get('lang', 'en')
    log.info("Serving general_dashboard")
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
                data[tool] = [ рекорд['data'] for record in records]
            else:
                if records:
                    latest_record_raw = records[-1]['data']
                    record_data = latest_record_raw.get('data', latest_record_raw)
                    data[tool] = expected_keys.copy()
                    data[tool].update({k: record_data.get(k, v) for k, v in expected_keys.items()})
                else:
                    data[tool] = expected_keys.copy()
            log.debug(f"Data for {tool}: {data[tool]}")
        except Exception as e:
            log.exception(f"Error fetching data for {tool}: {str(e)}")
            data[tool] = [] if tool == 'courses' else expected_keys.copy()
    return render_template('general_dashboard.html', data=data, t=trans, lang=lang)

@app.route('/logout')
@session_required
def logout():
    log.info("Logging out user")
    lang = session.get('lang', 'en')
    session.clear()
    session['lang'] = lang  # Preserve language after logout
    flash(trans('core_logged_out'))
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
    log.exception(f"Global error: {str(e)}")
    flash(trans('core_error_message'), 'danger')
    return render_template('500.html', error=trans('core_error_message'), t=trans, lang=lang), 500

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    lang = session.get('lang', 'en')
    log.error(f"CSRF Error: {str(e)}")
    flash(trans('core_csrf_error'), 'danger')
    return render_template('500.html', error=trans('core_csrf_error'), t=trans, lang=lang), 400

@app.errorhandler(404)
def page_not_found(e):
    lang = session.get('lang', 'en')
    log.error(f"404 Error: {str(e)}")
    return render_template('404.html', error=trans('core_page_not_found'), t=trans, lang=lang), 404

# Register blueprints
app.register_blueprint(financial_health_bp)
app.register_blueprint(budget_bp)
app.register_blueprint(quiz_bp)
app.register_blueprint(bill_bp)
app.register_blueprint(net_worth_bp)
app.register_blueprint(emergency_fund_bp)
app.register_blueprint(courses_bp)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=10000)
