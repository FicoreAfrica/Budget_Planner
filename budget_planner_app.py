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

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
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

# Google Sheets setup
SCOPE = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', 'your-spreadsheet-id')  # Set this in Render
PREDETERMINED_HEADERS = [
    'Timestamp', 'first_name', 'email', 'language', 'monthly_income',
    'housing_expenses', 'food_expenses', 'transport_expenses', 'other_expenses',
    'savings_goal', 'auto_email', 'total_expenses', 'savings', 'surplus_deficit',
    'badges', 'rank', 'total_users'
]

# Thread-safe Google Sheets client
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

# Initialize sheets at startup
if not initialize_sheets():
    logger.critical("Failed to initialize Google Sheets. App will not function correctly.")
    raise RuntimeError("Google Sheets initialization failed.")

# Constants for external links
FEEDBACK_FORM_URL = 'https://forms.gle/1g1FVulyf7ZvvXr7G0q7hAKwbGJMxV4blpjBuqrSjKzQ'
WAITLIST_FORM_URL = 'https://forms.gle/17e0XYcp-z3hCl0I-j2JkHoKKJrp4PfgujsK8D7uqNxo'
CONSULTANCY_FORM_URL = 'https://forms.gle/1TKvlT7OTvNS70YNd8DaPpswvqd9y7hKydxKr07gpK9A'
LINKEDIN_URL = 'https://www.linkedin.com/in/ficore-africa-58913a363/'
TWITTER_URL = 'https://x.com/Hassanahm4d'
COURSE_URL = 'https://example.com/budgeting-course'
COURSE_TITLE = 'Budgeting 101'

# Translations (same as your original app.py, simplified for brevity)
translations = {
    'en': {
        'Monthly Budget Planner': 'Monthly Budget Planner',
        'Plan Your Monthly Budget': 'Plan Your Monthly Budget',
        'Personal Information': 'Personal Information',
        'Income': 'Income',
        'Expenses': 'Expenses',
        'Savings & Review': 'Savings & Review',
        'First Name': 'First Name',
        'Enter your first name': 'Enter your first name',
        'First Name Required': 'First Name Required',
        'Email': 'Email',
        'Enter your email': 'Enter your email',
        'Invalid Email': 'Invalid Email',
        'Language': 'Language',
        'Choose your language.': 'Choose your language.',
        'Monthly Income': 'Monthly Income',
        'Housing Expenses': 'Housing Expenses',
        'Food Expenses': 'Food Expenses',
        'Transport Expenses': 'Transport Expenses',
        'Other Expenses': 'Other Expenses',
        'Savings Goal': 'Savings Goal',
        'Auto Email': 'Send Report to Email',
        'Start Planning Your Budget!': 'Start Planning Your Budget!',
        'Budget Surplus/Deficit': 'Budget Surplus/Deficit',
        'Great job! Save or invest your surplus to grow your wealth.': 'Great job! Save or invest your surplus to grow your wealth.',
        'Reduce non-essential spending to balance your budget.': 'Reduce non-essential spending to balance your budget.',
        'Budget Dashboard': 'Budget Dashboard',
        'Welcome': 'Welcome',
        'Your Budget Summary': 'Your Budget Summary',
        'Total Expenses': 'Total Expenses',
        'Savings': 'Savings',
        'Surplus/Deficit': 'Surplus/Deficit',
        'Advice': 'Advice',
        'Rank': 'Rank',
        'out of': 'out of',
        'users': 'users',
        'Budget Breakdown': 'Budget Breakdown',
        'Your Badges': 'Your Badges',
        'No Badges Yet': 'No Badges Yet',
        'First Budget Completed!': 'First Budget Completed!',
        'Quick Tips': 'Quick Tips',
        'Recommended Learning': 'Recommended Learning',
        'Whats Next': 'What’s Next',
        'Back to Home': 'Back to Home',
        'Send Email Report': 'Send Email Report',
        'Your Budget Report': 'Your Budget Report',
        'Dear': 'Dear',
        'Here is your monthly budget summary.': 'Here is your monthly budget summary.',
        'Budget Summary': 'Budget Summary',
        'Thank you for choosing Ficore Africa!': 'Thank you for choosing Ficore Africa!',
        'Budget Report Subject': 'Your Budget Report from Ficore Africa',
        'Submission Success': 'Your budget is submitted successfully! Check your dashboard below 👇',
        'Check Inbox': 'Please check your inbox or junk folders if email doesn’t arrive in a few minutes.',
        'Error saving data. Please try again.': 'Error saving data. Please try again.',
        'Error retrieving data. Please try again.': 'Error retrieving data. Please try again.',
        'Session Expired': 'Your session has expired. Please refresh the page and try again.'
    },
    'ha': {
        'Monthly Budget Planner': 'Mai Tsara Kasafin Kuɗi na Wata',
        'Plan Your Monthly Budget': 'Tsara Kasafin Kuɗin Wata',
        'Personal Information': 'Bayanan Sirri',
        'Income': 'Kuɗin Shiga',
        'Expenses': 'Kashe Kuɗi',
        'Savings & Review': 'Tattara Kuɗi & Bita',
        'First Name': 'Sunan Farko',
        'Enter your first name': 'Shigar da sunanka na farko',
        'First Name Required': 'Ana buƙatar sunan farko',
        'Email': 'Imel',
        'Enter your email': 'Shigar da imel ɗinka',
        'Invalid Email': 'Imel mara inganci',
        'Language': 'Harsa',
        'Choose your language.': 'Zaɓi harshenka.',
        'Monthly Income': 'Kuɗin Shiga na Wata',
        'Housing Expenses': 'Kuɗaɗen Gidaje',
        'Food Expenses': 'Kuɗaɗen Abinci',
        'Transport Expenses': 'Kuɗaɗen Sufuri',
        'Other Expenses': 'Sauran Kuɗaɗe',
        'Savings Goal': 'Makasudin Tattara Kuɗi',
        'Auto Email': 'Aika Rahoto ta Imel',
        'Start Planning Your Budget!': 'Fara Tsara Kasafin Kuɗinka!',
        'Budget Surplus/Deficit': 'Ragowa/Kasawa na Kasafi',
        'Great job! Save or invest your surplus to grow your wealth.': 'Aikin kyau! Ajiye ko saka ragowar kuɗin don haɓaka dukiyarka.',
        'Reduce non-essential spending to balance your budget.': 'Rage kashewa mara amfani don daidaita kasafin kuɗinka.',
        'Budget Dashboard': 'Dashboard na Kasafi',
        'Welcome': 'Barka da Zuwa',
        'Your Budget Summary': 'Takaitaccen Kasafinku',
        'Total Expenses': 'Jimlar Kashewa',
        'Savings': 'Tattara Kuɗi',
        'Surplus/Deficit': 'Ragowa/Kasawa',
        'Advice': 'Shawara',
        'Rank': 'Matsayi',
        'out of': 'daga cikin',
        'users': 'masu amfani',
        'Budget Breakdown': 'Rarraba Kasafi',
        'Your Badges': 'Bajojin Ka',
        'No Badges Yet': 'Babu Bajojin Har Yanzu',
        'First Budget Completed!': 'An Kammala Kasafin Farko!',
        'Quick Tips': 'Shawara Mai Sauri',
        'Recommended Learning': 'Koyon da Aka Shawarta',
        'Whats Next': 'Me Zai Biyo Baya',
        'Back to Home': 'Koma Gida',
        'Send Email Report': 'Aika Rahoton Imel',
        'Your Budget Report': 'Rahoton Kasafin Kuɗinka',
        'Dear': 'Dear',
        'Here is your monthly budget summary.': 'Ga takaitaccen rahoton kasafin kuɗinka na wata.',
        'Budget Summary': 'Takaitaccen Kasafi',
        'Thank you for choosing Ficore Africa!': 'Muna godiya da zaɓar Ficore Africa!',
        'Budget Report Subject': 'Rahoton Kasafin Kuɗinka daga Ficore Africa',
        'Submission Success': 'An shigar da kasafinka cikin nasara! Duba dashboard ɗinka a ƙasa 👇',
        'Check Inbox': 'Da fatan za a duba akwatin saƙonku ko foldar na Spam idan imel ɗin bai zo ba cikin ƴan mintuna.',
        'Error saving data. Please try again.': 'Anyi Kuskure wajen adana bayanai. Da fatan za a sake gwadawa.',
        'Error retrieving data. Please try again.': 'Anyi Kuskure wajen dawo da bayanai. Da fatan za a sake gwadawa.',
        'Session Expired': 'Lokacin aikin ku ya ƙare. Da fatan za a sake shigar da shafin kuma a gwada sake.'
    }
}

