import logging
import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for, flash, send_from_directory, has_request_context, g
from flask_session import Session
from flask_wtf.csrf import CSRFProtect, CSRFError

# Conditional import for python_dotenv
try:
    from python_dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Use a basic logger for this warning, as the main app logger might not be fully configured yet
    logging.basicConfig(level=logging.WARNING)
    logging.warning("python_dotenv not found, using os.environ directly for environment variables.")

# Conditional import for translations
try:
    from translations import trans, get_translations
except ImportError as e:
    logging.error(f"Translations import failed: {str(e)}. Using fallback translation functions.")
    def trans(key, lang=None):
        return key
    def get_translations(lang):
        return {}

# Import JsonStorage (it will now receive the global 'ficore_app' logger via constructor)
from json_store import JsonStorage
from functools import wraps

# --- Global Logging Configuration ---
# Get the root logger for the application. All other loggers will inherit from this.
root_logger = logging.getLogger('ficore_app')
root_logger.setLevel(logging.DEBUG) # Set the lowest level to capture all messages

# Formatter with timestamp and session ID placeholder
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s [session: %(session_id)s]')

# Ensure 'data' directory exists for logs and JSON storage
os.makedirs('data', exist_ok=True)

# File handler for all application logs (to data/storage.txt)
file_handler = logging.FileHandler('data/storage.txt')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
root_logger.addHandler(file_handler)

# Console handler for Render compatibility and local development
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

# LoggerAdapter for session context, applied globally
class SessionAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        kwargs['extra'] = kwargs.get('extra', {})
        # Safely get session_id only if request context exists and session is available
        if has_request_context() and 'sid' in session:
            kwargs['extra']['session_id'] = session.get('sid', 'unknown')
        else:
            kwargs['extra']['session_id'] = 'no-request-context' # Or 'unknown' for initial logs
        return msg, kwargs

# Initialize global logger with SessionAdapter, wrapping the root_logger
# This 'log' instance will be used in app.py's routes and contexts, and passed to JsonStorage
log = SessionAdapter(root_logger, {})

# Initialize Flask app
app = Flask(__name__)

# --- Application Configuration ---
# Set a robust secret key. It's critical for session security.
# It's highly recommended to set FLASK_SECRET_KEY as an environment variable in production.
app.secret_key = os.environ.get('FLASK_SECRET_KEY')
if not app.secret_key:
    log.critical("FLASK_SECRET_KEY environment variable not set. Using a default, but this is INSECURE for production!")
    app.secret_key = 'a_fallback_secret_key_for_dev_only_change_me' # Fallback for dev, but warn loudly

# Configure filesystem-based sessions
session_dir = os.environ.get('SESSION_DIR', 'data/sessions')
if os.environ.get('RENDER'):
    # For Render, ensure the path is absolute within the project directory
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
    # Fallback to a default if the configured path fails
    session_dir = 'data/sessions'
    os.makedirs(session_dir, exist_ok=True) # Try to create default if it doesn't exist
    log.warning(f"Falling back to session directory: {session_dir}")

app.config['SESSION_FILE_DIR'] = session_dir
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_SERIALIZER'] = 'json'
Session(app)
CSRFProtect(app)

# Initialize JsonStorage for each tool with permission check
storage_managers = {}
try:
    for tool, path in [
        ('financial_health', 'data/financial_health.json'),
        ('budget', 'data/budget.json'),
        ('quiz', 'data/quiz_data.json'),
        ('bills', 'data/bills.json'),
        ('net_worth', 'data/networth.json'),
        ('emergency_fund', 'data/emergency_fund.json')
    ]:
        dir_name = os.path.dirname(path)
        os.makedirs(dir_name, exist_ok=True)
        # Pass the SessionAdapter instance directly to JsonStorage
        storage = JsonStorage(path, logger_instance=log)
        
        # Test write access using append (this will now correctly use the adapted logger)
        test_data = {'test': 'write_check'}
        storage.append(test_data, session_id='test_session_init') # Use a distinct session ID for init tests
        log.info(f"Initialized JsonStorage for {tool} at {path}")
        storage_managers[tool] = storage
except Exception as e:
    log.critical(f"Failed to initialize JsonStorage for one or more tools: {str(e)}", exc_info=True)
    # Set storage managers to None to indicate failure, preventing further errors
    storage_managers = {tool: None for tool in ['financial_health', 'budget', 'quiz', 'bills', 'net_worth', 'emergency_fund']}

app.config['STORAGE_MANAGERS'] = storage_managers

# Template filter for number formatting
@app.template_filter('format_number')
def format_number(value):
    try:
        # Check if value is numeric, otherwise return as string
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
            log.info(f"New session ID generated by decorator: {session['sid']}")
        return f(*args, **kwargs)
    return decorated_function

