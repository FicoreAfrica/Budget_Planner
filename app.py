import uuid
from datetime import datetime, timedelta
from flask import Flask, render_template, request, session, redirect, url_for, flash, send_from_directory, has_request_context, g, jsonify
from flask_session import Session
from flask_wtf.csrf import CSRFProtect, CSRFError
from blueprints.financial_health import financial_health_bp
from blueprints.budget import budget_bp
from blueprints.quiz import quiz_bp
from blueprints.bill import bill_bp
from blueprints.net_worth import net_worth_bp
from blueprints.emergency_fund import emergency_fund_bp
from blueprints.courses import courses_bp
import logging
import os
from json_store import JsonStorage
from functools import wraps
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

try:
    from python_dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logging.basicConfig(level=logging.WARNING)
    logging.warning("python_dotenv not found, using os.environ directly for environment variables.")

try:
    from translations import trans, get_translations
except ImportError as e:
    logging.error(f"Translations import failed: {str(e)}. Using fallback translation functions.")
    def trans(key, lang=None):
        return key
    def get_translations(lang):
        return {}

root_logger = logging.getLogger('ficore_app')
root_logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s [session: %(session_id)s]')

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
        if has_request_context() and 'sid' in session:
            kwargs['extra']['session_id'] = session.get('sid', 'unknown')
        else:
            kwargs['extra']['session_id'] = 'no-request-context'
        return msg, kwargs

log = SessionAdapter(root_logger, {})

app = Flask(__name__)

app.secret_key = os.environ.get('FLASK_SECRET_KEY')
if not app.secret_key:
    log.critical("FLASK_SECRET_KEY not set. Using insecure default!")
    app.secret_key = 'a_fallback_secret_key_for_dev_only_change_me'

session_dir = os.environ.get('SESSION_DIR', 'data/sessions')
if os.environ.get('RENDER'):
    session_dir = '/opt/render/project/src/data/sessions'

try:
    os.makedirs(session_dir, exist_ok=True)
    test_file = os.path.join(session_dir, '.test_write')
    with open(test_file, 'w') as f:
        f.write('test')
    os.remove(test_file)
    log.info(f"Session directory set to: {session_dir} and is writable")
except Exception as e:
    log.error(f"Failed to create or verify session directory {session_dir}: {str(e)}", exc_info=True)
    session_dir = 'data/sessions'
    os.makedirs(session_dir, exist_ok=True)
    log.warning(f"Falling back to session directory: {session_dir}")

app.config['SESSION_FILE_DIR'] = session_dir
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_SERIALIZER'] = 'json'
Session(app)
CSRFProtect(app)

