import os
import logging
import json
import threading
import time
import re
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
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('app.log')]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
if not app.config['SECRET_KEY']:
    logger.critical("FLASK_SECRET_KEY not set. Application will not start.")
    raise RuntimeError("FLASK_SECRET_KEY environment variable not set.")

# Validate critical environment variables
required_env_vars = ['SMTP_SERVER', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD', 'SPREADSHEET_ID']
for var in required_env_vars:
    if not os.getenv(var):
        logger.critical(f"{var} not set. Application will not start.")
        raise RuntimeError(f"{var} environment variable not set.")

# Configure server-side session with flask-session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(app.root_path, 'flask_session')
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_COOKIE_NAME'] = 'session_id'
app.config['SESSION_COOKIE_SECURE'] = True  # Secure cookies in production
try:
    os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)
    logger.info(f"Session directory created at {app.config['SESSION_FILE_DIR']}")
except OSError as e:
    logger.error(f"Failed to create session directory: {e}")
    raise RuntimeError("Failed to create session directory.")
Session(app)

# Configure caching
app.config['CACHE_TYPE'] = 'filesystem'
app.config['CACHE_DIR'] = os.path.join(app.root_path, 'cache')
app.config['CACHE_DEFAULT_TIMEOUT'] = 600  # 10 minutes cache timeout
try:
    os.makedirs(app.config['CACHE_DIR'], exist_ok=True)
    cache = Cache(app)
