import os
import uuid
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

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key')

# Set session directory
session_dir = os.environ.get('SESSION_DIR', 'data/sessions')
os.makedirs(session_dir, exist_ok=True)
app.config['SESSION_FILE_DIR'] = session_dir
app.config['SESSION_TYPE'] = 'filesystem'

# Translation context processor
@app.context_processor
def inject_translations():
    def t(key):
        lang = session.get('lang', 'en')
        translations = get_translations(lang)
        return translations.get(key, key)
    return dict(t=t)

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
        if 'user_id' not in session:
            session['user_id'] = str(uuid.uuid4())
            session['sid'] = str(uuid.uuid4())  # Align with Blueprints
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
        data[tool] = records[-1]['data'] if records else {}
    return render_template('general_dashboard.html', data=data)

# Error Handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
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
