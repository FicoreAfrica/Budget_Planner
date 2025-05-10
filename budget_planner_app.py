import os
import logging
import json
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, flash, redirect, url_for, session
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Optional
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from flask_session import Session
from flask_caching import Cache

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('app.log')]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your-secret-key')
if not app.config['SECRET_KEY']:
    logger.critical("FLASK_SECRET_KEY not set. Application will not start.")
    raise RuntimeError("FLASK_SECRET_KEY environment variable not set.")

# Configure server-side session with flask-session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(app.root_path, 'flask_session')
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_COOKIE_NAME'] = 'session_id'
Session(app)

# Create session directory if it doesn't exist
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

# Configure caching
app.config['CACHE_TYPE'] = 'filesystem'
app.config['CACHE_DIR'] = os.path.join(app.root_path, 'cache')
app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 minutes cache timeout
cache = Cache(app)
os.makedirs(app.config['CACHE_DIR'], exist_ok=True)

# Google Sheets setup
SCOPE = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', 'your-spreadsheet-id')
PREDETERMINED_HEADERS = [
    'Timestamp', 'first_name', 'email', 'language', 'monthly_income',
    'housing_expenses', 'food_expenses', 'transport_expenses', 'other_expenses',
    'savings_goal', 'auto_email', 'total_expenses', 'savings', 'surplus_deficit',
    'badges', 'rank', 'total_users'
]

# Thread-safe Google Sheets client (lazy initialization)
sheets = None
sheets_lock = threading.Lock()