except OSError as e:
    logger.error(f"Failed to create cache directory: {e}")
    logger.warning("Cache initialization failed. Proceeding without caching.")
    cache = Cache(app, config={'CACHE_TYPE': 'null'}

# Google Sheets setup
SCOPE = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
PREDETERMINED_HEADERS = [
    'Timestamp', 'first_name', 'email', 'language', 'monthly_income',
    'housing_expenses', 'food_expenses', 'transport_expenses', 'other_expenses',
    'savings_goal', 'auto_email', 'total_expenses', 'savings', 'surplus_deficit',
    'badges', 'rank', 'total_users'
]

# Define URL constants
FEEDBACK_FORM_URL = os.getenv('FEEDBACK_FORM_URL', 'https://forms.gle/1g1FVulyf7ZvvXr7G0q7hAKwbGJMxV4blpjBuqrSjKzQ')
WAITLIST_FORM_URL = os.getenv('FEEDBACK_FORM_URL', 'https://forms.gle/17e0XYcp-z3hCl0I-j2JkHoKKJrp4PfgujsK8D7uqNxo')
CONSULTANCY_FORM_URL = os.getenv('CONSULTANCY_FORM_URL', 'https://forms.gle/1TKvlT7OTvNS70YNd8DaPpswvqd9y7hKydxKr07gpK9A')
COURSE_URL = os.getenv('COURSE_URL', 'https://example.com/course')
COURSE_TITLE = os.getenv('COURSE_TITLE', 'Learn Budgeting')
LINKEDIN_URL = os.getenv('LINKEDIN_URL', 'https://www.linkedin.com/in/ficore-africa-58913a363/')
TWITTER_URL = os.getenv('TWITTER_URL', 'https://x.com/Hassanahm4d')

# Thread-safe Google Sheets client (lazy initialization)
sheets = None
sheets_lock = threading.Lock()

# Translations Dictionary
translations = {
    'en': {
        # Flask routes and flash messages
        'First Budget Completed!': 'First Budget Completed!',
        'Check Inbox': 'Check your inbox for the budget report.',
        'Submission Success': 'Budget submitted successfully!',
        'Session Expired': 'Session expired. Please start over.',
        'Incomplete Data': 'Incomplete data. Please complete all steps.',
        'Error retrieving data. Please try again.': 'Error retrieving data. Please try again.',
        'Error saving data. Please try again.': 'Error saving data. Please try again.',
        'Send Email Report': 'Email report sent successfully!',
        'Google Sheets Error': 'Unable to access Google Sheets. Please try again later.',
        # budget_dashboard.html
        'Budget Dashboard': 'Budget Dashboard',
        'Financial growth passport for Africa': 'Financial growth passport for Africa',
        'Welcome': 'Welcome',
        'Your Budget Summary': 'Your Budget Summary',
        'Monthly Income': 'Monthly Income',
        'Housing': 'Housing',
        'Food': 'Food',
        'Transport': 'Transport',
        'Other': 'Other',
        'Total Expenses': 'Total Expenses',
        'Savings': 'Savings',
        'Surplus/Deficit': 'Surplus/Deficit',
        'Advice': 'Advice',
        'Great job! Save or invest your surplus to grow your wealth.': 'Great job! Save or invest your surplus to grow your wealth.',
        'Housing costs are high. Look for cheaper rent or utilities.': 'Housing costs are high. Look for cheaper rent or utilities.',
        'Food spending is high. Try cooking at home more.': 'Food spending is high. Try cooking at home more.',
        'Reduce non-essential spending to balance your budget.': 'Reduce non-essential spending to balance your budget.',
        'Other spending is high. Cut back on non-essentials like clothes or entertainment.': 'Other spending is high. Cut back on non-essentials like clothes or entertainment.',
        'Your ranking': 'Your ranking',
        'Rank': 'Rank',
        'out of': 'out of',
        'users': 'users',
        'Budget Breakdown': 'Budget Breakdown',
        'Income vs Expenses': 'Income vs Expenses',
        'Your Badges': 'Your Badges',
        'Earned badges': 'Earned badges',
        'No Badges Yet': 'No Badges Yet',
        'Quick Tips': 'Quick Tips',
        'Great job! Save or invest your surplus.': 'Great job! Save or invest your surplus.',
        'Keep tracking your expenses every month.': 'Keep tracking your expenses every month.',
        'Spend less on non-essentials to balance your budget.': 'Spend less on non-essentials to balance your budget.',
        'Look for ways to earn extra income.': 'Look for ways to earn extra income.',
        'Recommended Learning': 'Recommended Learning',
        'Learn more about budgeting!': 'Learn more about budgeting!',
        'Whats Next': 'What\'s Next',
        'Back to Home': 'Back to Home',
        'Provide Feedback': 'Provide Feedback',
        'Join Waitlist': 'Join Waitlist',
        'Book Consultancy': 'Book Consultancy',
        'Connect on LinkedIn': 'Connect on LinkedIn',
        'Follow on Twitter': 'Follow on Twitter',
        'Share Your Results': 'Share Your Results',
        'Contact Us': 'Contact Us',
        'Click to Email': 'Click to Email',
        'for support': 'for support',
        'My Budget': 'My Budget',
        'Check yours at': 'Check yours at',
        'Results copied to clipboard': 'Results copied to clipboard',
        'Failed to copy results': 'Failed to copy results',
        # budget_step1.html
        'Monthly Budget Planner': 'Monthly Budget Planner',
        'Personal Information': 'Personal Information',
        'First Name': 'First Name',
        'Enter your first name': 'Enter your first name',
        'Enter your first name for your report.': 'Enter your first name for your report.',
        'Email': 'Email',
        'Enter your email': 'Enter your email',
        'Get your budget report by email.': 'Get your budget report by email.',
        'Language': 'Language',
        'Choose your language.': 'Choose your language.',
        'Looks good!': 'Looks good!',
        'First Name Required': 'First Name Required',
        'Invalid Email': 'Invalid Email',
        'Language selected!': 'Language selected!',
        'Language required': 'Language required',
        'Next': 'Next',
        'Continue to Income': 'Continue to Income',
        'Step 1': 'Step 1',
        # budget_step2.html
        'Income': 'Income',
        'Monthly Income': 'Monthly Income',
        'e.g. ₦150,000': 'e.g. ₦150,000',
        'Your monthly pay or income.': 'Your monthly pay or income.',
        'Valid amount!': 'Valid amount!',
        'Invalid Number': 'Invalid Number',
        'Back': 'Back',
        'Step 2': 'Step 2',
        'Continue to Expenses': 'Continue to Expenses',
        'Please enter a valid income amount': 'Please enter a valid income amount',
        # budget_step3.html
        'Expenses': 'Expenses',
        'Housing Expenses': 'Housing Expenses',
        'e.g. ₦30,000': 'e.g. ₦30,000',
        'Rent, electricity, or water bills.': 'Rent, electricity, or water bills.',
        'Food Expenses': 'Food Expenses',
        'e.g. ₦45,000': 'e.g. ₦45,000',
        'Money spent on food each month.': 'Money spent on food each month.',
        'Transport Expenses': 'Transport Expenses',
        'e.g. ₦10,000': 'e.g. ₦10,000',
        'Bus, bike, taxi, or fuel costs.': 'Bus, bike, taxi, or fuel costs.',
        'Other Expenses': 'Other Expenses',
        'e.g. ₦20,000': 'e.g. ₦20,000',
        'Internet, clothes, or other spending.': 'Internet, clothes, or other spending.',
        'Step 3': 'Step 3',
        'Continue to Savings & Review': 'Continue to Savings & Review',
        'Please enter valid amounts for all expenses': 'Please enter valid amounts for all expenses',
        # budget_step4.html
        'Savings & Review': 'Savings & Review',
        'Savings Goal': 'Savings Goal',
        'e.g. ₦5,000': 'e.g. ₦5,000',
        'Desired monthly savings amount.': 'Desired monthly savings amount.',
        'Auto Email': 'Auto Email',
        'Submit': 'Submit',
        'Step 4': 'Step 4',
        'Continue to Dashboard': 'Continue to Dashboard',
        'Analyzing your budget': 'Analyzing your budget...',
        'Please enter a valid savings goal amount': 'Please enter a valid savings goal amount',
        # budget_dashboard.html
        'Summary with Emoji': 'Summary 📊',
        'Badges with Emoji': 'Badges 🏅',
        'Tips with Emoji': 'Tips 💡',
        # budget_email.html
        'Budget Report Subject': 'Your Budget Report',
        'Your Budget Report': 'Your Budget Report',
        'Dear': 'Dear',
        'Here is your monthly budget summary.': 'Here is your monthly budget summary.',
        'Budget Summary': 'Budget Summary',
        'Thank you for choosing Ficore Africa!': 'Thank you for choosing Ficore Africa!',
        'Summary with Emoji': 'Summary 📊',
        'Advice with Emoji': 'Advice 💡',
        'Recommended Learning with Emoji': 'Recommended Learning 📚'
    },
    'ha': {
        # Flask routes and flash messages
        'First Budget Completed!': 'An kammala kasafin kuɗi na farko!',
        'Check Inbox': 'Duba akwatin saƙonku don rahoton kasafin kuɗi.',
        'Submission Success': 'An ƙaddamar da kasafin kuɗi cikin nasara!',
        'Session Expired': 'Zaman ya ƙare. Da fatan za a sake farawa.',
        'Incomplete Data': 'Bayanai ba su cika ba. Da fatan za a cika dukkan matakai.',
        'Error retrieving data. Please try again.': 'Kuskure wajen dawo da bayanai. Da fatan za a sake gwadawa.',
        'Error saving data. Please try again.': 'Kuskure wajen ajiye bayanai. Da fatan za a sake gwadawa.',
        'Send Email Report': 'An aika rahoton imel cikin nasara!',
        'Google Sheets Error': 'Ba a iya samun damar Google Sheets ba. Da fatan za a sake gwadawa daga baya.',
        # budget_dashboard.html
        'Budget Dashboard': 'Dashboard na Kasafin Kuɗi',
        'Financial growth passport for Africa': 'Fasfo na ci gaban kuɗi don Afirka',
        'Welcome': 'Barka da Zuwa',
        'Your Budget Summary': 'Takaitaccen Kasafin Kuɗin Ku',
        'Monthly Income': 'Kuɗin Shiga na Wata',
        'Housing': 'Gida',
        'Food': 'Abinci',
        'Transport': 'Sufuri',
        'Other': 'Sauran',
        'Total Expenses': 'Jimlar Kuɗaɗe',
        'Savings': 'Tattara Kuɗi',
        'Surplus/Deficit': 'Rage/Riba',
        'Advice': 'Shawara',
        'Great job! Save or invest your surplus to grow your wealth.': 'Aiki mai kyau! Ajiye ko saka ragowar kuɗin ku don bunkasa arzikinku.',
        'Housing costs are high. Look for cheaper rent or utilities.': 'Kuɗin gida yana da yawa. Nemi haya mai rahusa ko kayan aiki.',
        'Food spending is high. Try cooking at home more.': 'Kuɗin abinci yana da yawa. Gwada dafa abinci a gida sosai.',
        'Reduce non-essential spending to balance your budget.': 'Rage kashe kuɗi marasa mahimmanci don daidaita kasafin kuɗin ku.',
        'Other spending is high. Cut back on non-essentials like clothes or entertainment.': 'Sauran kashe kuɗi yana da yawa. Rage abubuwan da ba su da mahimmanci kamar tufafi ko nishaɗi.',
        'Your ranking': 'Matsayin ku',
        'Rank': 'Matsayi',
        'out of': 'daga cikin',
        'users': 'masu amfani',
        'Budget Breakdown': 'Rarraba Kasafin Kuɗi',
        'Income vs Expenses': 'Kuɗin Shiga vs Kuɗaɗe',
        'Your Badges': 'Alamominku',
        'Earned badges': 'Alamomīn da aka samu',
        'No Badges Yet': 'Babu Alama Har Yanzu',
        'Quick Tips': 'Shawarwari masu Sauƙi',
        'Great job! Save or invest your surplus.': 'Aiki mai kyau! Ajiye ko saka ragowar kuɗin ku.',
        'Keep tracking your expenses every month.': 'Ci gaba da bin diddigin kuɗaɗen ku kowane wata.',
        'Spend less on non-essentials to balance your budget.': 'Kashe ƙasa da kima akan abubuwan da ba su da mahimmanci don daidaita kasafin kuɗin ku.',
        'Look for ways to earn extra income.': 'Nemi hanyoyin samun ƙarin kuɗin shiga.',
        'Recommended Learning': 'Koyon da Aka Shawarta',
        'Learn more about budgeting!': 'Ƙara koyo game da tsara kasafin kuɗi!',
        'Whats Next': 'Me ke Gaba',
        'Back to Home': 'Koma Gida',
        'Provide Feedback': 'Bayar da Shawara',
        'Join Waitlist': 'Shiga Jerin Jira',
        'Book Consultancy': 'Yi Alƙawarin Shawara',
        'Connect on LinkedIn': 'Haɗa a LinkedIn',
        'Follow on Twitter': 'Bi a Twitter',
        'Share Your Results': 'Raba Sakamakonku',
        'Contact Us': 'Tuntuɓe Mu',
        'Click to Email': 'Danna don Imel',
        'for support': 'don tallafi',
        'My Budget': 'Kasafin Kuɗina',
        'Check yours at': 'Duba naku a',
        'Results copied to clipboard': 'An kwafi sakamakon zuwa allo',
        'Failed to copy results': 'An kasa kwafi sakamakon',
        # budget_step1.html
        'Monthly Budget Planner': 'Mai Tsara Kasafin Kuɗi na Wata',
        'Personal Information': 'Bayanai na Kai',
        'First Name': 'Sunan Farko',
        'Enter your first name': 'Shigar da sunan farko',
        'Enter your first name for your report.': 'Shigar da sunan farko don rahotonku.',
        'Email': 'Imel',
        'Enter your email': 'Shigar da imel ɗin ku',
        'Get your budget report by email.': 'Samu rahoton kasafin kuɗin ku ta imel.',
        'Language': 'Yare',
        'Choose your language.': 'Zaɓi yarenku.',
        'Looks good!': 'Yana da kyau!',
        'First Name Required': 'Ana Buƙatar Sunan Farko',
        'Invalid Email': 'Imel Ba daidai ba ne',
        'Language selected!': 'An zaɓi yare!',
        'Language required': 'Ana buƙatar yare',
        'Next': 'Na Gaba',
        'Continue to Income': 'Ci gaba zuwa Kuɗin Shiga',
        'Step 1': 'Mataki na 1',
        # budget_step2.html
        'Income': 'Kuɗin Shiga',
        'Monthly Income': 'Kuɗin Shiga na Wata',
        'e.g. ₦150,000': 'misali ₦150,000',
        'Your monthly pay or income.': 'Albashin ku na wata ko kuɗin shiga.',
        'Valid amount!': 'Adadin daidai ne!',
        'Invalid Number': 'Lamba Ba daidai ba ne',
        'Back': 'Koma Baya',
        'Step 2': 'Mataki na 2',
        'Continue to Expenses': 'Ci gaba zuwa Kashe Kuɗi',
        'Please enter a valid income amount': 'Da fatan za a shigar da adadin kuɗin shiga mai inganci',
        # budget_step3.html
        'Expenses': 'Kuɗaɗe',
        'Housing Expenses': 'Kuɗin Gida',
        'e.g. ₦30,000': 'misali ₦30,000',
        'Rent, electricity, or water bills.': 'Haya, wutar lantarki, ko kuɗin ruwa.',
        'Food Expenses': 'Kuɗin Abinci',
        'e.g. ₦45,000': 'misali ₦45,000',
        'Money spent on food each month.': 'Kuɗin da aka kashe akan abinci kowane wata.',
        'Transport Expenses': 'Kuɗin Sufuri',
        'e.g. ₦10,000': 'misali ₦10,000',
        'Bus, bike, taxi, or fuel costs.': 'Bas, keke, taksi, ko kuɗin mai.',
        'Other Expenses': 'Sauran Kuɗaɗe',
        'e.g. ₦20,000': 'misali ₦20,000',
        'Internet, clothes, or other spending.': 'Intanet, tufafi, ko sauran kashe kuɗi.',
        'Step 3': 'Mataki na 3',
        'Continue to Savings & Review': 'Ci gaba zuwa Tattalin Arziki & Dubawa',
        'Please enter valid amounts for all expenses': 'Da fatan za a shigar da adadin da ya dace ga duk kashe kuɗi',
        # budget_step4.html
        'Savings & Review': 'Tattara Kuɗi & Dubawa',
        'Savings Goal': 'Manufar Tattara Kuɗi',
        'e.g. ₦5,000': 'misali ₦5,000',
        'Desired monthly savings amount.': 'Adadin tattara kuɗi na wata da ake so.',
        'Auto Email': 'Imel ta atomatik',
        'Submit': 'Sallama',
        'Step 4': 'Mataki na 4',
        'Continue to Dashboard': 'Ci gaba zuwa Dashboard',
        'Analyzing your budget': 'Nazarin kasafin kuɗin ku...',
        'Please enter a valid savings goal amount': 'Da fatan za a shigar da adadin manufa mai inganci',
        # budget_dashboard.html
        'Summary with Emoji': 'Taƙaice 📊',
        'Badges with Emoji': 'Baja 🏅',
        'Tips with Emoji': 'Shawara 💡',
        # budget_email.html
        'Budget Report Subject': 'Rahoton Kasafin Kuɗi',
        'Your Budget Report': 'Rahoton Kasafin Kuɗi',
        'Dear': 'Masoyi',
        'Here is your monthly budget summary.': 'Ga takaitaccen kasafin kuɗin ku na wata.',
        'Budget Summary': 'Takaitaccen Kasafin Kuɗi',
        'Thank you for choosing Ficore Africa!': 'Muna godiya da zaɓin Ficore Afirka!',
        'Summary with Emoji': 'Taƙaice 📊',
        'Advice with Emoji': 'Shawara 💡',
        'Recommended Learning with Emoji': 'Koyon da Aka Shawarta 📚'
    }
}

def sanitize_input(text):
    """Sanitize input to prevent XSS or injection attacks."""
    if not text:
        return text
    # Remove potentially dangerous characters and limit length
    text = re.sub(r'[<>";]', '', text.strip())[:100]
    return text

def initialize_sheets(max_retries=3, backoff_factor=1):
    """Initialize Google Sheets client with retries."""
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
                creds_dict = json.loads(creds_json)
                creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
                client = gspread.authorize(creds)
                sheets = client.open_by_key(SPREADSHEET_ID)
                logger.info("Successfully initialized Google Sheets.")
                return True
            except json.JSONDecodeError as e:
                logger.error(f"Invalid GOOGLE_CREDENTIALS_JSON format: {e}")
                return False
            except gspread.exceptions.APIError as e:
                logger.error(f"Google Sheets API error on attempt {attempt + 1}: {e} (Status: {getattr(e.response, 'status_code', 'unknown')}, Response: {getattr(e.response, 'text', 'no response')})")
                if attempt < max_retries - 1:
                    time.sleep(backoff_factor)
            except PermissionError as e:
                logger.error(f"Permission error accessing spreadsheet {SPREADSHEET_ID} on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(backoff_factor)
            except (ValueError, KeyError, TypeError) as e:
                logger.error(f"Configuration error on attempt {attempt + 1}: {e}")
                return False
            except Exception as e:
                logger.exception(f"Unexpected error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(backoff_factor)
        logger.critical("Max retries exceeded for Google Sheets initialization.")
        return False

def get_sheets_client():
    """Get initialized Google Sheets client."""
    global sheets
    try:
        if sheets is None:
            if not initialize_sheets():
                logger.error("Google Sheets initialization failed.")
                return None
        return sheets
    except Exception as e:
        logger.exception(f"Failed to get sheets client: {e}")
        return None

@cache.memoize(timeout=600)
def fetch_data_from_sheet(email=None, max_retries=3, backoff_factor=1):
    """Fetch data from Google Sheets with retries."""
    for attempt in range(max_retries):
        try:
            client = get_sheets_client()
            if client is None:
                logger.error(f"Attempt {attempt + 1}: Google Sheets client not initialized.")
                return pd.DataFrame(columns=PREDETERMINED_HEADERS)
            worksheet = client.worksheet('Sheet1')
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
                df = df[df['email'] == email].head(1)
            logger.info(f"Fetched {len(df)} rows for email {email if email else 'all'}.")
            return df
        except gspread.exceptions.APIError as e:
            logger.error(f"Google Sheets API error on attempt {attempt + 1}: {e} (Status: {getattr(e.response, 'status_code', 'unknown')}, Response: {getattr(e.response, 'text', 'no response')})")
            if attempt < max_retries - 1:
                time.sleep(backoff_factor)
        except gspread.exceptions.WorksheetNotFound as e:
            logger.error(f"Worksheet 'Sheet1' not found: {e}")
            return pd.DataFrame(columns=PREDETERMINED_HEADERS)
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data processing error on attempt {attempt + 1}: {e}")
            return pd.DataFrame(columns=PREDETERMINED_HEADERS)
        except Exception as e:
            logger.exception(f"Unexpected error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(backoff_factor)
    logger.error("Max retries reached while fetching data.")
    return pd.DataFrame(columns=PREDETERMINED_HEADERS)

def set_sheet_headers():
    """Set Google Sheets headers."""
    try:
        client = get_sheets_client()
        if client is None:
            logger.error("Google Sheets client not initialized for setting headers.")
            return False
        worksheet = client.worksheet('Sheet1')
        worksheet.update('A1:Q1', [PREDETERMINED_HEADERS])
        logger.info("Sheet1 headers updated.")
        return True
    except gspread.exceptions.APIError as e:
        logger.error(f"Google Sheets API error setting headers: {e} (Status: {getattr(e.response, 'status_code', 'unknown')}, Response: {getattr(e.response, 'text', 'no response')})")
        return False
    except gspread.exceptions.WorksheetNotFound as e:
        logger.error(f"Worksheet 'Sheet1' not found: {e}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error setting headers: {e}")
        return False

def append_to_sheet(data):
    """Append data to Google Sheets."""
    with sheets_lock:
        try:
            if not data or len(data) != len(PREDETERMINED_HEADERS):
                logger.error(f"Invalid data length ({len(data)}) for headers ({len(PREDETERMINED_HEADERS)}): {data}")
                return False
            client = get_sheets_client()
            if client is None:
                logger.error("Google Sheets client not initialized for appending data.")
                return False
            worksheet = client.worksheet('Sheet1')
            current_headers = worksheet.row_values(1)
            if not current_headers or current_headers != PREDETERMINED_HEADERS:
                logger.info("Headers missing or incorrect. Setting headers.")
                if not set_sheet_headers():
                    logger.error("Failed to set sheet headers.")
                    return False
            else:
                logger.info("Headers already correct. Skipping header update.")
            worksheet.append_row(data, value_input_option='RAW')
            logger.info(f"Appended data to sheet: {data}")
            time.sleep(1)  # Respect API rate limits
            return True
        except gspread.exceptions.APIError as e:
            logger.error(f"Google Sheets API error appending to sheet: {e} (Status: {getattr(e.response, 'status_code', 'unknown')}, Response: {getattr(e.response, 'text', 'no response')})")
            return False
        except gspread.exceptions.WorksheetNotFound as e:
            logger.error(f"Worksheet 'Sheet1' not found: {e}")
            return False
        except (ValueError, TypeError) as e:
            logger.error(f"Data validation error appending to sheet: {e}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error appending to sheet: {e}")
            return False

@cache.memoize(timeout=600)
def calculate_budget_metrics(df):
    """Calculate budget metrics for DataFrame."""
    try:
        if df.empty:
            logger.warning("Empty DataFrame in calculate_budget_metrics.")
            return df
        for col in ['monthly_income', 'housing_expenses', 'food_expenses', 'transport_expenses', 'other_expenses', 'savings_goal']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        df['total_expenses'] = df['housing_expenses'] + df['food_expenses'] + df['transport_expenses'] + df['other_expenses']
        df['savings'] = df.apply(
            lambda row: max(0, row['monthly_income'] * 0.1) if pd.isna(row['savings_goal']) or row['savings_goal'] == 0 else row['savings_goal'],
            axis=1
        )
        df['surplus_deficit'] = df['monthly_income'] - df['total_expenses'] - df['savings']
        df['advice'] = df['surplus_deficit'].apply(
            lambda x: translations[df['language'].iloc[0]]['Great job! Save or invest your surplus to grow your wealth.'] if x >= 0 else translations[df['language'].iloc[0]]['Reduce non-essential spending to balance your budget.']
        )
        return df
    except (ValueError, TypeError, KeyError) as e:
        logger.error(f"Data processing error in calculate_budget_metrics: {e}")
        return df
    except Exception as e:
        logger.exception(f"Unexpected error in calculate_budget_metrics: {e}")
        return df

def assign_badges(user_df):
    """Assign badges based on user data."""
    badges = []
    try:
        if user_df.empty:
            logger.warning("Empty user_df in assign_badges.")
            return badges
        user_df['Timestamp'] = pd.to_datetime(user_df['Timestamp'], format='mixed', errors='coerce')
        user_df = user_df.sort_values('Timestamp', ascending=False)
        user_row = user_df.iloc[0]
        language = user_row.get('language', 'en')
        if language not in translations:
            logger.warning(f"Invalid language '{language}'. Defaulting to English.")
            language = 'en'
        if len(user_df) == 1:
            badges.append(translations[language]['First Budget Completed!'])
        return badges
    except (ValueError, TypeError, KeyError) as e:
        logger.error(f"Data processing error in assign_badges: {e}")
        return badges
    except Exception as e:
        logger.exception(f"Unexpected error in assign_badges: {e}")
        return badges

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def send_budget_email(data, total_expenses, savings, surplus_deficit, chart_data, bar_data):
    """Send budget report email to user with retries."""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = translations[data.get('language', 'en')]['Budget Report Subject']
        msg['From'] = os.getenv('SMTP_USER')
        msg['To'] = data['email']

        html = render_template(
            'budget_email.html',
            translations=translations[data.get('language', 'en')],
            user_name=sanitize_input(data.get('first_name', 'User')),
            monthly_income=data.get('monthly_income', 0),
            housing_expenses=data.get('housing_expenses', 0),
            food_expenses=data.get('food_expenses', 0),
            transport_expenses=data.get('transport_expenses', 0),
            other_expenses=data.get('other_expenses', 0),
            total_expenses=total_expenses,
            savings=savings,
            surplus_deficit=surplus_deficit,
            FEEDBACK_FORM_URL=FEEDBACK_FORM_URL,
            WAITLIST_FORM_URL=WAITLIST_FORM_URL,
            CONSULTANCY_FORM_URL=CONSULTANCY_FORM_URL,
            course_url=COURSE_URL,
            course_title=COURSE_TITLE,
            linkedin_url=LINKEDIN_URL,
            twitter_url=TWITTER_URL
        )
        part = MIMEText(html, 'html')
        msg.attach(part)

        with smtplib.SMTP(os.getenv('SMTP_SERVER'), int(os.getenv('SMTP_PORT'))) as server:
            server.starttls()
            server.login(os.getenv('SMTP_USER'), os.getenv('SMTP_PASSWORD'))
            server.sendmail(msg['From'], msg['To'], msg.as_string())
        logger.info(f"Email sent to {data['email']}")
        flash(translations[data.get('language', 'en')]['Check Inbox'], 'info')
        return True
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending email to {data.get('email', 'unknown')}: {e}")
        flash("Error sending email notification. Dashboard will still display.", 'warning')
        return False
    except (ValueError, TypeError, KeyError) as e:
        logger.error(f"Data processing error sending email: {e}")
        flash("Invalid email data. Dashboard will still display.", 'warning')
        return False
    except Exception as e:
        logger.exception(f"Unexpected error sending email: {e}")
        flash("Unexpected error sending email. Dashboard will still display.", 'warning')
        return False

# Form Definitions
class Step1Form(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    language = SelectField('Language', choices=[('en', 'English'), ('ha', 'Hausa')], default='en')
    submit = SubmitField('Next')

class Step2Form(FlaskForm):
    income = FloatField('Monthly Income', validators=[DataRequired()])
    submit = SubmitField('Continue to Expenses')

class Step3Form(FlaskForm):
    housing = FloatField('Housing Expenses', validators=[DataRequired()])
    food = FloatField('Food Expenses', validators=[DataRequired()])
    transport = FloatField('Transport Expenses', validators=[DataRequired()])
    other = FloatField('Other Expenses', validators=[DataRequired()])
    submit = SubmitField('Continue to Savings & Review')

class Step4Form(FlaskForm):
    savings_goal = FloatField('Savings Goal', validators=[Optional()])
    auto_email = BooleanField('Receive Email Report')
    submit = SubmitField('Continue to Dashboard')

# Routes
@app.route('/', methods=['GET', 'POST'])
def step1():
    """Handle Step 1: Personal Information."""
    try:
        form = Step1Form()
        language = form.language.data if form.language.data in translations else 'en'
        if form.validate_on_submit():
            first_name = sanitize_input(form.first_name.data)
            email = sanitize_input(form.email.data)
            if not first_name or not email:
                logger.error(f"Invalid sanitized input: first_name={first_name}, email={email}")
                flash(translations[language]['Invalid Email'], 'error')
                return render_template('budget_step1.html', form=form, translations=translations.get(language, translations['en']))
            session['budget_data'] = {
                'first_name': first_name,
                'email': email,
                'language': form.language.data
            }
            logger.info(f"Step 1 completed for {email}. Session data: {session['budget_data']}")
            return redirect(url_for('step2'))
        return render_template('budget_step1.html', form=form, translations=translations.get(language, translations['en']))
    except Exception as e:
        logger.exception(f"Error in step1 route: {e}")
        flash(translations.get('en')['Error retrieving data. Please try again.'], 'error')
        return redirect(url_for('step1'))

@app.route('/step2', methods=['GET', 'POST'])
def step2():
    """Handle Step 2: Income."""
    try:
        logger.info(f"Step 2 accessed. Current session data: {session.get('budget_data', {})}")
        form = Step2Form()
        if 'budget_data' not in session:
            logger.warning("Session data missing in step2.")
            flash(translations['en']['Session Expired'], 'error')
            return redirect(url_for('step1'))
        language = session['budget_data'].get('language', 'en')
        if form.validate_on_submit():
            income = form.income.data
            if income < 0:
                logger.error(f"Invalid income: {income}")
                flash(translations[language]['Please enter a valid income amount'], 'error')
                return render_template('budget_step2.html', form=form, translations=translations.get(language, translations['en']))
            session['budget_data']['monthly_income'] = income
            session.modified = True
            logger.info(f"Step 2 completed for {session['budget_data']['email']}. Updated session data: {session['budget_data']}")
            return redirect(url_for('step3'))
        return render_template('budget_step2.html', form=form, translations=translations.get(language, translations['en']))
    except Exception as e:
        logger.exception(f"Error in step2 route: {e}")
        flash(translations.get('en')['Error retrieving data. Please try again.'], 'error')
        return redirect(url_for('step1'))

@app.route('/step3', methods=['GET', 'POST'])
def step3():
    """Handle Step 3: Expenses."""
    try:
        logger.info(f"Step 3 accessed. Current session data: {session.get('budget_data', {})}")
        form = Step3Form()
        if 'budget_data' not in session:
            logger.warning("Session data missing in step3.")
            flash(translations['en']['Session Expired'], 'error')
            return redirect(url_for('step1'))
        language = session['budget_data'].get('language', 'en')
        if form.validate_on_submit():
            expenses = {
                'housing_expenses': form.housing.data,
                'food_expenses': form.food.data,
                'transport_expenses': form.transport.data,
                'other_expenses': form.other.data
            }
            for key, value in expenses.items():
                if value < 0:
                    logger.error(f"Invalid {key}: {value}")
                    flash(translations[language]['Please enter valid amounts for all expenses'], 'error')
                    return render_template('budget_step3.html', form=form, translations=translations.get(language, translations['en']))
            session['budget_data'].update(expenses)
            session.modified = True
            logger.info(f"Step 3 completed for {session['budget_data']['email']}. Updated session data: {session['budget_data']}")
            return redirect(url_for('step4'))
        return render_template('budget_step3.html', form=form, translations=translations.get(language, translations['en']))
    except Exception as e:
        logger.exception(f"Error in step3 route: {e}")
        flash(translations.get('en')['Error retrieving data. Please try again.'], 'error')
        return redirect(url_for('step1'))

@app.route('/step4', methods=['GET', 'POST'])
def step4():
    """Handle Step 4: Savings and Submission."""
    try:
        logger.info(f"Step 4 accessed. Current session data: {session.get('budget_data', {})}")
        form = Step4Form()
        if 'budget_data' not in session:
            logger.warning("Session data missing in step4.")
            flash(translations['en']['Session Expired'], 'error')
            return redirect(url_for('step1'))
        language = session['budget_data'].get('language', 'en')
        if form.validate_on_submit():
            savings_goal = form.savings_goal.data or 0
            if savings_goal < 0:
                logger.error(f"Invalid savings_goal: {savings_goal}")
                flash(translations[language]['Please enter a valid savings goal amount'], 'error')
                return render_template('budget_step4.html', form=form, translations=translations.get(language, translations['en']))
            session['budget_data'].update({
                'savings_goal': savings_goal,
                'auto_email': form.auto_email.data
            })
            session.modified = True
            data = session['budget_data']
            logger.info(f"Step 4 session data after update: {data}")

            # Validate required keys
            required_keys = ['first_name', 'email', 'language', 'monthly_income', 'housing_expenses', 'food_expenses', 'transport_expenses', 'other_expenses']
            missing_keys = [key for key in required_keys if key not in data]
            if missing_keys:
                logger.error(f"Missing keys in session['budget_data']: {missing_keys}")
                flash(translations[language]['Incomplete Data'], 'error')
                if 'monthly_income' in missing_keys:
                    return redirect(url_for('step2'))
                if any(key in missing_keys for key in ['housing_expenses', 'food_expenses', 'transport_expenses', 'other_expenses']):
                    return redirect(url_for('step3'))
                return redirect(url_for('step1'))

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

            # Fetch existing data to calculate rank (with fallback)
            all_users_df = fetch_data_from_sheet()
            if all_users_df.empty:
                logger.warning("No data retrieved from Google Sheets. Assigning default rank.")
                flash(translations[language]['Google Sheets Error'], 'warning')
                rank = 1
                total_users = 1
            else:
                all_users_df = calculate_budget_metrics(all_users_df)
                all_users_df['surplus_deficit'] = pd.to_numeric(all_users_df['surplus_deficit'], errors='coerce').fillna(0.0)
                all_users_df = all_users_df.sort_values('surplus_deficit', ascending=False).reset_index(drop=True)
                total_users = len(all_users_df.drop_duplicates(subset=['email']))
                user_df = pd.DataFrame([data])
                user_df = calculate_budget_metrics(user_df)
                user_index = all_users_df.index[all_users_df['email'] == data['email']].tolist()
                rank = user_index[0] + 1 if user_index else total_users

            # Assign badges
            user_df = pd.DataFrame([data])
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

            # Append to Google Sheets (with fallback)
            if not append_to_sheet(sheet_data):
                logger.error(f"Failed to save data for {data['email']} to Google Sheets.")
                flash(translations[language]['Google Sheets Error'], 'warning')

            # Send email if requested
            if data.get('auto_email') and data.get('email'):
                send_budget_email(data, total_expenses, savings, surplus_deficit, chart_data, bar_data)

            flash(translations[language]['Submission Success'], 'success')
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
            logger.info(f"Step 4 completed for {data['email']}. Dashboard data: {session['dashboard_data']}")
            return redirect(url_for('dashboard'))

        return render_template('budget_step4.html', form=form, translations=translations.get(language, translations['en']))
    except Exception as e:
        logger.exception(f"Error in step4 route: {e}")
        flash(translations.get('en')['Error retrieving data. Please try again.'], 'error')
        return redirect(url_for('step1'))

@app.route('/dashboard')
def dashboard():
    """Render user dashboard."""
    try:
        logger.info(f"Dashboard accessed. Current dashboard data: {session.get('dashboard_data', {})}")
        dashboard_data = session.get('dashboard_data', {})
        if not dashboard_data:
            logger.warning("Dashboard data missing in session.")
            flash(translations['en']['Session Expired'], 'error')
            return redirect(url_for('step1'))
        language = dashboard_data.get('language', 'en')

        return render_template(
            'budget_dashboard.html',
            translations=translations[language],
            first_name=dashboard_data.get('first_name', 'User'),
            monthly_income=dashboard_data.get('monthly_income', 0),
            housing_expenses=dashboard_data.get('housing_expenses', 0),
            food_expenses=dashboard_data.get('food_expenses', 0),
            transport_expenses=dashboard_data.get('transport_expenses', 0),
            other_expenses=dashboard_data.get('other_expenses', 0),
            total_expenses=dashboard_data.get('total_expenses', 0),
            savings=dashboard_data.get('savings', 0),
            surplus_deficit=dashboard_data.get('surplus_deficit', 0),
            chart_data=json.dumps(dashboard_data.get('chart_data', {})),
            bar_data=json.dumps(dashboard_data.get('bar_data', {})),
            rank=dashboard_data.get('rank', 0),
            total_users=dashboard_data.get('total_users', 0),
            badges=dashboard_data.get('badges', []),
            course_url=COURSE_URL,
            course_title=COURSE_TITLE,
            FEEDBACK_FORM_URL=FEEDBACK_FORM_URL,
            WAITLIST_FORM_URL=WAITLIST_FORM_URL,
            CONSULTANCY_FORM_URL=CONSULTANCY_FORM_URL,
            linkedin_url=LINKEDIN_URL,
            twitter_url=TWITTER_URL
        )
    except Exception as e:
        logger.exception(f"Error in dashboard route: {e}")
        flash(translations.get('en')['Error retrieving data. Please try again.'], 'error')
        return redirect(url_for('step1'))

@app.route('/send_budget_email', methods=['POST'])
def send_budget_email_route():
    """Handle manual email report request."""
    try:
        logger.info(f"Send budget email accessed. Current dashboard data: {session.get('dashboard_data', {})}")
        dashboard_data = session.get('dashboard_data', {})
        if not dashboard_data:
            logger.warning("Dashboard data missing in session for email route.")
            flash(translations['en']['Session Expired'], 'error')
            return redirect(url_for('step1'))
        language = dashboard_data.get('language', 'en')

        success = send_budget_email(
            dashboard_data,
            dashboard_data.get('total_expenses', 0),
            dashboard_data.get('savings', 0),
            dashboard_data.get('surplus_deficit', 0),
            dashboard_data.get('chart_data', {}),
            dashboard_data.get('bar_data', {})
        )
        if success:
            flash(translations[language]['Send Email Report'], 'success')
        return redirect(url_for('dashboard'))
    except Exception as e:
        logger.exception(f"Error in send_budget_email_route: {e}")
        flash(translations.get('en')['Error retrieving data. Please try again.'], 'error')
        return redirect(url_for('step1'))

if __name__ == '__main__':
    try:
        port = int(os.getenv('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=True)
    except ValueError as e:
        logger.error(f"Invalid PORT value: {e}")
        raise
    except Exception as e:
        logger.exception(f"Failed to start Flask app: {e}")
        raise