# Simulated user data (will be updated from Google Sheets)
user_data = {'total_users': 1000, 'user_rank': 250, 'badges': ['First Budget Completed!']}

# Flask-WTF Forms (same as your original app.py)
class Step1Form(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    email = StringField('Email', validators=[Optional(), Email()])
    language = SelectField('Language', choices=[('en', 'English'), ('ha', 'Hausa')], validators=[DataRequired()])
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
    auto_email = BooleanField('Auto Email')
    submit = SubmitField('Review & Submit')

# Google Sheets Utilities
def get_sheet_headers():
    try:
        worksheet = sheets.worksheet('Sheet1')
        headers = worksheet.row_values(1)
        logger.debug(f"Fetched headers: {headers}")
        return headers
    except Exception as e:
        logger.error(f"Error fetching sheet headers: {e}")
        return None

def set_sheet_headers():
    try:
        worksheet = sheets.worksheet('Sheet1')
        worksheet.update('A1:Q1', [PREDETERMINED_HEADERS])
        logger.info("Sheet1 headers updated.")
        return True
    except Exception as e:
        logger.error(f"Error setting headers: {e}")
        return False

def append_to_sheet(data):
    with sheets_lock:
        try:
            worksheet = sheets.worksheet('Sheet1')
            current_headers = get_sheet_headers()
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

def fetch_data_from_sheet(email=None, max_retries=5, backoff_factor=2):
    for attempt in range(max_retries):
        try:
            worksheet = sheets.worksheet('Sheet1')
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
                df = df[df['email'] == email]
            logger.info(f"Fetched {len(df)} rows for email {email if email else 'all'}.")
            return df
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(backoff_factor ** attempt)
    logger.error("Max retries reached while fetching data.")
    return None

# Business Logic
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
        raise

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
        raise
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

        # Fetch existing data to calculate rank
        all_users_df = fetch_data_from_sheet()
        if all_users_df is None:
            flash(translations[language]['Error retrieving data. Please try again.'], 'error')
            return redirect(url_for('step1'))

        # Calculate metrics for ranking (simplified ranking based on surplus/deficit)
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

        # Store in session for dashboard
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
            'badges': badges,
            'user_df': user_df.to_dict(),
            'all_users_df': all_users_df.to_dict()
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
                          twitter_url=TWITTER_URL,
                          user_data_json=json.dumps(dashboard_data))

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
