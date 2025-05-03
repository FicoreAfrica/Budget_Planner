import os
import uuid
import json
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, TextAreaField, EmailField, SubmitField
from wtforms.validators import DataRequired, Email, Optional, NumberRange
from flask_mail import Mail, Message
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dateutil.parser import parse
from dateutil import parser
import random

# Initialize Flask app with custom template and static folders
app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get('FLASK_SECRET_KEY')
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'ficore.ai.africa@gmail.com'
app.config['MAIL_PASSWORD'] = os.environ.get('SMTP_PASSWORD')
mail = Mail(app)

# Embedded translations dictionary (replacing import from translations.py)
translations = {
    'English': {
        'Welcome': 'Welcome',
        'Your Financial Health Summary': 'Your Financial Health Summary',
        'Financial Health Score': 'Financial Health Score',
        'Ranked': 'Ranked',
        'out of': 'out of',
        'users': 'users',
        'Strong Financial Health': 'Your score indicates strong financial health. Focus on investing the surplus funds to grow your wealth.',
        'Stable Finances': 'Your finances are stable but could improve. Consider saving more or reducing your expenses.',
        'Financial Strain': 'Your score suggests financial strain. Prioritize paying off debt and managing your expenses.',
        'Urgent Attention Needed': 'Your finances need urgent attention. Seek professional advice and explore recovery strategies.',
        'Score Breakdown': 'Score Breakdown',
        'Chart Unavailable': 'Chart unavailable at this time.',
        'Asset-Liability Breakdown': 'Asset-Liability Breakdown',
        'Expense-Fund Breakdown': 'Expense-Fund Breakdown',
        'Question Performance': 'Question Performance',
        'Expense Breakdown': 'Expense Breakdown',
        'Comparison to Peers': 'Comparison to Peers',
        'Your Badges': 'Your Badges',
        'No Badges Yet': 'No badges earned yet. Keep submitting to earn more!',
        'First Health Score Completed!': 'First Health Score Completed!',
        'Financial Stability Achieved!': 'Financial Stability Achieved!',
        'Debt Slayer!': 'Debt Slayer!',
        'High Value Badge': 'High Value Badge',
        'Positive Value Badge': 'Positive Value Badge',
        'Recommended Learning': 'Recommended Learning',
        'Recommended Course': 'Recommended Course',
        'Quick Financial Tips': 'Quick Financial Tips',
        'Build Savings': 'Save 10% of your income monthly to create an emergency fund.',
        'Cut Costs': 'Review needs and wants - check expenses and reduce non-essential spending to boost cash flow.',
        'Reduce Debt': 'Prioritize paying off high-interest loans to ease financial strain.',
        'Back to Home': 'Back to Home',
        'Provide Feedback': 'Provide Feedback',
        'Join Waitlist': 'Join Premium Waitlist',
        'Book Consultancy': 'Book Consultancy',
        'Contact Us': 'Contact us at:',
        'for support': 'for support',
        'Click to Email': 'Click to Email',
        'Email Ficore Africa Support': 'Email Ficore Africa Support',
        'Personal Information': 'Personal Information',
        'Enter your first name': 'Enter your first name',
        'First Name Required': 'First name is required.',
        'Enter your last name (optional)': 'Enter your last name (optional)',
        'Enter your email': 'Enter your email',
        'Invalid Email': 'Please enter a valid email address.',
        'Confirm your email': 'Confirm your email',
        'Emails Do Not Match': 'Emails do not match.',
        'Enter phone number (optional)': 'Enter phone number (optional)',
        'Invalid Number': 'Please enter a valid number.',
        'Language': 'Language',
        'Select Language': 'Select Language',
        'Submit': 'Submit',
        'Please answer all questions before submitting!': 'Please answer all questions before submitting!',
        'Submission Success': 'Your information is submitted successfully! Check your dashboard below 👇',
        'Error processing form': 'Error processing form. Please try again.',
        'Email sent successfully': 'Email sent successfully!',
        'Failed to send email': 'Failed to send email. Please try again later.',
        'Score Report Subject': '📊 Your Ficore Score Report is Ready, {user_name}!',
        'Email Body': '''
            <html>
            <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #1E7F71; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
                    <h2 style="color: #FFFFFF; margin: 0;">Ficore Africa Financial Health Score</h2>
                    <p style="font-style: italic; color: #E0F7FA; font-size: 0.9rem; margin: 5px 0 0 0;">
                        Financial growth passport for Africa
                    </p>
                </div>
                <p>Dear {user_name},</p>
                <p>We have calculated your Ficore Africa Financial Health Score based on your recent submission.</p>
                <ul>
                    <li><strong>Score</strong>: {health_score}</li>
                    <li><strong>Advice</strong>: {score_description}</li>
                    <li><strong>Rank</strong>: #{rank} out of {total_users} users</li>
                </ul>
                <p>Follow the advice above to improve your financial health.</p>
                <p style="margin-bottom: 10px;">
                    Want to learn more? Check out this course: 
                    <a href="{course_url}" style="display: inline-block; padding: 10px 20px; background-color: #FBC02D; color: #333; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">{course_title}</a>
                </p>
                <p style="margin-bottom: 10px;">
                    Please provide feedback on your experience: 
                    <a href="{FEEDBACK_FORM_URL}" style="display: inline-block; padding: 10px 20px; background-color: #2E7D32; color: white; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">Feedback Form</a>
                </p>
                <p style="margin-bottom: 10px;">
                    Want Smart Insights? Join our waitlist: 
                    <a href="{WAITLIST_FORM_URL}" style="display: inline-block; padding: 10px 20px; background-color: #0288D1; color: white; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">Join Waitlist</a>
                </p>
                <p style="margin-bottom: 10px;">
                    Need expert advice? Book a consultancy: 
                    <a href="{CONSULTANCY_FORM_URL}" style="display: inline-block; padding: 10px 20px; background-color: #D81B60; color: white; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">Book Consultancy</a>
                </p>
                <p>Thank you for choosing Ficore Africa!</p>
                <p style="font-size: 0.8rem; color: #666; margin-top: 20px;">
                    © 2025 Ficore Africa. All rights reserved.
                </p>
            </body>
            </html>
        ''',
        'Get Your Score': 'Get Your Score',
        'Getting Started with Ficore Africa': 'Getting Started with Ficore Africa',
        'Fill in your name, email, and phone number. Choose your language—English or Hausa.': 'Fill in your name, email, and phone number. Choose your language—English or Hausa.',
        'Enter your business name, or your personal name if you don’t have a business. Select if you’re an individual or a business.': 'Enter your business name, or your personal name if you don’t have a business. Select if you’re an individual or a business.',
        'Add your monthly money details. Hover or tap the ℹ️ icons for help on what to enter.': 'Add your monthly money details. Hover or tap the ℹ️ icons for help on what to enter.',
        'Double-check your details, then click Submit to get your financial health score!': 'Double-check your details, then click Submit to get your financial health score!',
        'User Information': 'User Information',
        'Financial Information': 'Financial Information',
        'Total money you receive regularly, like salary, business sales, gifts, grants, incentives, or side hustles.': 'Total money you receive regularly, like salary, business sales, gifts, grants, incentives, or side hustles.',
        'All the money you spend, such as on rent, food, transport, electricity bill, gas and utilities, fine and penalties, levies, taxes, etc.': 'All the money you spend, such as on rent, food, transport, electricity bill, gas and utilities, fine and penalties, levies, taxes, etc.',
        'Money you owe, like loans, IOUs, borrowings, or funds lent to you.': 'Money you owe, like loans, IOUs, borrowings, or funds lent to you.',
        'Extra percentage you pay on a loan, usually per year or month. It’s usually something like 12% or 7%.': 'Extra percentage you pay on a loan, usually per year or month. It’s usually something like 12% or 7%.',
        'Type personal name if no business': 'Type personal name if no business',
        'e.g. 150,000': 'e.g. 150,000',
        'e.g. 60,000': 'e.g. 60,000',
        'e.g. 25,000': 'e.g. 25,000',
        'e.g. 10%': 'e.g. 10%',
        'New to finances? Click here to get guided tips on how to fill this form.': 'New to finances? Click here to get guided tips on how to fill this form.',
        'Select Individual if managing personal finances, or Business if submitting for a company.': 'Select Individual if managing personal finances, or Business if submitting for a company.',
        'Looks good!': 'Looks good!',
        'Valid amount!': 'Valid amount!',
        'Valid percentage!': 'Valid percentage!',
        'Emails match!': 'Emails match!',
        'Language selected!': 'Language selected!',
        'User type selected!': 'User type selected!',
        'Business name required': 'Business name required.',
        'Next': 'Next',
        'Previous': 'Previous',
        'Analyzing your score...': 'Analyzing your score...',
        'Net Worth Calculator': 'Net Worth Calculator',
        'Understand your financial standing and track your progress towards your goals.': 'Understand your financial standing and track your progress towards your goals.',
        'Enter amounts in Naira (₦).': 'Enter amounts in Naira (₦).',
        'Total value of everything you own — cash, property, investments, vehicles, etc.': 'Total value of everything you own — cash, property, investments, vehicles, etc.',
        'Total amount of money you owe — loans, debts, unpaid bills, etc.': 'Total amount of money you owe — loans, debts, unpaid bills, etc.',
        'Get your net worth instantly!': 'Get your net worth instantly!',
        'e.g. 500,000': 'e.g. 500,000',
        'e.g. 200,000': 'e.g. 200,000',
        'Submit net worth form': 'Submit net worth form',
        'Financial Personality Quiz': 'Financial Personality Quiz',
        'Discover your financial personality and gain insights': 'Discover your financial personality and gain insights into your money habits.',
        'Answer each question with Yes or No.': 'Answer each question with Yes or No.',
        'Enter your first name to personalize your results.': 'Enter your first name to personalize your results.',
        'Provide your email address to receive your results and personalized tips.': 'Provide your email address to receive your results and personalized tips.',
        'Choose your preferred language for the quiz. Options: English, Hausa.': 'Choose your preferred language for the quiz. Options: English, Hausa.',
        'Answer each question with Yes or No based on your financial habits.': 'Answer each question with Yes or No based on your financial habits.',
        'Uncover Your Financial Style': 'Uncover Your Financial Style',
        'Test your financial knowledge now!': 'Test your financial knowledge now!',
        'Submit quiz form': 'Submit quiz form',
        'Do you regularly track your income and expenses?': 'Do you regularly track your income and expenses?',
        'Do you prefer saving for the future over spending on immediate desires?': 'Do you prefer saving for the future over spending on immediate desires?',
        'Are you comfortable with taking financial risks to grow your wealth?': 'Are you comfortable with taking financial risks to grow your wealth?',
        'Do you have an emergency fund set aside for unexpected situations?': 'Do you have an emergency fund set aside for unexpected situations?',
        'Do you review your financial goals and strategies regularly?': 'Do you review your financial goals and strategies regularly?',
        'Emergency Fund Calculator': 'Emergency Fund Calculator',
        'Protect your financial well-being from unexpected events. Calculate your ideal safety net.': 'Protect your financial well-being from unexpected events. Calculate your ideal safety net.',
        'Most experts recommend saving 3-6 months of essential living expenses.': 'Most experts recommend saving 3-6 months of essential living expenses.',
        'Recommended fund size: ₦': 'Recommended fund size: ₦',
        'Enter the total amount you spend monthly on essentials like food, rent, transport, etc.': 'Enter the total amount you spend monthly on essentials like food, rent, transport, etc.',
        'Calculate Your Recommended Fund Size': 'Calculate Your Recommended Fund Size',
        'Find your safety net amount now!': 'Find your safety net amount now!',
        'Submit emergency fund form': 'Submit emergency fund form',
        'e.g. 50,000': 'e.g. 50,000',
        'Monthly Budget Planner': 'Monthly Budget Planner',
        'Take control of your finances and achieve your goals by creating a monthly budget.': 'Take control of your finances and achieve your goals by creating a monthly budget.',
        'Enter your total monthly earnings, including salary and side income.': 'Enter your total monthly earnings, including salary and side income.',
        'Include rent, electricity, water, and related housing bills.': 'Include rent, electricity, water, and related housing bills.',
        'Estimate how much you spend on food monthly.': 'Estimate how much you spend on food monthly.',
        'Monthly cost of transport—bus, bike, taxi, or fuel.': 'Monthly cost of transport—bus, bike, taxi, or fuel.',
        'Include internet, airtime, clothes, or personal spending.': 'Include internet, airtime, clothes, or personal spending.',
        'Get budgeting tips in your inbox.': 'Get budgeting tips in your inbox.',
        'e.g. 150,000': 'e.g. 150,000',
        'e.g. 30,000': 'e.g. 30,000',
        'e.g. 45,000': 'e.g. 45,000',
        'e.g. 10,000': 'e.g. 10,000',
        'e.g. 20,000': 'e.g. 20,000',
        'Start Planning Your Budget!': 'Start Planning Your Budget!',
        'Create your monthly budget now!': 'Create your monthly budget now!',
        'Submit budget form': 'Submit budget form',
        'FiCore Africa Home': 'FiCore Africa Home',
        'Home': 'Home',
        'Back': 'Back',
        'Expense Tracker': 'Expense Tracker',
        'Track your daily expenses to stay on top of your finances.': 'Track your daily expenses to stay on top of your finances.',
        'Enter your expense details': 'Enter your expense details',
        'Amount': 'Amount',
        'Category': 'Category',
        'Select a category': 'Select a category',
        'Date': 'Date',
        'e.g. today, yesterday, 2025-05-03': 'e.g. today, yesterday, 2025-05-03',
        'Description': 'Description',
        'e.g. Groceries at Market': 'e.g. Groceries at Market',
        'Submit Expense': 'Submit Expense',
        'Add your expense now!': 'Add your expense now!',
        'Submit expense form': 'Submit expense form',
        'Edit Expense': 'Edit Expense',
        'Update your expense details': 'Update your expense details',
        'Update Expense': 'Update Expense',
        'Bill Planner': 'Bill Planner',
        'Plan and manage your upcoming bills to avoid surprises.': 'Plan and manage your upcoming bills to avoid surprises.',
        'Enter your bill details': 'Enter your bill details',
        'Bill Name': 'Bill Name',
        'e.g. Electricity Bill': 'e.g. Electricity Bill',
        'Due Date': 'Due Date',
        'Status': 'Status',
        'Pending': 'Pending',
        'Paid': 'Paid',
        'Submit Bill': 'Submit Bill',
        'Add your bill now!': 'Add your bill now!',
        'Submit bill form': 'Submit bill form',
        'Edit Bill': 'Edit Bill',
        'Update your bill details': 'Update your bill details',
        'Update Bill': 'Update Bill',
        'Complete Bill': 'Complete Bill',
        'Mark as Paid': 'Mark as Paid',
        'Food and Groceries': 'Food and Groceries',
        'Transport': 'Transport',
        'Housing': 'Housing',
        'Utilities': 'Utilities',
        'Entertainment': 'Entertainment',
        'Other': 'Other',
        'Unlock Your Financial Freedom': 'Unlock Your Financial Freedom',
        'Access essential tools and insights to understand, manage, and grow your finances across Africa': 'Access essential tools and insights to understand, manage, and grow your finances across Africa',
        'Why Ficore Africa?': 'Why Ficore Africa?',
        'Localized for Africa with support for Naira and regional financial contexts': 'Localized for Africa with support for Naira and regional financial contexts',
        'Empowers financial literacy with easy-to-use tools': 'Empowers financial literacy with easy-to-use tools',
        'Provides actionable insights for better financial decisions': 'Provides actionable insights for better financial decisions',
        'Assess your financial health with a personalized score and insights': 'Assess your financial health with a personalized score and insights',
        'This tool evaluates your income, expenses, and debt to provide a health score': 'This tool evaluates your income, expenses, and debt to provide a health score',
        'Get Started with Financial Health Score': 'Get Started with Financial Health Score',
        'Calculate your net worth by evaluating your assets and liabilities': 'Calculate your net worth by evaluating your assets and liabilities',
        'Net worth is calculated as assets minus liabilities': 'Net worth is calculated as assets minus liabilities',
        'Get Started with Net Worth Calculator': 'Get Started with Net Worth Calculator',
        'Plan your emergency fund to cover unexpected expenses': 'Plan your emergency fund to cover unexpected expenses',
        'Aims to cover 3-6 months of expenses for financial security': 'Aims to cover 3-6 months of expenses for financial security',
        'Get Started with Emergency Fund Calculator': 'Get Started with Emergency Fund Calculator',
        'Test your financial knowledge and get personalized tips': 'Test your financial knowledge and get personalized tips',
        'Answer a series of questions to assess your financial literacy': 'Answer a series of questions to assess your financial literacy',
        'Get Started with Financial Personality Quiz': 'Get Started with Financial Personality Quiz',
        'Create a budget to manage your income and expenses effectively': 'Create a budget to manage your income and expenses effectively',
        'Helps you allocate your income across various expense categories': 'Helps you allocate your income across various expense categories',
        'Get Started with Weekly Budget Planner': 'Get Started with Weekly Budget Planner'
    },
    'Hausa': {
        'Welcome': 'Barka da Zuwa',
        'Your Financial Health Summary': 'Takaitaccen Lafiyar Kuɗin Ka',
        'Financial Health Score': 'Makin Lafiyar Kuɗi',
        'Ranked': 'An sanya matsayi',
        'out of': 'daga cikin',
        'users': 'masu amfani',
        'Strong Financial Health': 'Makin ka yana nuna lafiyar kuɗi mai ƙarfi. Mai da hankali kan saka hannun jari don haɓaka dukiyarka.',
        'Stable Finances': 'Kuɗin ka na da kwanciyar hankali amma yana iya inganta. Yi la’akari da ajiyar kuɗi ko rage kashe kuɗin ka.',
        'Financial Strain': 'Makin ka yana nuna matsi na kuɗi. Fifita biyan bashi da sarrafa kashe kuɗin ka.',
        'Urgent Attention Needed': 'Kuɗin ka na buƙatar kulawa cikin gaggaga. Nemi shawarar ƙwararru kuma bincika dabarun farfado da kuɗi.',
        'Score Breakdown': 'Rarraba Maki',
        'Chart Unavailable': 'Chart ba ya samuwa a wannan lokacin.',
        'Asset-Liability Breakdown': 'Rarraba Dukiya-Basussuka',
        'Expense-Fund Breakdown': 'Rarraba Kashe-Kudin Gaggawa',
        'Question Performance': 'Ayyukan Tambayoyi',
        'Expense Breakdown': 'Rarraba Kashe Kuɗi',
        'Comparison to Peers': 'Kwatantawa da Takwarorin Ka',
        'Your Badges': 'Alamominka',
        'No Badges Yet': 'Ba a samu alamomi ba tukuna. Ci gaba da ƙaddamarwa don samun ƙari!',
        'First Health Score Completed!': 'An Kammala Makin Lafiyar Kuɗi na Farko!',
        'Financial Stability Achieved!': 'An Sami Kwanciyar Hankali na Kuɗi!',
        'Debt Slayer!': 'Mai Kashe Bashi!',
        'High Value Badge': 'Alamar Daraja Mai Girma',
        'Positive Value Badge': 'Alamar Daraja Mai Kyau',
        'Recommended Learning': 'Ilimin da Aka Ba da Shawara',
        'Recommended Course': 'Kwas da Aka Ba da Shawara',
        'Quick Financial Tips': 'Shawarwari na Kuɗi Cikin Sauƙi',
        'Build Savings': 'Ajiye kashi 10% na kuɗin shigar ka kowane wata don ƙirƙirar kuɗin gaggawa.',
        'Cut Costs': 'Duba buƙatu da son rai - duba kashe kuɗi kuma rage kashe kuɗin da ba dole ba don ƙara kuɗin shiga.',
        'Reduce Debt': 'Fifita biyan lamuni masu yawan riba don sauƙaƙa matsin kuɗi.',
        'Back to Home': 'Koma Gida',
        'Provide Feedback': 'Ba da Shawara',
        'Join Waitlist': 'Shiga Jerin Jira na Premium',
        'Book Consultancy': 'Yi Rijistar Shawara',
        'Contact Us': 'Tuntuɓe mu a:',
        'for support': 'domin tallafi',
        'Click to Email': 'Danna don Imel',
        'Email Ficore Africa Support': 'Aika Imel zuwa Tallafin Ficore Africa',
        'Personal Information': 'Bayanin Sirri',
        'Enter your first name': 'Shigar da sunan ka na farko',
        'First Name Required': 'Ana buƙatar sunan farko.',
        'Enter your last name (optional)': 'Shigar da sunan ka na ƙarshe (na zaɓi)',
        'Enter your email': 'Shigar da imel ɗin ka',
        'Invalid Email': 'Da fatan za a shigar da adireshin imel mai inganci.',
        'Confirm your email': 'Tabbatar da imel ɗin ka',
        'Emails Do Not Match': 'Imel ba su daidaita ba.',
        'Enter phone number (optional)': 'Shigar da lambar waya (na zaɓi)',
        'Invalid Number': 'Da fatan za a shigar da lamba mai inganci.',
        'Language': 'Harshe',
        'Select Language': 'Zaɓi Harshe',
        'Submit': 'Sallama',
        'Please answer all questions before submitting!': 'Da fatan za a amsa duk tambayoyin kafin ƙaddamarwa!',
        'Submission Success': 'An ƙaddamar da bayananka cikin nasara! Duba dashboard ɗin ka a ƙasa 👇',
        'Error processing form': 'Kuskure wajen sarrafa fom. Da fatan za a sake gwadawa.',
        'Email sent successfully': 'An aika imel cikin nasara!',
        'Failed to send email': 'An kasa aika imel. Da fatan za a sake gwadawa daga baya.',
        'Score Report Subject': '📊 Rahoton Makin Ficore ɗin Ka Ya Shirya, {user_name}!',
        'Email Body': '''
            <html>
            <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #1E7F71; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
                    <h2 style="color: #FFFFFF; margin: 0;">Makin Lafiyar Kuɗi na Ficore Africa</h2>
                    <p style="font-style: italic; color: #E0F7FA; font-size: 0.9rem; margin: 5px 0 0 0;">
                        Fasfo na ci gaban kuɗi na Afirka
                    </p>
                </div>
                <p>Mai girma {user_name},</p>
                <p>Mun lissafa Makin Lafiyar Kuɗi na Ficore Africa bisa ga ƙaddamarwar ka na baya-bayan nan.</p>
                <ul>
                    <li><strong>Maki</strong>: {health_score}</li>
                    <li><strong>Shawara</strong>: {score_description}</li>
                    <li><strong>Matsayi</strong>: #{rank} daga cikin {total_users} masu amfani</li>
                </ul>
                <p>Bi shawarar da ke sama don inganta lafiyar kuɗin ka.</p>
                <p style="margin-bottom: 10px;">
                    Kana son ƙarin koyo? Duba wannan kwas: 
                    <a href="{course_url}" style="display: inline-block; padding: 10px 20px; background-color: #FBC02D; color: #333; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">{course_title}</a>
                </p>
                <p style="margin-bottom: 10px;">
                    Da fatan za a ba da shawara kan kwarewar ka: 
                    <a href="{FEEDBACK_FORM_URL}" style="display: inline-block; padding: 10px 20px; background-color: #2E7D32; color: white; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">Fom ɗin Shawara</a>
                </p>
                <p style="margin-bottom: 10px;">
                    Kana son Fahimta Mai Wayo? Shiga jerin jiranmu: 
                    <a href="{WAITLIST_FORM_URL}" style="display: inline-block; padding: 10px 20px; background-color: #0288D1; color: white; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">Shiga Jerin Jira</a>
                </p>
                <p style="margin-bottom: 10px;">
                    Kana buƙatar shawarar ƙwararru? Yi rijistar shawara: 
                    <a href="{CONSULTANCY_FORM_URL}" style="display: inline-block; padding: 10px 20px; background-color: #D81B60; color: white; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">Yi Rijistar Shawara</a>
                </p>
                <p>Na gode da zaɓin Ficore Africa!</p>
                <p style="font-size: 0.8rem; color: #666; margin-top: 20px;">
                    © 2025 Ficore Africa. Duk hakkoki ajiye.
                </p>
            </body>
            </html>
        ''',
        'Get Your Score': 'Sami Makin Ka',
        'Getting Started with Ficore Africa': 'Fara da Ficore Africa',
        'Fill in your name, email, and phone number. Choose your language—English or Hausa.': 'Cika sunan ka, imel, da lambar waya. Zaɓi harshen ka—Turanici ko Hausa.',
        'Enter your business name, or your personal name if you don’t have a business. Select if you’re an individual or a business.': 'Shigar da sunan kasuwancin ka, ko sunan ka na sirri idan ba ka da kasuwanci. Zaɓi ko kai mutum ne ko kasuwanci.',
        'Add your monthly money details. Hover or tap the ℹ️ icons for help on what to enter.': 'Ƙara bayanan kuɗin ka na wata-wata. Janyo ko taɓa alamun ℹ️ don taimako kan abin da za ka shigar.',
        'Double-check your details, then click Submit to get your financial health score!': 'Sake duba bayananka, sannan danna Sallama don samun makin lafiyar kuɗin ka!',
        'User Information': 'Bayanin Mai Amfani',
        'Financial Information': 'Bayanin Kuɗi',
        'Total money you receive regularly, like salary, business sales, gifts, grants, incentives, or side hustles.': 'Jimillar kuɗin da kake samu a kai a kai, kamar albashi, tallace-tallacen kasuwanci, kyaututtuka, tallafi, ƙarfafawa, ko sana’o’in gefe.',
        'All the money you spend, such as on rent, food, transport, electricity bill, gas and utilities, fine and penalties, levies, taxes, etc.': 'Duk kuɗin da kake kashewa, kamar haya, abinci, sufuri, lissafin wuta, gas da kayan aiki, tara da hukunci, haraji, da sauransu.',
        'Money you owe, like loans, IOUs, borrowings, or funds lent to you.': 'Kuɗin da ake bin ka, kamar lamuni, bashi, aro, ko kuɗin da aka ba ka bashi.',
        'Extra percentage you pay on a loan, usually per year or month. It’s usually something like 12% or 7%.': 'Ƙarin kaso da kake biya akan lamuni, yawanci a kowace shekara ko wata. Yawanci wani abu ne kamar 12% ko 7%.',
        'Type personal name if no business': 'Rubuta sunan sirri idan ba ka da kasuwanci',
        'e.g. 150,000': 'misali 150,000',
        'e.g. 60,000': 'misali 60,000',
        'e.g. 25,000': 'misali 25,000',
        'e.g. 10%': 'misali 10%',
        'New to finances? Click here to get guided tips on how to fill this form.': 'Sabon shiga cikin kuɗi? Danna nan don samun shawarwari kan yadda ake cika wannan fom.',
        'Select Individual if managing personal finances, or Business if submitting for a company.': 'Zaɓi Mutum idan kana sarrafa kuɗin ka na sirri, ko Kasuwanci idan kana ƙaddamarwa don kamfani.',
        'Looks good!': 'Yana da kyau!',
        'Valid amount!': 'Adadin da ya dace!',
        'Valid percentage!': 'Kason da ya dace!',
        'Emails match!': 'Imel sun dace!',
        'Language selected!': 'An zaɓi harshe!',
        'User type selected!': 'An zaɡi nau’in mai amfani!',
        'Business name required': 'Ana buƙatar sunan kasuwanci.',
        'Next': 'Na Gaba',
        'Previous': 'Na Baya',
        'Analyzing your score...': 'Ana nazarin makin ka...',
        'Net Worth Calculator': 'Kalkuletar Darajar Dukiya',
        'Understand your financial standing and track your progress towards your goals.': 'Fahimci matsayin kuɗin ka kuma bin diddigin ci gabanka zuwa ga manufofin ka.',
        'Enter amounts in Naira (₦).': 'Shigar da adadin a Naira (₦).',
        'Total value of everything you own — cash, property, investments, vehicles, etc.': 'Jimillar darajar duk abin da kake da shi — kuɗi, dukiya, zuba jari, motoci, da sauransu.',
        'Total amount of money you owe — loans, debts, unpaid bills, etc.': 'Jimillar kuɗin da ake bin ka — lamuni, basussuka, kuɗin da ba a biya ba, da sauransu.',
        'Get your net worth instantly!': 'Sami darajar dukiyarka nan take!',
        'e.g. 500,000': 'misali 500,000',
        'e.g. 200,000': 'misali 200,000',
        'Submit net worth form': 'Sallama fom ɗin darajar dukiya',
        'Financial Personality Quiz': 'Gwajin Halin Kuɗi',
        'Discover your financial personality and gain insights': 'Gano halin kuɗin ka kuma sami fahimta',
        'Answer each question with Yes or No.': 'Amsa kowace tambaya da Iya ko A’a.',
        'Enter your first name to personalize your results.': 'Shigar da sunan ka na farko don keɓance sakamakon.',
        'Provide your email address to receive your results and personalized tips.': 'Samar da adireshin imel don karɓar sakamakon ka da shawarwari na musamman.',
        'Choose your preferred language for the quiz. Options: English, Hausa.': 'Zaɓi harshen da kake so don gwajin. Zaɓuɓɓuka: Turanci, Hausa.',
        'Answer each question with Yes or No based on your financial habits.': 'Amsa kowace tambaya da Iya ko A’a bisa ga halayen kuɗin ka.',
        'Uncover Your Financial Style': 'Gano Salon Kuɗin Ka',
        'Test your financial knowledge now!': 'Gwada ilimin kuɗin ka yanzu!',
        'Submit quiz form': 'Sallama fom ɗin gwaji',
        'Do you regularly track your income and expenses?': 'Shin kuna bin diddigin kuɗin shigar ku da kashe kuɗi a kai a kai?',
        'Do you prefer saving for the future over spending on immediate desires?': 'Shin kuna son ajiyar kuɗi domin gaba fiye da kashe kuɗi akan abubuwan da kuke so yanzu?',
        'Are you comfortable with taking financial risks to grow your wealth?': 'Shin kuna jin daɗin ɗaukar haɗarin kuɗi don haɓaka dukiyarku?',
        'Do you have an emergency fund set aside for unexpected situations?': 'Shin kuna da ajiyar gaggawa da kuka tanada domin yanayi na rashin tsammani?',
        'Do you review your financial goals and strategies regularly?': 'Shin kuna duba manufofin kuɗi da dabarun ku a kai a kai?',
        'Emergency Fund Calculator': 'Kalkuletar Kudin Gaggawa',
        'Protect your financial well-being from unexpected events. Calculate your ideal safety net.': 'Kare lafiyar kuɗin ka daga abubuwan da ba a ji ba a gani ba. Lissafa madaidaicin kariyar ka.',
        'Most experts recommend saving 3-6 months of essential living expenses.': 'Yawancin ƙwararru suna ba da shawarar ajiyar kuɗin rayuwa na wata 3-6.',
        'Recommended fund size: ₦': 'Adadin kuɗin da aka ba da shawara: ₦',
        'Enter the total amount you spend monthly on essentials like food, rent, transport, etc.': 'Shigar da jimillar kuɗin da kake kashewa kowane wata akan abubuwan rayuwa kamar abinci, haya, sufuri, da sauransu.',
        'Calculate Your Recommended Fund Size': 'Lissafa Adadin Kudin Gaggawa da Ya Kamata Ka Ajiye',
        'Find your safety net amount now!': 'Gano adadin kariyar ka yanzu!',
        'Submit emergency fund form': 'Sallama fom ɗin kuɗin gaggawa',
        'e.g. 50,000': 'misali 50,000',
        'Monthly Budget Planner': 'Mai Tsara Kuɗin Wata-wata',
        'Take control of your finances and achieve your goals by creating a monthly budget.': 'Sarrafa kuɗin ka kuma cimma burinka ta hanyar ƙirƙirar kasafin kuɗi na wata-wata.',
        'Enter your total monthly earnings, including salary and side income.': 'Shigar da kuɗin da kake samu a wata – albashi da wasu sana’o’i.',
        'Include rent, electricity, water, and related housing bills.': 'Shigar da haya, wuta, ruwa da sauran kuɗin gidan zama.',
        'Estimate how much you spend on food monthly.': 'Kimanta kuɗin abinci da kake kashewa a wata.',
        'Monthly cost of transport—bus, bike, taxi, or fuel.': 'Kudin sufuri a wata—keke, mota, mai, ko haya.',
        'Include internet, airtime, clothes, or personal spending.': 'Saka intanet, katin waya, tufafi, ko duk wasu kashe-kashe.',
        'Get budgeting tips in your inbox.': 'Samu shawarwari akan tsara kuɗi ta imel.',
        'e.g. 150,000': 'misali 150,000',
        'e.g. 30,000': 'misali 30,000',
        'e.g. 45,000': 'misali 45,000',
        'e.g. 10,000': 'misali 10,000',
        'e.g. 20,000': 'misali 20,000',
        'Start Planning Your Budget!': 'Fara Tsara Kasafin Kuɗin Ka!',
        'Create your monthly budget now!': 'Ƙirƙiri kasafin kuɗin ka na wata yanzu!',
        'Submit budget form': 'Sallama fom ɗin kasafi',
        'FiCore Africa Home': 'Gidan Ficore Africa',
        'Home': 'Gida',
        'Back': 'Baya',
        'Expense Tracker': 'Mai Bibiyar Kashe Kuɗi',
        'Track your daily expenses to stay on top of your finances.': 'Biyi kashe kuɗin ka na yau da kullum don kasancewa a saman kuɗin ka.',
        'Enter your expense details': 'Shigar da bayanan kashe kuɗin ka',
        'Amount': 'Adadi',
        'Category': 'Rukuni',
        'Select a category': 'Zaɓi rukuni',
        'Date': 'Kwanan Wata',
        'e.g. today, yesterday, 2025-05-03': 'misali yau, jiya, 2025-05-03',
        'Description': 'Bayani',
        'e.g. Groceries at Market': 'misali Kayayyakin Abinci a Kasuwa',
        'Submit Expense': 'Sallama Kashe Kuɗi',
        'Add your expense now!': 'Ƙara kashe kuɗin ka yanzu!',
        'Submit expense form': 'Sallama fom ɗin kashe kuɗi',
        'Edit Expense': 'Gyara Kashe Kuɗi',
        'Update your expense details': 'Sabunta bayanan kashe kuɗin ka',
        'Update Expense': 'Sabunta Kashe Kuɗi',
        'Bill Planner': 'Mai Tsara Kuɗin Biyan Kuɗi',
        'Plan and manage your upcoming bills to avoid surprises.': 'Tsara kuma sarrafa kuɗin biyan kuɗin ka masu zuwa don gujewa abubuwan ban mamaki.',
        'Enter your bill details': 'Shigar da bayanan kuɗin biyan kuɗin ka',
        'Bill Name': 'Sunan Kuɗin Biyan Kuɗi',
        'e.g. Electricity Bill': 'misali Kuɗin Wuta',
        'Due Date': 'Kwanan Biyan Kuɗi',
        'Status': 'Matsayi',
        'Pending': 'Ana Jiran Biya',
        'Paid': 'An Biya',
        'Submit Bill': 'Sallama Kuɗin Biyan Kuɗi',
        'Add your bill now!': 'Ƙara kuɗin biyan kuɗin ka yanzu!',
        'Submit bill form': 'Sallama fom ɗin kuɗin biyan kuɗi',
        'Edit Bill': 'Gyara Kuɗin Biyan Kuɗi',
        'Update your bill details': 'Sabunta bayanan kuɗin biyan kuɗin ka',
        'Update Bill': 'Sabunta Kuɗin Biyan Kuɗi',
        'Complete Bill': 'Cika Kuɗin Biyan Kuɗi',
        'Mark as Paid': 'Alama a matsayin An Biya',
        'Food and Groceries': 'Abinci da Kayayyakin Abinci',
        'Transport': 'Sufuri',
        'Housing': 'Gidaje',
        'Utilities': 'Kayan Aiki',
        'Entertainment': 'Nishaɗi',
        'Other': 'Sauran',
        'Unlock Your Financial Freedom': 'Buɗe Yancin Kuɗin Ku',
        'Access essential tools and insights to understand, manage, and grow your finances across Africa': 'Samun kayan aiki masu mahimmanci da fahimta don fahimta, sarrafawa, da haɓaka kuɗin ku a duk faɗin Afirka',
        'Why Ficore Africa?': 'Me yasa Ficore Afirka?',
        'Localized for Africa with support for Naira and regional financial contexts': 'An keɓance shi don Afirka tare da tallafi ga Naira da yanayin kuɗi na yanki',
        'Empowers financial literacy with easy-to-use tools': 'Yana ƙarfafa ilimin kuɗi tare da kayan aiki masu sauƙin amfani',
        'Provides actionable insights for better financial decisions': 'Yana ba da fahimta mai aiki don mafi kyawun yanke shawara na kuɗi',
        'Assess your financial health with a personalized score and insights': 'Tantance lafiyar kuɗin ku tare da maki na keɓaɓɓu da fahimta',
        'This tool evaluates your income, expenses, and debt to provide a health score': 'Wannan kayan aiki yana kimanta kuɗin shiga, kashe kuɗi, da bashi don samar da makin lafiya',
        'Get Started with Financial Health Score': 'Fara da Makin Lafiyar Kuɗi',
        'Calculate your net worth by evaluating your assets and liabilities': 'Lissafa darajar dukiyarka ta hanyar kimanta kadarori da basussuka',
        'Net worth is calculated as assets minus liabilities': 'Darajar dukiya ana lissafa kamar kadarori ban da basussuka',
        'Get Started with Net Worth Calculator': 'Fara da Kalkuletar Darajar Dukiya',
        'Plan your emergency fund to cover unexpected expenses': 'Shirya kuɗin gaggawa don rufe kashe kuɗin da ba a ji tsammani ba',
        'Aims to cover 3-6 months of expenses for financial security': 'Yana nufin rufe kashe kuɗin watanni 3-6 don tsaron kuɗi',
        'Get Started with Emergency Fund Calculator': 'Fara da Kalkuletar Kuɗin Gaggawa',
        'Test your financial knowledge and get personalized tips': 'Gwada ilimin kuɗin ku kuma sami shawarwari na keɓaɓɓu',
        'Answer a series of questions to assess your financial literacy': 'Amsa jerin tambayoyi don tantance ilimin kuɗin ku',
        'Get Started with Financial Personality Quiz': 'Fara da Gwajin Halin Kuɗi',
        'Create a budget to manage your income and expenses effectively': 'Ƙirƙiri kasafin kuɗi don sarrafa kuɗin shiga da kashe kuɗi yadda ya kamata',
        'Helps you allocate your income across various expense categories': 'Yana taimakawa wajen raba kuɗin shiga a cikin nau’ikan kashe kuɗi daban-daban',
        'Get Started with Weekly Budget Planner': 'Fara da Mai Tsara Kasafin Mako-mako'
    }
}

