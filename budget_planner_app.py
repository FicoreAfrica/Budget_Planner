from flask import Flask, render_template, request, flash, redirect, url_for, session
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Optional
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Replace with a secure key in production
app.config['SESSION_PERMANENT'] = False

# Comprehensive translations
translations = {
    'en': {
        'Monthly Budget Planner': 'Monthly Budget Planner',
        'Financial growth passport for Africa': 'Financial growth passport for Africa',
        'Plan Your Monthly Budget': 'Plan Your Monthly Budget',
        'Personal Information': 'Personal Information',
        'Income': 'Income',
        'Expenses': 'Expenses',
        'Savings & Review': 'Savings & Review',
        'First Name': 'First Name',
        'Enter your first name': 'Enter your first name',
        'Enter your first name for your report.': 'Enter your first name for your report.',
        'Looks good!': 'Looks good!',
        'First Name Required': 'First Name Required',
        'Email': 'Email',
        'Enter your email': 'Enter your email',
        'Get your budget report by email.': 'Get your budget report by email.',
        'Invalid Email': 'Invalid Email',
        'Language': 'Language',
        'Choose your language.': 'Choose your language.',
        'Language selected!': 'Language selected!',
        'Language required': 'Language required',
        'Monthly Income': 'Monthly Income',
        'Your monthly pay or income.': 'Your monthly pay or income.',
        'e.g. ₦150,000': 'e.g. ₦150,000',
        'Valid amount!': 'Valid amount!',
        'Invalid Number': 'Invalid Number',
        'Housing Expenses': 'Housing Expenses',
        'Rent, electricity, or water bills.': 'Rent, electricity, or water bills.',
        'e.g. ₦30,000': 'e.g. ₦30,000',
        'Food Expenses': 'Food Expenses',
        'Money spent on food each month.': 'Money spent on food each month.',
        'e.g. ₦45,000': 'e.g. ₦45,000',
        'Transport Expenses': 'Transport Expenses',
        'Bus, bike, taxi, or fuel costs.': 'Bus, bike, taxi, or fuel costs.',
        'e.g. ₦10,000': 'e.g. ₦10,000',
        'Other Expenses': 'Other Expenses',
        'Internet, clothes, or other spending.': 'Internet, clothes, or other spending.',
        'e.g. ₦20,000': 'e.g. ₦20,000',
        'Savings Goal': 'Savings Goal',
        'Desired monthly savings amount.': 'Desired monthly savings amount.',
        'e.g. ₦5,000': 'e.g. ₦5,000',
        'Auto Email': 'Send Report to Email',
        'Start Planning Your Budget!': 'Start Planning Your Budget!',
        'Planning your budget...': 'Planning your budget...',
        'Budget Surplus/Deficit': 'Budget Surplus/Deficit',
        'Great job! Save or invest your surplus to grow your wealth.': 'Great job! Save or invest your surplus to grow your wealth.',
        'Housing costs are high. Look for cheaper rent or utilities.': 'Housing costs are high. Look for cheaper rent or utilities.',
        'Food spending is high. Try cooking at home more.': 'Food spending is high. Try cooking at home more.',
        'Other spending is high. Cut back on non-essentials like clothes or entertainment.': 'Other spending is high. Cut back on non-essentials like clothes or entertainment.',
        'Reduce non-essential spending to balance your budget.': 'Reduce non-essential spending to balance your budget.',
        'Home': 'Home',
        'Contact Us': 'Contact Us',
        'Click to Email': 'Click to Email',
        'for support': 'for support',
        'Provide Feedback': 'Provide Feedback',
        'Join Waitlist': 'Join Waitlist',
        'Book Consultancy': 'Book Consultancy',
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
        'Earned badges': 'Earned badges',
        'No Badges Yet': 'No Badges Yet',
        'First Budget Completed!': 'First Budget Completed!',
        'Quick Tips': 'Quick Tips',
        'Great job! Save or invest your surplus.': 'Great job! Save or invest your surplus.',
        'Keep tracking your expenses every month.': 'Keep tracking your expenses every month.',
        'Spend less on non-essentials to balance your budget.': 'Spend less on non-essentials to balance your budget.',
        'Look for ways to earn extra income.': 'Look for ways to earn extra income.',
        'Recommended Learning': 'Recommended Learning',
        'Learn more about budgeting!': 'Learn more about budgeting!',
        'Whats Next': 'What’s Next',
        'Back to Home': 'Back to Home',
        'Send Email Report': 'Send Email Report',
        'Share Your Results': 'Share Your Results',
        'My Budget': 'My Budget',
        'My Budget Results': 'My Budget Results',
        'Check yours at': 'Check yours at',
        'Results copied to clipboard': 'Results copied to clipboard',
        'Failed to copy results': 'Failed to copy results',
        'Switch to Hausa': 'Switch to Hausa',
        'Switch to English': 'Switch to English',
        'Your Budget Report': 'Your Budget Report',
        'Dear': 'Dear',
        'Here is your monthly budget summary.': 'Here is your monthly budget summary.',
        'Budget Summary': 'Budget Summary',
        'Thank you for choosing Ficore Africa!': 'Thank you for choosing Ficore Africa!',
        'Budget Report Subject': 'Your Budget Report from Ficore Africa'
    },
    'ha': {
        'Monthly Budget Planner': 'Mai Tsara Kasafin Kuɗi na Wata',
        'Financial growth passport for Africa': 'Fasfo na ci gaban kuɗi na Afirka',
        'Plan Your Monthly Budget': 'Tsara Kasafin Kuɗin Wata',
        'Personal Information': 'Bayanan Sirri',
        'Income': 'Kuɗin Shiga',
        'Expenses': 'Kashe Kuɗi',
        'Savings & Review': 'Tattara Kuɗi & Bita',
        'First Name': 'Sunan Farko',
        'Enter your first name': 'Shigar da sunanka na farko',
        'Enter your first name for your report.': 'Shigar da sunanka na farko don rahotanka.',
        'Looks good!': 'Yayi kyau!',
        'First Name Required': 'Ana buƙatar sunan farko',
        'Email': 'Imel',
        'Enter your email': 'Shigar da imel ɗinka',
        'Get your budget report by email.': 'Samu rahoton kasafin kuɗinka ta imel.',
        'Invalid Email': 'Imel mara inganci',
        'Language': 'Harsa',
        'Choose your language.': 'Zaɓi harshenka.',
        'Language selected!': 'An zaɓi harshe!',
        'Language required': 'Ana buƙatar harshe',
        'Monthly Income': 'Kuɗin Shiga na Wata',
        'Your monthly pay or income.': 'Albashi ko kuɗin shiga na wata.',
        'e.g. ₦150,000': 'misali ₦150,000',
        'Valid amount!': 'Adadin da ya dace!',
        'Invalid Number': 'Lambar da ba ta dace ba',
        'Housing Expenses': 'Kuɗaɗen Gidaje',
        'Rent, electricity, or water bills.': 'Haya, wutar lantarki, ko kuɗin ruwa.',
        'e.g. ₦30,000': 'misali ₦30,000',
        'Food Expenses': 'Kuɗaɗen Abinci',
        'Money spent on food each month.': 'Kuɗin da aka kashe akan abinci kowane wata.',
        'e.g. ₦45,000': 'misali ₦45,000',
        'Transport Expenses': 'Kuɗaɗen Sufuri',
        'Bus, bike, taxi, or fuel costs.': 'Bas, keke, taksi, ko kuɗin mai.',
        'e.g. ₦10,000': 'misali ₦10,000',
        'Other Expenses': 'Sauran Kuɗaɗe',
        'Internet, clothes, or other spending.': 'Intanet, tufafi, ko sauran kashewa.',
        'e.g. ₦20,000': 'misali ₦20,000',
        'Savings Goal': 'Makasudin Tattara Kuɗi',
        'Desired monthly savings amount.': 'Adadin kuɗin da ake so a tara kowane wata.',
        'e.g. ₦5,000': 'misali ₦5,000',
        'Auto Email': 'Aika Rahoto ta Imel',
        'Start Planning Your Budget!': 'Fara Tsara Kasafin Kuɗinka!',
        'Planning your budget...': 'Ana tsara kasafin kuɗinka...',
        'Budget Surplus/Deficit': 'Ragowa/Kasawa na Kasafi',
        'Great job! Save or invest your surplus to grow your wealth.': 'Aikin kyau! Ajiye ko saka ragowar kuɗin don haɓaka dukiyarka.',
        'Housing costs are high. Look for cheaper rent or utilities.': 'Kuɗin gidaje yana da yawa. Nemi haya ko kayan aiki masu rahusa.',
        'Food spending is high. Try cooking at home more.': 'Kashe kuɗi akan abinci yana da yawa. Gwada dafa abinci a gida sosai.',
        'Other spending is high. Cut back on non-essentials like clothes or entertainment.': 'Sauran kashewa yana da yawa. Rage kashewa akan abubuwan da ba su da amfani kamar tufafi ko nishaɗi.',
        'Reduce non-essential spending to balance your budget.': 'Rage kashewa mara amfani don daidaita kasafin kuɗinka.',
        'Home': 'Gida',
        'Contact Us': 'Tuntube Mu',
        'Click to Email': 'Danna don Imel',
        'for support': 'don tallafi',
        'Provide Feedback': 'Bayar da Shawara',
        'Join Waitlist': 'Shiga Jerin Jira',
        'Book Consultancy': 'Yi Rijista don Shawara',
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
        'Earned badges': 'Bajojin da aka samu',
        'No Badges Yet': 'Babu Bajojin Har Yanzu',
        'First Budget Completed!': 'An Kammala Kasafin Farko!',
        'Quick Tips': 'Shawara Mai Sauri',
        'Great job! Save or invest your surplus.': 'Aikin kyau! Ajiye ko saka ragowar kuɗi.',
        'Keep tracking your expenses every month.': 'Ci gaba da bin diddigin kashe kuɗinka kowane wata.',
        'Spend less on non-essentials to balance your budget.': 'Rage kashewa akan abubuwan da ba su da amfani don daidaita kasafin kuɗinka.',
        'Look for ways to earn extra income.': 'Nemo hanyoyin samun ƙarin kuɗin shiga.',
        'Recommended Learning': 'Koyon da Aka Shawarta',
        'Learn more about budgeting!': 'Ƙara koyo game da tsara kasafi!',
        'Whats Next': 'Me Zai Biyo Baya',
        'Back to Home': 'Koma Gida',
        'Send Email Report': 'Aika Rahoton Imel',
        'Share Your Results': 'Raba Sakamakon Ka',
        'My Budget': 'Kasafina',
        'My Budget Results': 'Sakamakon Kasafina',
        'Check yours at': 'Duba naka a',
        'Results copied to clipboard': 'An kwafi sakamakon zuwa allo',
        'Failed to copy results': 'An kasa kwafi sakamakon',
        'Switch to Hausa': 'Canza zuwa Hausa',
        'Switch to English': 'Canza zuwa Turanci',
        'Your Budget Report': 'Rahoton Kasafin Kuɗinka',
        'Dear': 'Dear',
        'Here is your monthly budget summary.': 'Ga takaitaccen rahoton kasafin kuɗinka na wata.',
        'Budget Summary': 'Takaitaccen Kasafi',
        'Thank you for choosing Ficore Africa!': 'Muna godiya da zaɓar Ficore Africa!',
        'Budget Report Subject': 'Rahoton Kasafin Kuɗinka daga Ficore Africa'
    }
}