# Before request handler to log directory contents and set g.log
@app.before_request
def before_request_setup():
    # Ensure session ID is set for every request
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        log.info(f"New session ID generated in before_request: {session['sid']}")

    # Make the adapted logger available via g.log for blueprints and other request-bound code
    g.log = log
    g.log.info(f"Request started for path: {request.path}")
    g.log.debug(f"Current directory: {os.getcwd()}")
    g.log.debug(f"Directory contents: {os.listdir('.')}")
    if not os.path.exists('data/storage.txt'):
        g.log.warning("data/storage.txt not found in data directory")


# Translation and context processor
@app.context_processor
def inject_translations():
    def context_trans(key):
        return trans(key)
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

# General Routes
@app.route('/')
def index():
    # Session ID is now handled by before_request_setup
    if 'lang' not in session:
        session['lang'] = 'en'
    t = trans('t')
    log.info("Serving index page")
    return render_template('index.html', t=t)

@app.route('/set_language/<lang>')
def set_language(lang):
    valid_langs = ['en', 'ha']
    session['lang'] = lang if lang in valid_langs else 'en'
    log.info(f"Language set to {session['lang']}")
    flash(trans('Language changed successfully') if lang in valid_langs else trans('Invalid language'))
    return redirect(request.referrer or url_for('index'))

@app.route('/favicon.ico')
def favicon():
    log.debug("Serving favicon.ico")
    # Ensure this path is correct for your favicon
    return send_from_directory(os.path.join(app.root_path, 'static', 'img'), 'favicon-32x32.png', mimetype='image/png')

@app.route('/general_dashboard')
@session_required
def general_dashboard():
    log.info("Serving general_dashboard")
    data = {}
    for tool, storage in app.config['STORAGE_MANAGERS'].items(): # Access storage_managers from app.config
        try:
            if storage is None:
                log.error(f"Storage for {tool} was not initialized successfully.")
                data[tool] = {
                    'score': None, 'surplus_deficit': None, 'personality': None,
                    'bills': [], 'net_worth': None, 'savings_gap': None
                }
                continue # Skip to next tool if storage is None

            records = storage.filter_by_session(session['sid'])
            # Normalize data structure from storage for consistent access
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
            log.exception(f"Error fetching data for {tool} in general_dashboard:") # Use log.exception here
            data[tool] = {
                'score': None, 'surplus_deficit': None, 'personality': None,
                'bills': [], 'net_worth': None, 'savings_gap': None
            }
    t = trans('t')
    return render_template('general_dashboard.html', data=data, t=t)

@app.route('/logout')
def logout():
    log.info("Logging out user")
    session.clear()
    flash(trans('You have been logged out'))
    return redirect(url_for('index'))

# Global Error Handler (catches all unhandled exceptions)
@app.errorhandler(Exception)
def handle_global_error(e):
    t = trans('t')
    # Use log.exception to get the full traceback automatically
    log.exception(f"Global error handler caught exception: {str(e)}")
    flash(t("An unexpected error occurred. Please try again or contact support."), "danger")
    return render_template(
        '500.html',
        error=t.get('Internal Server Error', 'Internal Server Error'),
        t=t
    ), 500

# Specific Error Handlers (these will also use the global logger)
@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    t = trans('t')
    log.error(f"CSRF Error: {str(e)}", exc_info=True) # Use exc_info=True to get traceback
    flash(t("CSRF token missing or invalid. Please try again."), "danger")
    return render_template('500.html', error=t.get('CSRF Error', 'CSRF Error'), t=t), 400

@app.errorhandler(404)
def page_not_found(e):
    t = trans('t')
    log.error(f"404 Error: {str(e)}", exc_info=True) # Use exc_info=True to get traceback
    return render_template('404.html', error=t.get('Page Not Found', 'Page Not Found'), t=t), 404

@app.errorhandler(500)
def internal_server_error(e):
    t = trans('t')
    # This handler is specific for 500, but global error handler will catch it first
    # unless you re-raise. If you want to handle it here, ensure it logs traceback.
    log.error(f"500 Error: {str(e)}", exc_info=True) # Ensure traceback is logged
    flash(t("An internal server error occurred. Please try again."), "danger")
    return render_template('500.html', error=t.get('Internal Server Error', 'Internal Server Error'), t=t), 500


# Register Blueprints
# Note: url_prefix is handled in the blueprint definition (e.g., financial_health_bp = Blueprint('financial_health', __name__, url_prefix='/financial_health'))
# If not defined in blueprint, you can add it here: app.register_blueprint(financial_health_bp, url_prefix='/financial_health')
app.register_blueprint(financial_health_bp)
app.register_blueprint(budget_bp)
app.register_blueprint(quiz_bp)
app.register_blueprint(bill_bp)
app.register_blueprint(net_worth_bp)
app.register_blueprint(emergency_fund_bp)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=10000) # Listen on all interfaces for Render
