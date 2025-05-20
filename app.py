import os
import uuid
import logging
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_session import Session
from flask_wtf.csrf import CSRFProtect
from blueprints.financial_health import financial_health_bp  # Fixed import
from blueprints.budget import budget_bp  # Fixed import
from blueprints.quiz import quiz_bp  # Fixed import
from blueprints.bill import bill_bp  # Fixed import
from blueprints.net_worth import net_worth_bp  # Fixed import
from blueprints.emergency_fund import emergency_fund_bp  # Fixed import
try:
    from python_dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logging.warning("python_dotenv not found, using os.environ directly")
try:
    from translations import trans, get_translations
except ImportError as e:
    logging.warning(f"Translations import failed: {str(e)}")
    def trans(key, lang=None):
        return key
    def get_translations(lang):
        return {}
from json_store import JsonStorage
from functools import wraps

# Debug: Log directory contents
print("Current directory:", os.getcwd())
print("Directory contents:", os.listdir('.'))

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key')

# Configure filesystem-based sessions
session_dir = os.environ.get('SESSION_DIR', 'data/sessions')
if os.environ.get('RENDER'):
    session_dir = '/opt/render/project/src/data/sessions'
os.makedirs(os.path.dirname(session_dir) or '.', exist_ok=True)
os.makedirs(session_dir, exist_ok=True)
app.config['SESSION_FILE_DIR'] = session_dir
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
Session(app)
CSRFProtect(app)

# Configure logging
logging.basicConfig(filename='data/storage.txt', level=logging.DEBUG)

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
    except (ValueError, TypeError):
        return str(value)

# Session required decorator
def session_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'sid' not in session:
            session['sid'] = str(uuid.uuid4())
        return f(*args, **kwargs)
    return decorated_function

# Translation and context processor
@app.context_processor
def inject_translations():
    def context_trans(key):
        return trans(key)
    return dict(trans=context_trans, current_year=datetime.now().year)

# General Routes
@app.route('/')
def index():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    if 'lang' not in session:
        session['lang'] = 'en'
    t = trans('t')  # Get translation dictionary for templates
    return render_template('index.html', t=t)

@app.route('/set_language/<lang>')
def set_language(lang):
    if lang in ['en', 'ha']:
        session['lang'] = lang
        flash(trans('Language changed successfully'))
    else:
        flash(trans('Invalid language'))
    return redirect(request.referrer or url_for('index'))

@app.route('/general_dashboard')
@session_required
def general_dashboard():
    data = {}
    for tool, storage in storage_managers.items():
        try:
            records = storage.filter_by_session(session['sid'])
            data[tool] = records[-1]['data'] if records else {
                'score': None, 'surplus_deficit': None, 'personality': None,
                'bills': [], 'net_worth': None, 'savings_gap': None
            }
        except Exception as e:
            logging.exception(f"Error fetching data for {tool}: {str(e)}")
            data[tool] = {
                'score': None, 'surplus_deficit': None, 'personality': None,
                'bills': [], 'net_worth': None, 'savings_gap': None
            }
    t = trans('t')  # Get translation dictionary
    return render_template('general_dashboard.html', data=data, t=t)

@app.route('/logout')
def logout():
    """Clear session and redirect to homepage."""
    session.clear()
    flash(trans('You have been logged out'))
    return redirect(url_for('index'))

# Error Handlers
@app.errorhandler(404)
def page_not_found(e):
    t = trans('t')
    return render_template('404.html', error=t.get('Page Not Found', 'Page Not Found'), t=t), 404

@app.errorhandler(500)
def internal_server_error(e):
    logging.exception(f"500 Error: {str(e)}")
    t = trans('t')
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