def initialize_sheets(max_retries=5, backoff_factor=2):
    global sheets
    with sheets_lock:
        if sheets is not None:
            logger.info("Google Sheets already initialized.")
            return True
        for attempt in range(max_retries):
            try:
                creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
                if not creds_json:
                    logger.critical("GOOGLE_CREDENTIALS_JSON not set.")
                    return False
                try:
                    creds_dict = json.loads(creds_json)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid GOOGLE_CREDENTIALS_JSON format: {e}")
                    return False
                creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
                client = gspread.authorize(creds)
                sheets = client.open_by_key(SPREADSHEET_ID)
                logger.info("Successfully initialized Google Sheets.")
                return True
            except gspread.exceptions.APIError as e:
                logger.error(f"Google Sheets API error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(backoff_factor ** attempt)
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(backoff_factor ** attempt)
        logger.critical("Max retries exceeded for Google Sheets initialization.")
        return False

# Lazy initialization of sheets on first use
def get_sheets_client():
    global sheets
    if sheets is None:
        if not initialize_sheets():
            raise RuntimeError("Google Sheets initialization failed.")
    return sheets

# Google Sheets Utilities with caching
@cache.memoize(timeout=300)  # Cache for 5 minutes
def fetch_data_from_sheet(email=None, max_retries=5, backoff_factor=2):
    for attempt in range(max_retries):
        try:
            worksheet = get_sheets_client().worksheet('Sheet1')
            values = worksheet.get_all_values()
            if not values:
                logger.info(f"Attempt {attempt + 1}: No data in Google Sheet.")
                return pd.DataFrame(columns=PREDETERMINED_HEADERS)
            headers = values[0]
            rows = values[1:] if len(values) > 1 else []
            adjusted_rows = [
                row + [''] * (len(PREDETERMINED_HEADERS) - len(row)) if len(row) < len(PREDETERMINED_HEADERS) else row[:len(PREDETERMINED_HEADERS)]
                for row in rows
            ]
            df = pd.DataFrame(adjusted_rows, columns=PREDETERMINED_HEADERS)
            df['language'] = df['language'].replace('', 'en').apply(lambda x: x if x in translations else 'en')
            if email:
                df = df[df['email'] == email].head(1)  # Limit to one row for user-specific data
            logger.info(f"Fetched {len(df)} rows for email {email if email else 'all'}.")
            return df
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(backoff_factor ** attempt)
    logger.error("Max retries reached while fetching data.")
    return pd.DataFrame(columns=PREDETERMINED_HEADERS)  # Return empty DataFrame on failure

def set_sheet_headers():
    try:
        worksheet = get_sheets_client().worksheet('Sheet1')
        worksheet.update('A1:Q1', [PREDETERMINED_HEADERS])
        logger.info("Sheet1 headers updated.")
        return True
    except Exception as e:
        logger.error(f"Error setting headers: {e}")
        return False

def append_to_sheet(data):
    with sheets_lock:
        try:
            worksheet = get_sheets_client().worksheet('Sheet1')
            current_headers = worksheet.row_values(1)
            if not current_headers or current_headers != PREDETERMINED_HEADERS:
                if not set_sheet_headers():
                    logger.error("Failed to set sheet headers.")
                    return False
            if len(data) != len(PREDETERMINED_HEADERS):
                logger.error(f"Data length ({len(data)}) does not match headers ({len(PREDETERMINED_HEADERS)}): {data}")
                return False
            worksheet.append_row(data, value_input_option='RAW')
            logger.info(f"Appended data to sheet: {data}")
            time.sleep(1)  # Respect API rate limits
            return True
        except gspread.exceptions.APIError as api_err:
            logger.error(f"Google Sheets API error appending to sheet: {api_err}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error appending to sheet: {e}")
            return False

# Business Logic with caching
@cache.memoize(timeout=300)  # Cache for 5 minutes
def calculate_budget_metrics(df):
    try:
        if df.empty:
            logger.warning("Empty DataFrame in calculate_budget_metrics.")
            return df
        for col in ['monthly_income', 'housing_expenses', 'food_expenses', 'transport_expenses', 'other_expenses', 'savings_goal']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        df['total_expenses'] = df['housing_expenses'] + df['food_expenses'] + df['transport_expenses'] + df['other_expenses']
        df['savings'] = df.apply(lambda row: max(0, row['monthly_income'] * 0.1) if pd.isna(row['savings_goal']) or row['savings_goal'] == 0 else row['savings_goal'], axis=1)
        df['surplus_deficit'] = df['monthly_income'] - df['total_expenses'] - df['savings']
        df['advice'] = df['surplus_deficit'].apply(
            lambda x: 'Great job! Save or invest your surplus to grow your wealth.' if x >= 0 else 'Reduce non-essential spending to balance your budget.'
        )
        return df
    except Exception as e:
        logger.error(f"Error calculating budget metrics: {e}")
        return df  # Return original DataFrame on error

def assign_badges(user_df):
    badges = []
    if user_df.empty:
        logger.warning("Empty user_df in assign_badges.")
        return badges
    try:
        user_df['Timestamp'] = pd.to_datetime(user_df['Timestamp'], format='mixed', errors='coerce')
        user_df = user_df.sort_values('Timestamp', ascending=False)
    except Exception as e:
        logger.error(f"Error parsing timestamps in assign_badges: {e}")
        return badges
    user_row = user_df.iloc[0]
    language = user_row['language']
    if language not in translations:
        logger.warning(f"Invalid language '{language}'. Defaulting to English.")
        language = 'en'
    if len(user_df) == 1:
        badges.append(translations[language]['First Budget Completed!'])
    return badges

def send_budget_email(data, total_expenses, savings, surplus_deficit, chart_data, bar_data):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = translations[data['language']]['Budget Report Subject']
    msg['From'] = os.getenv('SMTP_USER', 'ficoreafrica@gmail.com')
    msg['To'] = data['email']

    html = render_template('budget_email.html',
                          translations=translations[data['language']],
                          user_name=data['first_name'],
                          monthly_income=data['monthly_income'],
                          housing_expenses=data['housing_expenses'],
                          food_expenses=data['food_expenses'],
                          transport_expenses=data['transport_expenses'],
                          other_expenses=data['other_expenses'],
                          total_expenses=total_expenses,
                          savings=savings,
                          surplus_deficit=surplus_deficit,
                          FEEDBACK_FORM_URL=FEEDBACK_FORM_URL,
                          WAITLIST_FORM_URL=WAITLIST_FORM_URL,
                          CONSULTANCY_FORM_URL=CONSULTANCY_FORM_URL,
                          course_url=COURSE_URL,
                          course_title=COURSE_TITLE,
                          linkedin_url=LINKEDIN_URL,
                          twitter_url=TWITTER_URL)
    part = MIMEText(html, 'html')
    msg.attach(part)

    try:
        with smtplib.SMTP(os.getenv('SMTP_SERVER', 'smtp.gmail.com'), int(os.getenv('SMTP_PORT', '587'))) as server:
            server.starttls()
            server.login(os.getenv('SMTP_USER', 'ficoreafrica@gmail.com'), os.getenv('SMTP_PASSWORD', 'your-password'))
            server.sendmail(os.getenv('SMTP_USER', 'ficoreafrica@gmail.com'), data['email'], msg.as_string())
        logger.info(f"Email sent to {data['email']}")
        flash(translations[data['language']]['Check Inbox'], 'info')
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        flash("Error sending email notification. Dashboard will still display.", 'warning')

# Form Definitions
class Step1Form(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    language = SelectField('Language', choices=[('en', 'English'), ('es', 'Spanish'), ('fr', 'French')], default='en')
    submit = SubmitField('Next')

class Step2Form(FlaskForm):
    income = FloatField('Monthly Income', validators=[DataRequired()])
    submit = SubmitField('Next')

class Step3Form(FlaskForm):
    housing = FloatField('Housing Expenses', validators=[DataRequired()])
    food = FloatField('Food Expenses', validators=[DataRequired()])
    transport = FloatField('Transport Expenses', validators=[DataRequired()])
    other = FloatField('Other Expenses', validators=[DataRequired()])
    submit = SubmitField('Next')

class Step4Form(FlaskForm):
    savings_goal = FloatField('Savings Goal', validators=[Optional()])
    auto_email = BooleanField('Receive Email Report')
    submit = SubmitField('Submit')

# Translations Dictionary
translations = {
    'en': {
        'First Budget Completed!': 'First Budget Completed!',
        'Check Inbox': 'Check your inbox for the budget report.',
        'Submission Success': 'Budget submitted successfully!',
        'Session Expired': 'Session expired. Please start over.',
        'Error retrieving data. Please try again.': 'Error retrieving data. Please try again.',
        'Error saving data. Please try again.': 'Error saving data. Please try again.',
        'Send Email Report': 'Email report sent successfully!',
        'Budget Report Subject': 'Your Budget Report'
    },
    'es': {
        'First Budget Completed!': '¡Primer presupuesto completado!',
        'Check Inbox': 'Revisa tu bandeja de entrada para el informe de presupuesto.',
        'Submission Success': '¡Presupuesto enviado con éxito!',
        'Session Expired': 'Sesión expirada. Por favor, comienza de nuevo.',
        'Error retrieving data. Please try again.': 'Error al recuperar datos. Por favor, intenta de nuevo.',
        'Error saving data. Please try again.': 'Error al guardar datos. Por favor, intenta de nuevo.',
        'Send Email Report': '¡Informe por correo enviado con éxito!',
        'Budget Report Subject': 'Tu Informe de Presupuesto'
    },
    'fr': {
        'First Budget Completed!': 'Premier budget complété !',
        'Check Inbox': 'Vérifiez votre boîte de réception pour le rapport de budget.',
        'Submission Success': 'Budget soumis avec succès !',
        'Session Expired': 'Session expirée. Veuillez recommencer.',
        'Error retrieving data. Please try again.': 'Erreur lors de la récupération des données. Veuillez réessayer.',
        'Error saving data. Please try again.': 'Erreur lors de l\'enregistrement des données. Veuillez réessayer.',
        'Send Email Report': 'Rapport par e-mail envoyé avec succès !',
        'Budget Report Subject': 'Votre Rapport de Budget'
    }
}

# Routes
@app.route('/', methods=['GET', 'POST'])
def step1():
    form = Step1Form()
    language = form.language.data if form.language.data in translations else 'en'
    if form.validate_on_submit():
        session['budget_data'] = {
            'first_name': form.first_name.data,
            'email': form.email.data,
            'language': form.language.data
        }
        return redirect(url_for('step2'))
    return render_template('budget_step1.html', form=form, translations=translations.get(language, translations['en']))

@app.route('/step2', methods=['GET', 'POST'])
def step2():
    form = Step2Form()
    language = session.get('budget_data', {}).get('language', 'en')
    if form.validate_on_submit():
        session['budget_data'].update({'monthly_income': form.income.data})
        return redirect(url_for('step3'))
    return render_template('budget_step2.html', form=form, translations=translations.get(language, translations['en']))

@app.route('/step3', methods=['GET', 'POST'])
def step3():
    form = Step3Form()
    language = session.get('budget_data', {}).get('language', 'en')
    if form.validate_on_submit():
        session['budget_data'].update({
            'housing_expenses': form.housing.data,
            'food_expenses': form.food.data,
            'transport_expenses': form.transport.data,
            'other_expenses': form.other.data
        })
        return redirect(url_for('step4'))
    return render_template('budget_step3.html', form=form, translations=translations.get(language, translations['en']))

@app.route('/step4', methods=['GET', 'POST'])
def step4():
    form = Step4Form()
    language = session.get('budget_data', {}).get('language', 'en')
    if form.validate_on_submit():
        session['budget_data'].update({
            'savings_goal': form.savings_goal.data or 0,
            'auto_email': form.auto_email.data
        })
        data = session['budget_data']
        
        # Calculate metrics
        total_expenses = data['housing_expenses'] + data['food_expenses'] + data['transport_expenses'] + data['other_expenses']
        savings = max(0, data['monthly_income'] * 0.1) if not data['savings_goal'] else data['savings_goal']
        surplus_deficit = data['monthly_income'] - total_expenses - savings
        chart_data = {
            'labels': ['Housing', 'Food', 'Transport', 'Other'],
            'datasets': [{'data': [data['housing_expenses'], data['food_expenses'], data['transport_expenses'], data['other_expenses']], 'backgroundColor': ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0']}]
        }
        bar_data = {
            'labels': ['Income', 'Expenses'],
            'datasets': [{'data': [data['monthly_income'], total_expenses], 'backgroundColor': ['#36A2EB', '#FF6384']}]
        }

        # Fetch existing data to calculate rank (cached)
        all_users_df = fetch_data_from_sheet()
        if all_users_df.empty:
            flash(translations[language]['Error retrieving data. Please try again.'], 'error')
            return redirect(url_for('step1'))

        # Calculate metrics for ranking (cached)
        all_users_df = calculate_budget_metrics(all_users_df)
        all_users_df['surplus_deficit'] = pd.to_numeric(all_users_df['surplus_deficit'], errors='coerce').fillna(0.0)
        all_users_df = all_users_df.sort_values('surplus_deficit', ascending=False).reset_index(drop=True)
        total_users = len(all_users_df.drop_duplicates(subset=['email']))
        user_df = pd.DataFrame([data])
        user_df = calculate_budget_metrics(user_df)
        user_index = all_users_df.index[all_users_df['email'] == data['email']].tolist()
        rank = user_index[0] + 1 if user_index else total_users  # Simplified ranking

        # Assign badges
        user_df['Timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        badges = assign_badges(user_df)

        # Prepare data for Google Sheets
        sheet_data = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            data['first_name'],
            data['email'],
            data['language'],
            str(data['monthly_income']),
            str(data['housing_expenses']),
            str(data['food_expenses']),
            str(data['transport_expenses']),
            str(data['other_expenses']),
            str(data['savings_goal']),
            str(data['auto_email']),
            str(total_expenses),
            str(savings),
            str(surplus_deficit),
            ','.join(badges),
            str(rank),
            str(total_users)
        ]

        # Append to Google Sheets
        if not append_to_sheet(sheet_data):
            flash(translations[language]['Error saving data. Please try again.'], 'error')
            return redirect(url_for('step1'))

        # Send email if requested
        if data.get('auto_email') and data.get('email'):
            send_budget_email(data, total_expenses, savings, surplus_deficit, chart_data, bar_data)

        flash(translations[language]['Submission Success'], 'success')

        # Store minimal data in session for dashboard
        session['dashboard_data'] = {
            'language': language,
            'first_name': data['first_name'],
            'email': data['email'],
            'monthly_income': data['monthly_income'],
            'housing_expenses': data['housing_expenses'],
            'food_expenses': data['food_expenses'],
            'transport_expenses': data['transport_expenses'],
            'other_expenses': data['other_expenses'],
            'total_expenses': total_expenses,
            'savings': savings,
            'surplus_deficit': surplus_deficit,
            'chart_data': chart_data,
            'bar_data': bar_data,
            'rank': rank,
            'total_users': total_users,
            'badges': badges
        }
        return redirect(url_for('dashboard'))

    return render_template('budget_step4.html', form=form, translations=translations.get(language, translations['en']))

@app.route('/dashboard')
def dashboard():
    language = session.get('dashboard_data', {}).get('language', 'en')
    dashboard_data = session.get('dashboard_data', {})
    if not dashboard_data:
        flash(translations[language]['Session Expired'], 'error')
        return redirect(url_for('step1'))

    return render_template('budget_dashboard.html',
                          translations=translations[language],
                          first_name=dashboard_data['first_name'],
                          monthly_income=dashboard_data['monthly_income'],
                          housing_expenses=dashboard_data['housing_expenses'],
                          food_expenses=dashboard_data['food_expenses'],
                          transport_expenses=dashboard_data['transport_expenses'],
                          other_expenses=dashboard_data['other_expenses'],
                          total_expenses=dashboard_data['total_expenses'],
                          savings=dashboard_data['savings'],
                          surplus_deficit=dashboard_data['surplus_deficit'],
                          chart_data=json.dumps(dashboard_data['chart_data']),
                          bar_data=json.dumps(dashboard_data['bar_data']),
                          rank=dashboard_data['rank'],
                          total_users=dashboard_data['total_users'],
                          badges=dashboard_data['badges'],
                          course_url=COURSE_URL,
                          course_title=COURSE_TITLE,
                          FEEDBACK_FORM_URL=FEEDBACK_FORM_URL,
                          WAITLIST_FORM_URL=WAITLIST_FORM_URL,
                          CONSULTANCY_FORM_URL=CONSULTANCY_FORM_URL,
                          linkedin_url=LINKEDIN_URL,
                          twitter_url=TWITTER_URL)

@app.route('/send_budget_email', methods=['POST'])
def send_budget_email_route():
    language = session.get('dashboard_data', {}).get('language', 'en')
    dashboard_data = session.get('dashboard_data', {})
    if not dashboard_data:
        flash(translations[language]['Session Expired'], 'error')
        return redirect(url_for('step1'))

    send_budget_email(
        dashboard_data,
        dashboard_data['total_expenses'],
        dashboard_data['savings'],
        dashboard_data['surplus_deficit'],
        dashboard_data['chart_data'],
        dashboard_data['bar_data']
    )
    flash(translations[language]['Send Email Report'], 'success')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
