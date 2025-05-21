import logging
import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for, flash, send_from_directory
from flask_session import Session
from flask_wtf.csrf import CSRFProtect
from blueprints.financial_health import financial_health_bp
from blueprints.budget import budget_bp
from blueprints.quiz import quiz_bp
from blueprints.bill import bill_bp
from blueprints.net_worth import net_worth_bp
from blueprints.emergency_fund import emergency_fund_bp
try:
    from python_dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logging.warning("python_dotenv not found, using os.environ directly")
try:
    from translations import trans, get_translations
except ImportError as e:
    logging.error(f"Translations import failed: {str(e)}")
    def trans(key, lang=None):
        return key
    def get_translations(lang):
        return {}
from json_store import JsonStorage
from functools import wraps
import traceback

# Configure basic logging
logger = logging.getLogger('ficore_app')
logger.setLevel(logging.DEBUG)

# Formatter with timestamp
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s [session: %(session_id)s]')

# File handler with fallback
try:
    os.makedirs('data', exist_ok=True)
    file_handler = logging.FileHandler('data/storage.txt')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
except Exception as e:
    logger.warning(f"Failed to set up file logging: {str(e)}")

# Console handler for Render compatibility
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# LoggerAdapter for session context
class SessionAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        kwargs['extra'] = kwargs.get('extra', {})
        kwargs['extra']['session_id'] = session.get('sid', 'unknown')
        return msg, kwargs

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key')  # Replace with a secure key in production

# Configure filesystem-based sessions
session_dir = os.environ.get('SESSION_DIR', 'data/sessions')
if os.environ.get('RENDER'):
    session_dir = '/opt/render/project/src/data/sessions'
try:
    os.makedirs(session_dir, exist_ok=True)
    # Verify directory is writable
    test_file = os.path.join(session_dir, '.test_write')
    with open(test_file, 'w') as f:
        f.write('test')
    os.remove(test_file)
    logger.info(f"Session directory set to: {session_dir} and is writable")
except Exception as e:
    logger.error(f"Failed to create or verify session directory {session_dir}: {str(e)}", exc_info=True)
    session_dir = 'data/sessions'  # Fallback to local directory
app.config['SESSION_FILE_DIR'] = session_dir
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True  # Enable session data signing for security
app.config['SESSION_SERIALIZER'] = 'json'  # Explicitly use JSON serializer for complex data
Session(app)
CSRFProtect(app)

# Initialize JsonStorage for each tool
storage_managers = {
    'financial_health': JsonStorage('data/financial_health.json'),
    'budget': JsonStorage('data/budget.json'),
    'quiz': JsonStorage('data/quiz_data.json'),
    'bills': JsonStorage('data/bills.json'),
    'net_worth': JsonStorage('data/networth.json'),
    'emergency_fund': JsonStorage('data/emergency_fund.json')
}

# Template filter for number formatting
@app.template_filter('format_number')
def format_number(value):
    try:
        return f"{float(value):,.2f}" if isinstance(value, (int, float)) else str(value)
    except (ValueError, TypeError) as e:
        logger.warning(f"Error formatting number {value}: {str(e)}")
        return str(value)

# Session required decorator
def session_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'sid' not in session:
            session['sid'] = str(uuid.uuid4())
        return f(*args, **kwargs)
    return decorated_function

# Before request handler to log directory contents and set logger
@app.before_request
def log_directory():
    global log
    log = SessionAdapter(logger, {})
    log.info(f"Current directory: {os.getcwd()}")
    log.info(f"Directory contents: {os.listdir('.')}")
    if not os.path.exists('data/storage.txt'):
        log.warning("storage.txt not found in data directory")

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
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
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
    return send_from_directory(os.path.join(app.root_path, 'static', 'img'), 'favicon-32x32.png', mimetype='image/png')

@app.route('/general_dashboard')
@session_required
def general_dashboard():
    log.info("Serving general_dashboard")
    data = {}
    for tool, storage in storage_managers.items():
        try:
            records = storage.filter_by_session(session['sid'])
            data[tool] = records[-1]['data'] if records else {
                'score': None, 'surplus_deficit': None, 'personality': None,
                'bills': [], 'net_worth': None, 'savings_gap': None
            }
            log.debug(f"Data for {tool}: {data[tool]}")
        except Exception as e:
            log.error(f"Error fetching data for {tool}: {str(e)}", exc_info=True)
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

# Error Handlers
@app.errorhandler(404)
def page_not_found(e):
    t = trans('t')
    log.error(f"404 Error: {str(e)}", exc_info=True)
    return render_template('404.html', error=t.get('Page Not Found', 'Page Not Found'), t=t), 404

@app.errorhandler(500)
def internal_server_error(e):
    t = trans('t')
    log.error(f"500 Error: {str(e)}", exc_info=True)
    return render_template('500.html', error=t.get('Internal Server Error', 'Internal Server Error'), t=t), 500

# Register Blueprints
app.register_blueprint(financial_health_bp, url_prefix='/financial_health')
app.register_blueprint(budget_bp, url_prefix='/budget')
app.register_blueprint(quiz_bp, url_prefix='/quiz')
app.register_blueprint(bill_bp, url_prefix='/bill')
app.register_blueprint(net_worth_bp, url_prefix='/net_worth')
app.register_blueprint(emergency_fund_bp, url_prefix='/emergency_fund')

if __name__ == '__main__':
    app.run(debug=True)