# Constants
SCOPES = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
SPREADSHEET_ID = '13hbiMTMRBHo9MHjWwcugngY_aSiuxII67HCf03MiZ8I'
FEEDBACK_FORM_URL = 'https://forms.gle/1g1FVulyf7ZvvXr7G0q7hAKwbGJMxV4blpjBuqrSjKzQ'
WAITLIST_FORM_URL = 'https://forms.gle/17e0XYcp-z3hCl0I-j2JkHoKKJrp4PfgujsK8D7uqNxo'
CONSULTANCY_FORM_URL = 'https://forms.gle/1TKvlT7OTvNS70YNd8DaPpswvqd9y7hKydxKr07gpK9A'
SHEET_NAMES = {
    'submissions': 'Submissions',
    'net_worth': 'NetWorth',
    'emergency_fund': 'EmergencyFund',
    'quiz': 'Quiz',
    'budget': 'Budget',
    'expense_tracker': 'ExpenseTracker',
    'bill_planner': 'BillPlanner'
}
PREDETERMINED_HEADERS = {
    'Submissions': ['ID', 'First Name', 'Last Name', 'Email', 'Phone Number', 'Language', 'Business Name', 'User Type', 'Income/Revenue', 'Expenses/Costs', 'Debt/Loan', 'Debt Interest Rate', 'Timestamp'],
    'NetWorth': ['ID', 'First Name', 'Email', 'Language', 'Assets', 'Liabilities', 'Net Worth', 'Timestamp'],
    'EmergencyFund': ['ID', 'First Name', 'Email', 'Language', 'Monthly Expenses', 'Recommended Fund', 'Timestamp'],
    'Quiz': ['ID', 'First Name', 'Email', 'Language', 'Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Score', 'Personality Type', 'Timestamp'],
    'Budget': ['ID', 'First Name', 'Email', 'Language', 'Monthly Income', 'Housing Expenses', 'Food Expenses', 'Transport Expenses', 'Other Expenses', 'Savings', 'Timestamp'],
    'ExpenseTracker': ['ID', 'User Email', 'Amount', 'Category', 'Date', 'Description', 'Timestamp'],
    'BillPlanner': ['ID', 'User Email', 'Bill Name', 'Amount', 'Due Date', 'Status', 'Timestamp']
}
CATEGORIES = [
    ('Food and Groceries', 'Food and Groceries'),
    ('Transport', 'Transport'),
    ('Housing', 'Housing'),
    ('Utilities', 'Utilities'),
    ('Entertainment', 'Entertainment'),
    ('Other', 'Other')
]