def init_gspread_client():
    try:
        creds_json = os.environ.get('GOOGLE_CREDENTIALS')
        if not creds_json:
            log.error("GOOGLE_CREDENTIALS not set in environment variables")
            return None
        creds = Credentials.from_service_account_info(
            json.loads(creds_json),
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(creds)
        log.info("Initialized gspread client for Google Sheets")
        return client
    except Exception as e:
        log.error(f"Failed to initialize gspread client: {str(e)}", exc_info=True)
        return None

app.config['GSPREAD_CLIENT'] = init_gspread_client()

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
    with app.app_context():
        for tool, path in tools:
            try:
                dir_name = os.path.dirname(path)
                os.makedirs(dir_name, exist_ok=True)
                storage = JsonStorage(path, logger_instance=log)
                log.info(f"Initialized JsonStorage for {tool} at {path}", extra={'session_id': f'init_{tool}'})
                storage_managers[tool] = storage
            except Exception as e:
                log.error(f"Failed to initialize JsonStorage for {tool} at {path}: {str(e)}", exc_info=True, extra={'session_id': f'init_{tool}'})
                storage_managers[tool] = None
    return storage_managers

app.config['STORAGE_MANAGERS'] = init_storage_managers()

@app.template_filter('format_number')
def format_number(value):
    try:
        if isinstance(value, (int, float)):
            return f"{float(value):,.2f}"
        return str(value)
    except (ValueError, TypeError) as e:
        log.warning(f"Error formatting number {value}: {str(e)}")
        return str(value)

def session_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'sid' not in session:
            session['sid'] = str(uuid.uuid4())
            log.info(f"New session ID generated by decorator: {session['sid']}")
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def before_request_setup():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        log.info(f"New session ID generated in before_request: {session['sid']}")
    g.log = log
    g.log.info(f"Request started for path: {request.path}")
    g.log.debug(f"Current directory: {os.getcwd()}")
    g.log.debug(f"Directory contents: {os.listdir('.')}")
    if not os.path.exists('data/storage.txt'):
        g.log.warning("data/storage.txt not found in data directory")

@app.context_processor
def inject_translations():
    def context_trans(key):
        return trans(key)  # Remove lang argument
    log.debug("Injecting translations and context variables")
    return dict(
        trans=context_trans,
        current_year=datetime.now().year,
        LINKEDIN_URL=os.environ.get('LINKEDIN_URL', '#'),
        TWITTER_URL=os.environ.get('TWITTER_URL', '#'),
        FACEBOOK_URL=os.environ.get('FACEBOOK_URL', '#'),
        FEEDBACK_FORM_URL=os.environ.get('FEEDBACK_FORM_URL', '#'),
        WAITLIST_FORM_URL=os.environ.get('WAITLIST_FORM_URL', '#'),
        CONSULTANCY_FORM_URL=os.environ.get('CONSULTANCY_FORM_URL', '#')
    )

@app.route('/health')
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
        log.error(f"Health check failed: {str(e)}", exc_info=True)
        status["status"] = "unhealthy"
        status["details"] = str(e)
        return jsonify(status), 500
    return jsonify(status), 200

@app.route('/')
def index():
    if 'lang' not in session:
        session['lang'] = 'en'
    t = trans  # Pass trans function
    log.info("Serving index page")
    courses_storage = app.config['STORAGE_MANAGERS']['courses']
    try:
        courses = [record['data'] for record in courses_storage.read_all()] if courses_storage.read_all() else []
        log.debug(f"Retrieved {len(courses)} courses")
    except Exception as e:
        log.error(f"Error retrieving courses: {str(e)}", exc_info=True)
        courses = []
        flash(trans("error_message"), "danger")
    return render_template('index.html', t=t, courses=courses)

@app.route('/set_language/<lang>')
def set_language(lang):
    valid_langs = ['en', 'ha']
    session['lang'] = lang if lang in valid_langs else 'en'
    log.info(f"Language set to {session['lang']}")
    flash(trans('language_changed') if lang in valid_langs else trans('invalid_language'))
    return redirect(request.referrer or url_for('index'))

@app.route('/favicon.ico')
def favicon():
    log.debug("Serving favicon.ico")
    return send_from_directory(os.path.join(app.root_path, 'static', 'img'), 'favicon-32x32.png', mimetype='image/png')

@app.route('/general_dashboard')
@session_required
def general_dashboard():
    log.info("Serving general_dashboard")
    t = trans  # Pass trans function
    data = {}
    for tool, storage in app.config['STORAGE_MANAGERS'].items():
        try:
            if storage is None:
                log.error(f"Storage for {tool} was not initialized successfully.")
                if tool == 'courses':
                    data[tool] = []
                else:
                    data[tool] = {
                        'score': None, 'surplus_deficit': None, 'personality': None,
                        'bills': [], 'net_worth': None, 'savings_gap': None
                    }
                continue
            records = storage.filter_by_session(session['sid'])
            if tool == 'courses':
                data[tool] = [record['data'] for record in records]
            else:
                if records:
                    latest_record_raw = records[-1]['data']
                    if 'step' in latest_record_raw:
                        data[tool] = latest_record_raw.get('data', {})
                    else:
                        data[tool] = latest_record_raw
                else:
                    data[tool] = {
                        'score': None, 'surplus_deficit': None, 'personality': None,
                        'bills': [], 'net_worth': None, 'savings_gap': None
                    }
            log.debug(f"Data for {tool}: {data[tool]}")
        except Exception as e:
            log.exception(f"Error fetching data for {tool} in general_dashboard: {str(e)}")
            if tool == 'courses':
                data[tool] = []
            else:
                data[tool] = {
                    'score': None, 'surplus_deficit': None, 'personality': None,
                    'bills': [], 'net_worth': None, 'savings_gap': None
                }
    return render_template('general_dashboard.html', data=data, t=t)

@app.route('/logout')
def logout():
    log.info("Logging out user")
    session.clear()
    flash(trans('logged_out'))
    return redirect(url_for('index'))

@app.errorhandler(Exception)
def handle_global_error(e):
    t = trans  # Pass trans function
    log.exception(f"Global error handler caught exception: {str(e)}")
    flash(trans("error_message"), "danger")
    return render_template('500.html', error=trans('error_message'), t=t), 500

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    t = trans
    log.error(f"CSRF Error: {str(e)}", exc_info=True)
    flash(trans("csrf_error"), "danger")
    return render_template('500.html', error=trans('csrf_error'), t=t), 400

@app.errorhandler(404)
def page_not_found(e):
    t = trans
    log.error(f"404 Error: {str(e)}", exc_info=True)
    return render_template('404.html', error=trans('page_not_found'), t=t), 404

@app.errorhandler(500)
def internal_server_error(e):
    t = trans
    log.error(f"500 Error: {str(e)}", exc_info=True)
    flash(trans("error_message"), "danger")
    return render_template('500.html', error=trans('error_message'), t=t), 500

app.register_blueprint(financial_health_bp)
app.register_blueprint(budget_bp)
app.register_blueprint(quiz_bp)
app.register_blueprint(bill_bp)
app.register_blueprint(net_worth_bp)
app.register_blueprint(emergency_fund_bp)
app.register_blueprint(courses_bp)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=10000)