# Simulated user data
user_data = {
    'total_users': 1000,
    'user_rank': 250,
    'badges': ['First Budget Completed!']
}

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

@app.route('/', methods=['GET', 'POST'])
def step1():
    form = Step1Form()
    if form.validate_on_submit():
        session['budget_data'] = {
            'first_name': form.first_name.data,
            'email': form.email.data,
            'language': form.language.data
        }
        return redirect(url_for('step2'))
    return render_template('budget_step1.html', form=form, translations=translations.get(session.get('budget_data', {}).get('language', 'en'), translations['en']))

@app.route('/step2', methods=['GET', 'POST'])
def step2():
    form = Step2Form()
    if form.validate_on_submit():
        session['budget_data'].update({'monthly_income': form.income.data})
        return redirect(url_for('step3'))
    return render_template('budget_step2.html', form=form, translations=translations.get(session.get('budget_data', {}).get('language', 'en'), translations['en']))

@app.route('/step3', methods=['GET', 'POST'])
def step3():
    form = Step3Form()
    if form.validate_on_submit():
        session['budget_data'].update({
            'housing_expenses': form.housing.data,
            'food_expenses': form.food.data,
            'transport_expenses': form.transport.data,
            'other_expenses': form.other.data
        })
        return redirect(url_for('step4'))
    return render_template('budget_step3.html', form=form, translations=translations.get(session.get('budget_data', {}).get('language', 'en'), translations['en']))

