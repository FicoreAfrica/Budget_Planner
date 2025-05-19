import os
import uuid
import logging
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for, flash
from translations import get_translations
from json_store import JsonStorageManager
from blueprints.bill import bill_bp
from blueprints.quiz import quiz_bp
from blueprints.net_worth import net_worth_bp
from blueprints.emergency_fund import emergency_fund_bp
from blueprints.financial_health import financial_health_bp
from blueprints.budget import budget_bp
from functools import wraps

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or 'your-secret-key'  # Warning: Set FLASK_SECRET_KEY in production

# Configure filesystem-based sessions
session_dir = os.environ.get('SESSION_DIR', 'data/sessions')  # Default to data/sessions locally
if os.environ.get('RENDER'):  # Detect Render environment
    session_dir = '/opt/render/project/src/data/sessions'
os.makedirs(os.path.dirname(session_dir) or '.', exist_ok=True)  # Create parent directory (data/)
os.makedirs(session_dir, exist_ok=True)  # Create sessions directory
app.config['SESSION_FILE_DIR'] = session_dir
app.config['SESSION_TYPE'] = 'filesystem'

# Set up logging for errors
logging.basicConfig(filename='data/storage.txt', level=logging.ERROR)

# Translation and context processor
@app.context_processor
def inject_translations():
    def t(key):
        lang = session.get('lang', 'en')
        translations = get_translations(lang)
        return translations.get(key, key)
    return dict(t=t, current_year=datetime.now().year)

# Initialize JsonStorageManager for each tool
storage_managers = {
    'financial_health': JsonStorageManager('data/financial_health.json'),
    'budget': JsonStorageManager('data/budget.json'),
    'quiz': JsonStorageManager('data/quiz_data.json'),
    'bills': JsonStorageManager('data/bills.json'),
    'net_worth': JsonStorageManager('data/networth.json'),
    'emergency_fund': JsonStorageManager('data/emergency_fund.json')
}

# Session required decorator
def session_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'sid' not in session:
            session['sid'] = str(uuid.uuid4())
        return f(*args, **kwargs)
    return decorated_function

# General Routes
@app.route('/')
def index():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    if 'lang' not in session:
        session['lang'] = 'en'
    return render_template('index.html')

@app.route('/set_language/<lang>')
def set_language(lang):
    if lang in ['en', 'ha']:
        session['lang'] = lang
        translations = get_translations(lang)
        flash(translations.get('language_changed', 'Language changed successfully'))
    else:
        flash('Invalid language selected')
    return redirect(request.referrer or url_for('index'))

@app.route('/general_dashboard')
@session_required
def general_dashboard():
    data = {}
    for tool, storage in storage_managers.items():
        records = storage.filter_by_session(session['sid'])
        data[tool] = records[-1]['data'] if records else {
            'score': None, 'surplus_deficit': None, 'personality': None,
            'bills': [], 'net_worth': None, 'savings_gap': None
        }  # Default values to prevent template errors
    return render_template('general_dashboard.html', data=data)

# Error Handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    logging.error(f"500 Error: {str(e)}")
    return render_template('500.html'), 500

# Register Blueprints
app.register_blueprint(financial_health_bp, url_prefix='/financial_health')
app.register_blueprint(budget_bp, url_prefix='/budget')
app.register_blueprint(quiz_bp, url_prefix='/quiz')
app.register_blueprint(bill_bp, url_prefix='/bill')
app.register_blueprint(net_worth_bp, url_prefix='/net_worth')
app.register_blueprint(emergency_fund_bp, url_prefix='/emergency_fund')

if __name__ == '__main__':
    app.run(debug=True)