# Google Sheets Setup
def get_sheets_client():
    creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPES)
    client = gspread.authorize(creds)
    return client

def ensure_sheet_and_headers(sheet_name, headers):
    client = get_sheets_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=len(headers))
        worksheet.append_row(headers)
    existing_headers = worksheet.row_values(1)
    if existing_headers != headers:
        worksheet.clear()
        worksheet.append_row(headers)
    return worksheet

# Forms
class SubmissionForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[Optional()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    auto_email = EmailField('Confirm Email', validators=[DataRequired(), Email()])
    phone_number = StringField('Phone Number', validators=[Optional()])
    language = SelectField('Language', choices=[('English', 'English'), ('Hausa', 'Hausa')], validators=[DataRequired()])
    business_name = StringField('Business Name', validators=[DataRequired()])
    user_type = SelectField('User Type', choices=[('Individual', 'Individual'), ('Business', 'Business')], validators=[DataRequired()])
    income_revenue = FloatField('Income/Revenue', validators=[DataRequired(), NumberRange(min=0)])
    expenses_costs = FloatField('Expenses/Costs', validators=[DataRequired(), NumberRange(min=0)])
    debt_loan = FloatField('Debt/Loan', validators=[DataRequired(), NumberRange(min=0)])
    debt_interest_rate = FloatField('Debt Interest Rate (%)', validators=[DataRequired(), NumberRange(min=0, max=100)])
    submit = SubmitField('Submit')

class NetWorthForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    language = SelectField('Language', choices=[('English', 'English'), ('Hausa', 'Hausa')], validators=[DataRequired()])
    assets = FloatField('Assets', validators=[DataRequired(), NumberRange(min=0)])
    liabilities = FloatField('Liabilities', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Get your net worth instantly!')

class EmergencyFundForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    language = SelectField('Language', choices=[('English', 'English'), ('Hausa', 'Hausa')], validators=[DataRequired()])
    monthly_expenses = FloatField('Monthly Expenses', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Calculate Your Recommended Fund Size')

class QuizForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    language = SelectField('Language', choices=[('English', 'English'), ('Hausa', 'Hausa')], validators=[DataRequired()])
    q1 = SelectField('Question 1', choices=[('Yes', 'Yes'), ('No', 'No')], validators=[DataRequired()])
    q2 = SelectField('Question 2', choices=[('Yes', 'Yes'), ('No', 'No')], validators=[DataRequired()])
    q3 = SelectField('Question 3', choices=[('Yes', 'Yes'), ('No', 'No')], validators=[DataRequired()])
    q4 = SelectField('Question 4', choices=[('Yes', 'Yes'), ('No', 'No')], validators=[DataRequired()])
    q5 = SelectField('Question 5', choices=[('Yes', 'Yes'), ('No', 'No')], validators=[DataRequired()])
    submit = SubmitField('Uncover Your Financial Style')

class BudgetForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    auto_email = EmailField('Confirm Email', validators=[DataRequired(), Email()])
    language = SelectField('Language', choices=[('English', 'English'), ('Hausa', 'Hausa')], validators=[DataRequired()])
    monthly_income = FloatField('Monthly Income', validators=[DataRequired(), NumberRange(min=0)])
    housing_expenses = FloatField('Housing Expenses', validators=[DataRequired(), NumberRange(min=0)])
    food_expenses = FloatField('Food Expenses', validators=[DataRequired(), NumberRange(min=0)])
    transport_expenses = FloatField('Transport Expenses', validators=[DataRequired(), NumberRange(min=0)])
    other_expenses = FloatField('Other Expenses', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Start Planning Your Budget!')

class ExpenseForm(FlaskForm):
    amount = FloatField('Amount', validators=[DataRequired(), NumberRange(min=0)])
    category = SelectField('Category', choices=CATEGORIES, validators=[DataRequired()])
    date = StringField('Date', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional()])
    submit = SubmitField('Submit Expense')

class BillForm(FlaskForm):
    bill_name = StringField('Bill Name', validators=[DataRequired()])
    amount = FloatField('Amount', validators=[DataRequired(), NumberRange(min=0)])
    due_date = StringField('Due Date', validators=[DataRequired()])
    status = SelectField('Status', choices=[('Pending', 'Pending'), ('Paid', 'Paid')], validators=[DataRequired()])
    submit = SubmitField('Submit Bill')

# Helper Functions
def calculate_health_score(form_data):
    income = form_data.get('income_revenue', 0)
    expenses = form_data.get('expenses_costs', 0)
    debt = form_data.get('debt_loan', 0)
    interest_rate = form_data.get('debt_interest_rate', 0)
    savings_ratio = (income - expenses) / income if income > 0 else 0
    debt_to_income = debt / income if income > 0 else 1
    score = 100 * (0.5 * savings_ratio - 0.3 * debt_to_income - 0.2 * (interest_rate / 100))
    return max(0, min(100, round(score)))

def get_score_description(score):
    if score >= 80:
        return translations['English']['Strong Financial Health']
    elif score >= 50:
        return translations['English']['Stable Finances']
    elif score >= 20:
        return translations['English']['Financial Strain']
    else:
        return translations['English']['Urgent Attention Needed']

def suggest_category(description):
    if not description:
        return 'Other'
    description = description.lower()
    if any(keyword in description for keyword in ['food', 'groceries', 'market']):
        return 'Food and Groceries'
    elif any(keyword in description for keyword in ['transport', 'fuel', 'bus', 'taxi']):
        return 'Transport'
    elif any(keyword in description for keyword in ['rent', 'mortgage', 'housing']):
        return 'Housing'
    elif any(keyword in description for keyword in ['electricity', 'water', 'internet']):
        return 'Utilities'
    elif any(keyword in description for keyword in ['movie', 'concert', 'entertainment']):
        return 'Entertainment'
    return 'Other'

def parse_natural_date(date_str):
    try:
        parsed_date = parse(date_str, fuzzy=True)
        return parsed_date.strftime('%Y-%m-%d')
    except ValueError:
        return datetime.now().strftime('%Y-%m-%d')

def calculate_running_balance(email):
    worksheet = ensure_sheet_and_headers(SHEET_NAMES['expense_tracker'], PREDETERMINED_HEADERS['ExpenseTracker'])
    records = worksheet.get_all_records()
    user_expenses = [r for r in records if r['User Email'] == email]
    user_expenses.sort(key=lambda x: datetime.strptime(x['Date'], '%Y-%m-%d'))
    balance = 0
    for expense in user_expenses:
        balance -= float(expense['Amount'])
        expense['Running Balance'] = balance
    return user_expenses, balance

def generate_insights(email):
    expenses, balance = calculate_running_balance(email)
    if not expenses:
        return []
    categories = {}
    for expense in expenses:
        cat = expense['Category']
        categories[cat] = categories.get(cat, 0) + float(expense['Amount'])
    total_spent = sum(categories.values())
    insights = []
    for cat, amount in categories.items():
        percentage = (amount / total_spent) * 100 if total_spent > 0 else 0
        if percentage > 30:
            insights.append(f"You spent {percentage:.1f}% of your expenses on {cat}. Consider reviewing this category for savings.")
    if balance < 0:
        insights.append("Your running balance is negative. Prioritize reducing expenses or increasing income.")
    return insights

# Routes
@app.route('/')
def index():
    language = session.get('language', 'English')
    return render_template('landing.html', language=language, translations=translations[language], FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)

@app.route('/set_language', methods=['POST'])
def set_language():
    language = request.form.get('language', 'English')
    session['language'] = language
    return redirect(url_for('index'))

@app.route('/financial_health')
def financial_health():
    language = session.get('language', 'English')
    form = SubmissionForm()
    return render_template('health_score_form.html', form=form, language=language, translations=translations[language])

@app.route('/submit', methods=['POST'])
def submit():
    form = SubmissionForm()
    language = session.get('language', 'English')
    t = translations[language]
    if form.validate_on_submit():
        if form.email.data != form.auto_email.data:
            flash(t['Emails Do Not Match'], 'error')
            return redirect(url_for('financial_health'))
        worksheet = ensure_sheet_and_headers(SHEET_NAMES['submissions'], PREDETERMINED_HEADERS['Submissions'])
        submission_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data = [
            submission_id,
            form.first_name.data,
            form.last_name.data,
            form.email.data,
            form.phone_number.data,
            form.language.data,
            form.business_name.data,
            form.user_type.data,
            form.income_revenue.data,
            form.expenses_costs.data,
            form.debt_loan.data,
            form.debt_interest_rate.data,
            timestamp
        ]
        worksheet.append_row(data)
        health_score = calculate_health_score(form.data)
        score_description = get_score_description(health_score)
        
        # Send Email
        try:
            msg = Message(
                t['Score Report Subject'].format(user_name=form.first_name.data),
                sender=app.config['MAIL_USERNAME'],
                recipients=[form.email.data]
            )
            msg.html = t['Email Body'].format(
                user_name=form.first_name.data,
                health_score=health_score,
                score_description=score_description,
                rank=random.randint(1, 1000),
                total_users=10000,
                course_url='https://youtube.com/@ficore.africa?si=xRuw7Ozcqbfmveru',
                course_title=t['Recommended Course'],
                FEEDBACK_FORM_URL=FEEDBACK_FORM_URL,
                WAITLIST_FORM_URL=WAITLIST_FORM_URL,
                CONSULTANCY_FORM_URL=CONSULTANCY_FORM_URL
            )
            mail.send(msg)
            flash(t['Email sent successfully'], 'success')
        except Exception as e:
            flash(t['Failed to send email'], 'error')

        flash(t['Submission Success'], 'success')
        return redirect(url_for('dashboard', health_score=health_score, score_description=score_description))
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(error, 'error')
        return redirect(url_for('financial_health'))

@app.route('/dashboard')
def dashboard():
    language = session.get('language', 'English')
    health_score = request.args.get('health_score', type=int, default=0)
    score_description = request.args.get('score_description', '')
    return render_template('health_score_dashboard.html', health_score=health_score, score_description=score_description, language=language, translations=translations[language])

@app.route('/net_worth', methods=['GET', 'POST'])
def net_worth():
    language = session.get('language', 'English')
    form = NetWorthForm()
    if form.validate_on_submit():
        worksheet = ensure_sheet_and_headers(SHEET_NAMES['net_worth'], PREDETERMINED_HEADERS['NetWorth'])
        net_worth = form.assets.data - form.liabilities.data
        submission_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data = [
            submission_id,
            form.first_name.data,
            form.email.data,
            form.language.data,
            form.assets.data,
            form.liabilities.data,
            net_worth,
            timestamp
        ]
        worksheet.append_row(data)
        flash(translations[language]['Submission Success'], 'success')
        return redirect(url_for('dashboard'))
    return render_template('net_worth_form.html', form=form, language=language, translations=translations[language])

@app.route('/emergency_fund', methods=['GET', 'POST'])
def emergency_fund():
    language = session.get('language', 'English')
    form = EmergencyFundForm()
    if form.validate_on_submit():
        worksheet = ensure_sheet_and_headers(SHEET_NAMES['emergency_fund'], PREDETERMINED_HEADERS['EmergencyFund'])
        recommended_fund = form.monthly_expenses.data * 6
        submission_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data = [
            submission_id,
            form.first_name.data,
            form.email.data,
            form.language.data,
            form.monthly_expenses.data,
            recommended_fund,
            timestamp
        ]
        worksheet.append_row(data)
        flash(translations[language]['Submission Success'], 'success')
        return redirect(url_for('dashboard'))
    return render_template('emergency_fund_form.html', form=form, language=language, translations=translations[language])

@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    language = session.get('language', 'English')
    form = QuizForm()
    if form.validate_on_submit():
        worksheet = ensure_sheet_and_headers(SHEET_NAMES['quiz'], PREDETERMINED_HEADERS['Quiz'])
        score = sum(1 for q in ['q1', 'q2', 'q3', 'q4', 'q5'] if form[q].data == 'Yes')
        personality_types = {
            5: 'Financial Guru',
            4: 'Prudent Planner',
            3: 'Balanced Budgeter',
            2: 'Casual Spender',
            1: 'Risky Rover',
            0: 'Free Spirit'
        }
        personality = personality_types.get(score, 'Balanced Budgeter')
        submission_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data = [
            submission_id,
            form.first_name.data,
            form.email.data,
            form.language.data,
            form.q1.data,
            form.q2.data,
            form.q3.data,
            form.q4.data,
            form.q5.data,
            score,
            personality,
            timestamp
        ]
        worksheet.append_row(data)
        flash(translations[language]['Submission Success'], 'success')
        return redirect(url_for('dashboard'))
    return render_template('quiz_form.html', form=form, language=language, translations=translations[language])

@app.route('/budget', methods=['GET', 'POST'])
def budget():
    language = session.get('language', 'English')
    form = BudgetForm()
    if form.validate_on_submit():
        if form.email.data != form.auto_email.data:
            flash(translations[language]['Emails Do Not Match'], 'error')
            return redirect(url_for('budget'))
        worksheet = ensure_sheet_and_headers(SHEET_NAMES['budget'], PREDETERMINED_HEADERS['Budget'])
        total_expenses = sum([form.housing_expenses.data, form.food_expenses.data, form.transport_expenses.data, form.other_expenses.data])
        savings = form.monthly_income.data - total_expenses
        submission_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data = [
            submission_id,
            form.first_name.data,
            form.email.data,
            form.language.data,
            form.monthly_income.data,
            form.housing_expenses.data,
            form.food_expenses.data,
            form.transport_expenses.data,
            form.other_expenses.data,
            savings,
            timestamp
        ]
        worksheet.append_row(data)
        flash(translations[language]['Submission Success'], 'success')
        return redirect(url_for('dashboard'))
    return render_template('budget_form.html', form=form, language=language, translations=translations[language])

@app.route('/expense_tracker', methods=['GET', 'POST'])
def expense_tracker():
    language = session.get('language', 'English')
    form = ExpenseForm()
    user_email = session.get('user_email', '')
    
    if form.validate_on_submit():
        suggested_category = suggest_category(form.description.data)
        parsed_date = parse_natural_date(form.date.data)
        expense_id = str(uuid.uuid4())
        expense = {
            'ID': expense_id,
            'User Email': user_email,
            'Amount': form.amount.data,
            'Category': form.category.data,
            'Date': parsed_date,
            'Description': form.description.data or '',
            'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Cache in session
        if 'expenses' not in session:
            session['expenses'] = []
        session['expenses'].append(expense)
        session.modified = True
        
        # Save to Google Sheets
        worksheet = ensure_sheet_and_headers(SHEET_NAMES['expense_tracker'], PREDETERMINED_HEADERS['ExpenseTracker'])
        worksheet.append_row(list(expense.values()))
        
        flash(translations[language]['Submission Success'], 'success')
        return redirect(url_for('expense_tracker'))
    
    # Retrieve expenses from session or Google Sheets
    expenses = session.get('expenses', [])
    if not expenses and user_email:
        worksheet = ensure_sheet_and_headers(SHEET_NAMES['expense_tracker'], PREDETERMINED_HEADERS['ExpenseTracker'])
        records = worksheet.get_all_records()
        expenses = [r for r in records if r['User Email'] == user_email]
        session['expenses'] = expenses
        session.modified = True
    
    insights = generate_insights(user_email) if user_email else []
    expenses, balance = calculate_running_balance(user_email)
    
    return render_template('expense_tracker_form.html', form=form, expenses=expenses, balance=balance, insights=insights, language=language, translations=translations[language])

@app.route('/expense_submit', methods=['POST'])
def expense_submit():
    language = session.get('language', 'English')
    form = ExpenseForm()
    user_email = session.get('user_email', '')
    
    if form.validate_on_submit():
        suggested_category = suggest_category(form.description.data)
        parsed_date = parse_natural_date(form.date.data)
        expense_id = str(uuid.uuid4())
        expense = {
            'ID': expense_id,
            'User Email': user_email,
            'Amount': form.amount.data,
            'Category': form.category.data,
            'Date': parsed_date,
            'Description': form.description.data or '',
            'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Cache in session
        if 'expenses' not in session:
            session['expenses'] = []
        session['expenses'].append(expense)
        session.modified = True
        
        # Save to Google Sheets
        worksheet = ensure_sheet_and_headers(SHEET_NAMES['expense_tracker'], PREDETERMINED_HEADERS['ExpenseTracker'])
        worksheet.append_row(list(expense.values()))
        
        flash(translations[language]['Submission Success'], 'success')
        return redirect(url_for('expense_tracker'))
    
    return redirect(url_for('expense_tracker'))

@app.route('/bill_planner', methods=['GET', 'POST'])
def bill_planner():
    language = session.get('language', 'English')
    form = BillForm()
    user_email = session.get('user_email', '')
    
    if form.validate_on_submit():
        parsed_due_date = parse_natural_date(form.due_date.data)
        bill_id = str(uuid.uuid4())
        bill = {
            'ID': bill_id,
            'User Email': user_email,
            'Bill Name': form.bill_name.data,
            'Amount': form.amount.data,
            'Due Date': parsed_due_date,
            'Status': form.status.data,
            'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Cache in session
        if 'bills' not in session:
            session['bills'] = []
        session['bills'].append(bill)
        session.modified = True
        
        # Save to Google Sheets
        worksheet = ensure_sheet_and_headers(SHEET_NAMES['bill_planner'], PREDETERMINED_HEADERS['BillPlanner'])
        worksheet.append_row(list(bill.values()))
        
        flash(translations[language]['Submission Success'], 'success')
        return redirect(url_for('bill_planner'))
    
    # Retrieve bills from session or Google Sheets
    bills = session.get('bills', [])
    if not bills and user_email:
        worksheet = ensure_sheet_and_headers(SHEET_NAMES['bill_planner'], PREDETERMINED_HEADERS['BillPlanner'])
        records = worksheet.get_all_records()
        bills = [r for r in records if r['User Email'] == user_email]
        session['bills'] = bills
        session.modified = True
    
    return render_template('bill_planner_form.html', form=form, bills=bills, language=language, translations=translations[language])

if __name__ == '__main__':
    app.run(debug=True)