@app.route('/step4', methods=['GET', 'POST'])
def step4():
    form = Step4Form()
    if form.validate_on_submit():
        session['budget_data'].update({
            'savings_goal': form.savings_goal.data or 0,
            'auto_email': form.auto_email.data
        })
        data = session['budget_data']
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
        flash('Budget planned successfully!', 'success')
        if data.get('auto_email') and data.get('email'):
            send_budget_email(data, total_expenses, savings, surplus_deficit, chart_data, bar_data)
        return render_template('budget_dashboard.html',
                              translations=translations[data['language']],
                              first_name=data['first_name'],
                              monthly_income=data['monthly_income'],
                              housing_expenses=data['housing_expenses'],
                              food_expenses=data['food_expenses'],
                              transport_expenses=data['transport_expenses'],
                              other_expenses=data['other_expenses'],
                              total_expenses=total_expenses,
                              savings=savings,
                              surplus_deficit=surplus_deficit,
                              chart_data=json.dumps(chart_data),
                              bar_data=json.dumps(bar_data),
                              rank=user_data['user_rank'],
                              total_users=user_data['total_users'],
                              badges=user_data['badges'],
                              course_url="https://example.com/budgeting-course",
                              course_title="Budgeting 101",
                              user_data_json=json.dumps(data))
    return render_template('budget_step4.html', form=form, translations=translations.get(session.get('budget_data', {}).get('language', 'en'), translations['en']))

@app.route('/send_budget_email', methods=['POST'])
def send_budget_email():
    data = json.loads(request.form['user_data_json'])
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
    send_budget_email(data, total_expenses, savings, surplus_deficit, chart_data, bar_data)
    flash('Email report sent successfully!', 'success')
    return redirect(url_for('step4'))

def send_budget_email(data, total_expenses, savings, surplus_deficit, chart_data, bar_data):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = translations[data['language']]['Budget Report Subject']
    msg['From'] = 'ficore.ai.africa@gmail.com'  # Replace with your email
    msg['To'] = data['email']

    # HTML email body
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
                          FEEDBACK_FORM_URL="https://example.com/feedback",
                          WAITLIST_FORM_URL="https://example.com/waitlist",
                          CONSULTANCY_FORM_URL="https://example.com/consultancy",
                          course_url="https://example.com/budgeting-course",
                          course_title="Budgeting 101")
    part = MIMEText(html, 'html')
    msg.attach(part)

    # Email server configuration (use your SMTP server details)
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login('ficore.ai.africa@gmail.com', 'your-password')  # Replace with your email password or app password
            server.sendmail('ficore.ai.africa@gmail.com', data['email'], msg.as_string())
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == '__main__':
    app.run(debug=True)