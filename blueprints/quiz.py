from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, make_response
from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField, RadioField
from wtforms.validators import DataRequired, Email, Optional
import json
import uuid
from datetime import datetime
import pandas as pd
import threading
from flask_mail import Message

# Define the quiz blueprint
quiz_bp = Blueprint('quiz', __name__, template_folder='templates', static_folder='static', url_prefix='/quiz')

# Translation dictionary
QUIZ_TRANSLATIONS = {
    'en': {
        'quiz_financial_personality_quiz': 'Financial Personality Quiz',
        'quiz_enter_personal_information': 'Enter your personal information',
        'quiz_answer_questions_for_personality': 'Answer these questions to discover your financial personality',
        'quiz_step_progress': 'Step %(step)s of %(total)s',
        'quiz_your_financial_personality_results': 'Your financial personality results',
        'quiz_your_personality': 'Your Personality',
        'quiz_score': 'Score',
        'quiz_quiz_metrics': 'Quiz Metrics',
        'quiz_badges': 'Badges',
        'quiz_insights': 'Insights',
        'quiz_tips_for_improving_financial_habits': 'Tips for Improving Financial Habits',
        'quiz_call_to_actions': 'Call to Actions',
        'quiz_previous_quizzes': 'Previous Quizzes',
        'quiz_no_previous_quizzes': 'No previous quizzes',
        'quiz_no_quiz_data_available': 'No quiz data available',
        'quiz_start_quiz': 'Start Quiz',
        'quiz_retake_quiz': 'Retake Quiz',
        'quiz_create_budget': 'Create Budget',
        'quiz_calculate_net_worth': 'Calculate Net Worth',
        'quiz_config_error': 'Quiz configuration error. Please try again later.',
        'quiz_session_expired': 'Your session has expired. Please start over.',
        'quiz_submission_success': 'Quiz submitted successfully!',
        'quiz_check_inbox': 'Check your inbox for the quiz results.',
        'quiz_google_sheets_error': 'Failed to save results. Please try again.',
        'quiz_invalid_step': 'Invalid quiz step. Returning to start.',
        'core_first_name': 'First Name',
        'core_first_name_placeholder': 'e.g., Muhammad, Bashir, Umar',
        'core_first_name_tooltip': 'Enter your first name',
        'core_email': 'Email',
        'core_email_placeholder': 'e.g., muhammad@example.com',
        'core_email_tooltip': 'Enter your email to receive quiz results',
        'core_send_email': 'Send Email',
        'core_send_email_tooltip': 'Check to receive email with quiz results',
        'core_language': 'Language',
        'core_submit': 'Next',
        'core_back': 'Back',
        'core_continue': 'Continue',
        'core_see_results': 'See Results',
        'core_close': 'Close',
        'core_hello': 'Hello',
        'core_user': 'User',
        'core_date': 'Date',
        'core_created_at': 'Created At',
        'core_thank_you': 'Thank you for using Ficore Africa',
        'core_powered_by': 'Powered by Ficore Africa',
        'core_dear': 'Dear',
        'quiz_report_subject': 'Your Financial Personality Quiz Results',
        'quiz_quiz_summary_intro': 'Here is your financial personality quiz summary',
        'quiz_financial_behavior': 'Financial Behavior Breakdown',
        'quiz_your_answers': 'Your Answers',
        'quiz_yes': 'Yes',
        'quiz_no': 'No',
        'quiz_sometimes': 'Sometimes',
        'quiz_track_expenses_label': 'Do you track your expenses regularly?',
        'quiz_track_expenses_tooltip': 'Select how often you monitor your spending.',
        'quiz_track_expenses_placeholder': 'Select an option',
        'quiz_save_regularly_label': 'Do you save a portion of your income regularly?',
        'quiz_save_regularly_tooltip': 'Indicate your saving habits.',
        'quiz_save_regularly_placeholder': 'Select an option',
        'quiz_spend_non_essentials_label': 'Do you often spend on non-essential items?',
        'quiz_spend_non_essentials_tooltip': 'Consider luxury or discretionary purchases.',
        'quiz_spend_non_essentials_placeholder': 'Select an option',
        'quiz_plan_spending_label': 'Do you plan your spending in advance?',
        'quiz_plan_spending_tooltip': 'Think about budgeting or forecasting expenses.',
        'quiz_plan_spending_placeholder': 'Select an option',
        'quiz_impulse_purchases_label': 'Do you make impulse purchases frequently?',
        'quiz_impulse_purchases_tooltip': 'Reflect on unplanned buying decisions.',
        'quiz_impulse_purchases_placeholder': 'Select an option',
        'quiz_use_budget_label': 'Do you use a budget to manage your finances?',
        'quiz_use_budget_tooltip': 'Consider using budgeting apps or tools.',
        'quiz_use_budget_placeholder': 'Select an option',
        'quiz_invest_money_label': 'Do you invest your money regularly?',
        'quiz_invest_money_tooltip': 'Think about stocks, bonds, or other investments.',
        'quiz_invest_money_placeholder': 'Select an option',
        'quiz_emergency_fund_label': 'Do you have an emergency fund?',
        'quiz_emergency_fund_tooltip': 'Consider savings for unexpected expenses.',
        'quiz_emergency_fund_placeholder': 'Select an option',
        'quiz_set_financial_goals_label': 'Do you set financial goals?',
        'quiz_set_financial_goals_tooltip': 'Think about short-term or long-term financial targets.',
        'quiz_set_financial_goals_placeholder': 'Select an option',
        'quiz_seek_financial_advice_label': 'Do you seek financial advice?',
        'quiz_seek_financial_advice_tooltip': 'Consider consulting financial advisors or resources.',
        'quiz_seek_financial_advice_placeholder': 'Select an option',
        'quiz_planner_description': 'You are disciplined and plan your finances carefully, using tools like PiggyVest and setting clear goals.',
        'quiz_saver_description': 'You prioritize saving, often using Ajo/Esusu/Adashe, and are cautious with spending.',
        'quiz_balanced_description': 'You balance spending and saving, occasionally planning but open to impulse purchases.',
        'quiz_spender_description': 'You enjoy spending and may need to focus on budgeting and saving with apps like Moniepoint.',
        'quiz_avoider_description': 'You avoid financial planning and may benefit from starting with a simple budget.',
        'quiz_planner_insight': 'Strong financial planning.',
        'quiz_saver_insight': 'Excellent at saving.',
        'quiz_balanced_insight': 'Balanced saving/spending.',
        'quiz_spender_insight': 'Enjoy spending.',
        'quiz_avoider_insight': 'Planning is challenging.',
        'quiz_planner_tip': 'Set long-term goals.',
        'quiz_saver_tip': 'Consider investing.',
        'quiz_balanced_tip': 'Optimize with a budgeting app.',
        'quiz_spender_tip': 'Track expenses.',
        'quiz_avoider_tip': 'Start with a budget.',
        'badge_financial_guru': 'Financial Guru',
        'badge_savings_star': 'Savings Star',
        'badge_first_quiz_completed': 'First Quiz Completed!',
        'badge_needs_guidance': 'Needs Guidance!',
        'quiz_use_budgeting_app': 'Try using a budgeting app like PiggyVest or Moniepoint to track expenses.',
        'quiz_set_emergency_fund': 'Set up an emergency fund with Cowrywise for unexpected expenses.',
        'quiz_review_goals': 'Review your financial goals monthly to stay on track.',
        'quiz_personality_quiz': 'Personality Quiz',
        'quiz_assess_literacy': 'Assess Your Financial Literacy',
        'quiz_start_personality_quiz': 'Start Personality Quiz'
    },
    'ha': {
        'quiz_financial_personality_quiz': 'Tambayar Halayen Kuɗi',
        'quiz_enter_personal_information': 'Shigar da bayanan ka',
        'quiz_answer_questions_for_personality': 'Amsa waɗannan tambayoyin don gano halin kuɗin ka',
        'quiz_step_progress': 'Mataki %(step)s na %(total)s',
        'quiz_your_financial_personality_results': 'Sakamakon halin kuɗin ka',
        'quiz_your_personality': 'Halinka',
        'quiz_score': 'Maki',
        'quiz_quiz_metrics': 'Maƙasudin Tambaya',
        'quiz_badges': 'Alamomi',
        'quiz_insights': 'Hankali',
        'quiz_tips_for_improving_financial_habits': 'Shawarwari don Inganta Halayen Kuɗi',
        'quiz_call_to_actions': 'Kiraye zuwa Ayyuka',
        'quiz_previous_quizzes': 'Tambayoyin da Suka Gabata',
        'quiz_no_previous_quizzes': 'Babu tambayoyin da suka gabata',
        'quiz_no_quiz_data_available': 'Babu bayanan tambaya a yanzu',
        'quiz_start_quiz': 'Fara Tambaya',
        'quiz_retake_quiz': 'Sake Tambaya',
        'quiz_create_budget': 'Ƙirƙiri Kasafin Kuɗi',
        'quiz_calculate_net_worth': 'Ƙididdige Darajar Kuɗi',
        'quiz_config_error': 'Kuskuren saitin tambaya. Sake gwadawa daga baya.',
        'quiz_session_expired': 'Zaman ka ya ƙare. Fara daga farko.',
        'quiz_submission_success': 'An sallama tambaya cikin nasara!',
        'quiz_check_inbox': 'Duba akwatin saƙon ka don sakamakon tambaya.',
        'quiz_google_sheets_error': 'An kasa ajiye sakamako. Sake gwadawa.',
        'quiz_invalid_step': 'Matakin tambaya ba daidai ba ne. Komawa farko.',
        'core_first_name': 'Suna na Farko',
        'core_first_name_placeholder': 'misali, Muhammad, Bashir, Umar',
        'core_first_name_tooltip': 'Shigar da suna na farko',
        'core_email': 'Imel',
        'core_email_placeholder': 'misali, muhammad@example.com',
        'core_email_tooltip': 'Shigar da imel don karɓar sakamakon tambaya',
        'core_send_email': 'Aika Imel',
        'core_send_email_tooltip': 'Zaɓi don karɓar imel tare da sakamakon tambaya',
        'core_language': 'Harshe',
        'core_submit': 'Na gaba',
        'core_back': 'Baya',
        'core_continue': 'Ci gaba',
        'core_see_results': 'Duba Sakamako',
        'core_close': 'Rufe',
        'core_hello': 'Sannu',
        'core_user': 'Mai Amfani',
        'core_date': 'Kwanan Wata',
        'core_created_at': 'An Ƙirƙira A',
        'core_thank_you': 'Na gode da amfani da Ficore Africa',
        'core_powered_by': 'An ba da iko ta Ficore Africa',
        'core_dear': 'Mai Girma',
        'quiz_report_subject': 'Sakamakon Tambayar Halayen Kuɗin Ka',
        'quiz_quiz_summary_intro': 'Ga taƙaitaccen sakamakon tambayar halayen kuɗin ka',
        'quiz_financial_behavior': 'Rarrabuwar Halayen Kuɗi',
        'quiz_your_answers': 'Amsoshin Ka',
        'quiz_yes': 'Eh',
        'quiz_no': 'A’a',
        'quiz_sometimes': 'Wani lokaci',
        'quiz_track_expenses_label': 'Shin kana bin diddigin kashe kuɗin ka akai-akai?',
        'quiz_track_expenses_tooltip': 'Zaɓi sau nawa kake lura da kashe kuɗin ka.',
        'quiz_track_expenses_placeholder': 'Zaɓi zaɓi',
        'quiz_save_regularly_label': 'Shin kana ajiye wani ɓangare na kuɗin shigar ka akai-akai?',
        'quiz_save_regularly_tooltip': 'Nuna al’adun ajiye kuɗi.',
        'quiz_save_regularly_placeholder': 'Zaɓi zaɓi',
        'quiz_spend_non_essentials_label': 'Shin sau da yawa kana kashe kuɗi a kan abubuwan da ba su da muhimmanci?',
        'quiz_spend_non_essentials_tooltip': 'Ka ji tsammanin sayayya na alfarma ko na zaɓi.',
        'quiz_spend_non_essentials_placeholder': 'Zaɓi zaɓi',
        'quiz_plan_spending_label': 'Shin kana shirya kashe kuɗin ka a gaba?',
        'quiz_plan_spending_tooltip': 'Ka ji game da kasafin kuɗi ko ya.',
        'quiz_plan_spending_placeholder': 'Zaɓi zaɓi',
        'quiz_impulse_purchases_label': 'Shin sau da yawa kana sayen abubuwa ba tare da tunani ba?',
        'quiz_impulse_purchases_tooltip': 'Ka ji game da sayayya ba tare da shiri ba.',
        'quiz_impulse_purchases_placeholder': 'Zaɓi zaɓi',
        'quiz_use_budget_label': 'Shin kana amfani da kasafin kuɗi don sarrafa kuɗin ka?',
        'quiz_use_budget_tooltip': 'Ka ji game da amfani da manhajar kasafin kuɗi ko kayan aiki.',
        'quiz_use_budget_placeholder': 'Zaɓi zaɓi',
        'quiz_invest_money_label': 'Shin kana saka kuɗin ka akai-akai?',
        'quiz_invest_money_tooltip': 'Ka ji game da hannun jari, lamuni, ko wasu zuba jari.',
        'quiz_invest_money_placeholder': 'Zaɓi zaɓi',
        'quiz_emergency_fund_label': 'Shin kana da asusun gaggawa?',
        'quiz_emergency_fund_tooltip': 'Ka ji game da ajiyar kuɗi don kashe kuɗi ba zato ba tsammani.',
        'quiz_emergency_fund_placeholder': 'Zaɓi zaɓi',
        'quiz_set_financial_goals_label': 'Shin kana kafa maƙasudin kuɗi?',
        'quiz_set_financial_goals_tooltip': 'Ka ji game da maƙasudin kuɗi na ɗan gajeren lokaci ko na dogon lokaci.',
        'quiz_set_financial_goals_placeholder': 'Zaɓi zaɓi',
        'quiz_seek_financial_advice_label': 'Shin kana neman shawarar kuɗi?',
        'quiz_seek_financial_advice_tooltip': 'Ka ji game da tuntuɓar masu ba da shawara kan kuɗi ko albarkatu.',
        'quiz_seek_financial_advice_placeholder': 'Zaɓi zaɓi',
        'quiz_planner_description': 'Kana da shiri kuma kana shirya kuɗin ka da kyau, kuna amfani da kayan aiki kamar PiggyVest da kafa maƙasudi bayyananne.',
        'quiz_saver_description': 'Kana ba da fifiko ga ajiye kuɗi, sau da yawa kuna amfani da Ajo/Esusu/Adashe, kuma kana taka tsantsan da kashe kuɗi.',
        'quiz_balanced_description': 'Kana daidaita kashe kuɗi da ajiye kuɗi, wani lokaci kana shirya amma kuna buɗe don sayayya ba tare da shiri ba.',
        'quiz_spender_description': 'Kana jin daɗin kashe kuɗi kuma wataƙila kana buƙatar mai da hankali ga kasafin kuɗi da ajiye kuɗi tare da manhajoji kamar Moniepoint.',
        'quiz_avoider_description': 'Kana guje wa shirin kuɗi kuma wataƙila za ka ji daɗin farawa da kasafin kuɗi mai sauƙi.',
        'quiz_planner_insight': 'Shirin kuɗi mai ƙarfi.',
        'quiz_saver_insight': 'Kyakkyawan ajiye kuɗi.',
        'quiz_balanced_insight': 'Daidaitaccen ajiye/kashe kuɗi.',
        'quiz_spender_insight': 'Jin daɗin kashe kuɗi.',
        'quiz_avoider_insight': 'Shirin kuɗi yana da ƙalubale.',
        'quiz_planner_tip': 'Kafa maƙasudin kuɗi na dogon lokaci.',
        'quiz_saver_tip': 'Ka ji game da saka jari.',
        'quiz_balanced_tip': 'Inganta tare da manhajar kasafin kuɗi.',
        'quiz_spender_tip': 'Bin diddigin kashe kuɗi.',
        'quiz_avoider_tip': 'Fara da kasafin kuɗi.',
        'badge_financial_guru': 'Gurun Kuɗi',
        'badge_savings_star': 'Tauraron Ajiye Kuɗi',
        'badge_first_quiz_completed': 'Tambayar Farko An Kammala!',
        'badge_needs_guidance': 'Yana Bukatar Jagora!',
        'quiz_use_budgeting_app': 'Gwada amfani da manhajar kasafin kuɗi kamar PiggyVest ko Moniepoint don bin diddigin kashe kuɗi.',
        'quiz_set_emergency_fund': 'Kafa asusun gaggawa tare da Cowrywise don kashe kuɗi ba zato ba tsammani.',
        'quiz_review_goals': 'Duba maƙasudin kuɗin ka kowane wata don ci gaba da bin diddigi.',
        'quiz_personality_quiz': 'Tambayar Hali',
        'quiz_assess_literacy': 'Tantance Ilimin Kuɗin Ka',
        'quiz_start_personality_quiz': 'Fara Tambayar Hali'
    }
}

# Translation functions
def trans(key, lang='en', default=None):
    translation = QUIZ_TRANSLATIONS.get(lang, {}).get(key, default if default is not None else key)
    if translation == key:
        current_app.logger.warning(f"Missing translation for key={key} in lang={lang}, session: {session.get('sid', 'unknown')}")
    return translation

def get_translations(lang='en'):
    return QUIZ_TRANSLATIONS.get(lang, QUIZ_TRANSLATIONS['en'])

# Hardcoded questions (10 questions, using translation keys)
QUESTIONS = [
    {
        'id': 'question_1',
        'key': 'track_expenses',
        'text_key': 'quiz_track_expenses_label',
        'options': ['quiz_yes', 'quiz_sometimes', 'quiz_no'],
        'positive_answers': ['quiz_yes'],
        'negative_answers': ['quiz_no'],
        'weight': 10
    },
    {
        'id': 'question_2',
        'key': 'save_regularly',
        'text_key': 'quiz_save_regularly_label',
        'options': ['quiz_yes', 'quiz_sometimes', 'quiz_no'],
        'positive_answers': ['quiz_yes'],
        'negative_answers': ['quiz_no'],
        'weight': 10
    },
    {
        'id': 'question_3',
        'key': 'spend_non_essentials',
        'text_key': 'quiz_spend_non_essentials_label',
        'options': ['quiz_yes', 'quiz_sometimes', 'quiz_no'],
        'positive_answers': ['quiz_no'],
        'negative_answers': ['quiz_yes'],
        'weight': 10
    },
    {
        'id': 'question_4',
        'key': 'plan_spending',
        'text_key': 'quiz_plan_spending_label',
        'options': ['quiz_yes', 'quiz_sometimes', 'quiz_no'],
        'positive_answers': ['quiz_yes'],
        'negative_answers': ['quiz_no'],
        'weight': 10
    },
    {
        'id': 'question_5',
        'key': 'impulse_purchases',
        'text_key': 'quiz_impulse_purchases_label',
        'options': ['quiz_yes', 'quiz_sometimes', 'quiz_no'],
        'positive_answers': ['quiz_no'],
        'negative_answers': ['quiz_yes'],
        'weight': 10
    },
    {
        'id': 'question_6',
        'key': 'use_budget',
        'text_key': 'quiz_use_budget_label',
        'options': ['quiz_yes', 'quiz_sometimes', 'quiz_no'],
        'positive_answers': ['quiz_yes'],
        'negative_answers': ['quiz_no'],
        'weight': 10
    },
    {
        'id': 'question_7',
        'key': 'invest_money',
        'text_key': 'quiz_invest_money_label',
        'options': ['quiz_yes', 'quiz_sometimes', 'quiz_no'],
        'positive_answers': ['quiz_yes'],
        'negative_answers': ['quiz_no'],
        'weight': 10
    },
    {
        'id': 'question_8',
        'key': 'emergency_fund',
        'text_key': 'quiz_emergency_fund_label',
        'options': ['quiz_yes', 'quiz_no'],
        'positive_answers': ['quiz_yes'],
        'negative_answers': ['quiz_no'],
        'weight': 10
    },
    {
        'id': 'question_9',
        'key': 'set_financial_goals',
        'text_key': 'quiz_set_financial_goals_label',
        'options': ['quiz_yes', 'quiz_sometimes', 'quiz_no'],
        'positive_answers': ['quiz_yes'],
        'negative_answers': ['quiz_no'],
        'weight': 10
    },
    {
        'id': 'question_10',
        'key': 'seek_financial_advice',
        'text_key': 'quiz_seek_financial_advice_label',
        'options': ['quiz_yes', 'quiz_sometimes', 'quiz_no'],
        'positive_answers': ['quiz_yes'],
        'negative_answers': ['quiz_no'],
        'weight': 10
    }
]

# Define the QuizForm
class QuizForm(FlaskForm):
    first_name = StringField(
        label=trans('core_first_name'),
        validators=[DataRequired()],
        render_kw={'placeholder': trans('core_first_name_placeholder'), 'title': trans('core_first_name_tooltip'), 'aria-label': trans('core_first_name')}
    )
    email = StringField(
        label=trans('core_email'),
        validators=[DataRequired(), Email()],
        render_kw={'placeholder': trans('core_email_placeholder'), 'title': trans('core_email'), 'aria-label': trans('core_email')}
    )
    send_email = BooleanField(
        label=trans('core_send_email'),
        default=False,
        render_kw={'title': trans('core_send_email_tooltip'), 'aria-label': trans('core_send_email')}
    )
    submit = SubmitField(trans('core_submit'), render_kw={'aria-label': 'Submit Form'})
    back = SubmitField(trans('core_back'), render_kw={'aria-label': 'Go Back'})

    # Hardcoded question fields for steps 2+
    def __init__(self, personal_info=True, step_num=1, language='en', **kwargs):
        super().__init__(**kwargs)
        self.personal_info = personal_info
        self.step_num = step_num
        self.language = language

        # Dynamically add question fields based on step
        if not personal_info:
            del self.first_name
            del self.email
            # Define questions for each step
            if step_num == 2:
                question_indices = range(1, 6)  # Questions 1-5
            else:
                question_indices = range(6, 11)  # Questions 6-10
            for idx in question_indices:
                q = QUESTIONS[idx - 1]
                choices = [(opt, trans(opt, lang=language)) for opt in q['options']]
                setattr(
                    self,
                    q['id'],
                    RadioField(
                        label=trans(q['text_key'], lang=language),
                        choices=choices,
                        validators=[DataRequired()],
                        render_kw={'aria-label': trans(q['text_key'], lang=language), 'title': trans(f'{q["key"]}_tooltip', lang=language, default='')}
                    )
                )
            # Remove unused fields
            fields_to_keep = [f'question_{i}' for i in question_indices] + ['send_email', 'submit', 'back']
            for field_name in list(self._fields.keys()):
                if field_name not in fields_to_keep:
                    del self._fields[field_name]
        current_app.logger.debug(f"Initialized QuizForm: personal_info={personal_info}, step_num={step_num}, language={language}, fields={list(self._fields.keys())}")

    def validate(self, extra_validators=None):
        current_app.logger.debug(f"Validating QuizForm: fields={list(self._fields.keys())}")
        rv = super().validate(extra_validators)
        if not rv:
            current_app.logger.error(f"Validation errors: {self.errors}")
            flash(trans('quiz_form_errors', lang=self.language, default='Please correct the errors in the form.'), 'error')
        return rv

# Helper Functions
def calculate_score(answers):
    score = 0
    for question, answer in answers:
        if answer in question.get('positive_answers', []):
            score += 3
        elif answer in question.get('negative_answers', []):
            score -= 1
    return max(0, score)

def assign_personality(answers, language='en'):
    score = 0
    for question, answer in answers:
        weight = question.get('weight', 10)
        if answer in question.get('positive_answers', []):
            score += weight
        elif answer in question.get('negative_answers', []):
            score -= weight
    if score >= 60:
        return 'Planner', trans('quiz_planner_description', lang=language), trans('quiz_planner_tip', lang=language)
    elif score >= 40:
        return 'Saver', trans('quiz_saver_description', lang=language), trans('quiz_saver_tip', lang=language)
    elif score >= 20:
        return 'Balanced', trans('quiz_balanced_description', lang=language), trans('quiz_balanced_tip', lang=language)
    elif score >= 0:
        return 'Spender', trans('quiz_spender_description', lang=language), trans('quiz_spender_tip', lang=language)
    else:
        return 'Avoider', trans('quiz_avoider_description', lang=language), trans('quiz_avoider_tip', lang=language)

def assign_badges_quiz(user_df, all_users_df, language='en'):
    badges = []
    with open('badges.json', 'r', encoding='utf-8') as f:
        badge_configs = json.load(f)
    
    if user_df.empty:
        current_app.logger.warning("Empty user_df in assign_badges_quiz")
        return badges

    user_row = user_df.iloc[0]
    for badge in badge_configs:
        criteria = badge.get('criteria', {})
        badge_name = trans(f'badge_{badge["name"].lower().replace(" ", "_")}', lang=language, default=badge['name'])
        if (criteria.get('personality') == user_row['personality'] and
                user_row['score'] >= criteria.get('min_score', 0)):
            badges.append(badge_name)
        elif badge['name'] == 'First Quiz Completed!' and len(user_df) >= 1:
            badges.append(badge_name)
        elif badge['name'] == 'Needs Guidance!' and user_row['personality'] == 'Avoider' and len(all_users_df) > 10:
            badges.append(badge_name)
    
    return badges

def generate_quiz_summary_chart(answers, language='en'):
    labels = [trans(q['text_key'], lang=language) for q, _ in answers]
    scores = [3 if a in q.get('positive_answers', []) else -1 if a in q.get('negative_answers', []) else 0 for q, a in answers]
    return {
        'labels': labels,
        'datasets': [{
            'label': trans('quiz_your_answers', lang=language),
            'data': scores,
            'backgroundColor': 'rgba(30, 127, 113, 0.2)',
            'borderColor': '#1E7F71',
            'pointBackgroundColor': '#1E7F71',
            'pointBorderColor': '#fff',
            'pointHoverBackgroundColor': '#fff',
            'pointHoverBorderColor': '#1E7F71'
        }]
    }

def generate_insights_and_tips(personality, language='en'):
    insights = [trans(f'quiz_{personality.lower()}_insight', lang=language)]
    tips = [
        trans(f'quiz_{personality.lower()}_tip', lang=language),
        trans('quiz_use_budgeting_app', lang=language),
        trans('quiz_set_emergency_fund', lang=language),
        trans('quiz_review_goals', lang=language)
    ]
    return insights, tips

def append_to_google_sheet(data, headers, worksheet_name='Quiz', language='en'):
    try:
        storage_managers = current_app.config['STORAGE_MANAGERS']
        if storage_managers['sheets'].append_to_sheet(data, headers, worksheet_name):
            return True
        else:
            flash(trans('quiz_google_sheets_error', lang=language), 'error')
            return False
    except Exception as e:
        current_app.logger.error(f"Google Sheets append error: {e}")
        flash(trans('quiz_google_sheets_error', lang=language), 'error')
        return False

def send_quiz_email(to_email, user_name, personality, personality_desc, tip, answers, language='en'):
    try:
        msg = Message(
            subject=trans('quiz_report_subject', lang=language),
            recipients=[to_email],
            html=render_template(
                'quiz_email.html',
                trans=trans,
                user_name=user_name or trans('core_user', lang=language),
                personality=personality,
                personality_desc=personality_desc,
                tip=tip,
                answers=[(trans(q['text_key'], lang=language), trans(a, lang=language)) for q, a in answers],
                data={
                    'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
                    'score': calculate_score(answers),
                    'badges': session.get('quiz_results', {}).get('latest_record', {}).get('badges', [])
                },
                base_url=current_app.config.get('BASE_URL', ''),
                language=language
            )
        )
        current_app.extensions['mail'].send(msg)
        current_app.logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        current_app.logger.error(f"Email error to {to_email}: {e}")
        return False

def send_quiz_email_async(app, to_email, user_name, personality, personality_desc, tip, answers, language):
    with app.app_context():
        send_quiz_email(to_email, user_name, personality, personality_desc, tip, answers, language)

def partition_questions(questions, per_step=5):
    return [questions[i:i + per_step] for i in range(0, len(questions), per_step)]

# Setup session before every request
@quiz_bp.before_request
def setup_session():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
        session.permanent = True
        current_app.logger.debug(f"Initialized new session ID: {session['sid']}")
    if 'language' not in session:
        session['language'] = 'en'
        current_app.logger.debug(f"Set default language: en")
    session.modified = True

# Routes
@quiz_bp.route('/step1', methods=['GET', 'POST'])
def step1():
    language = session.get('language', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')

    if request.method == 'GET' and 'quiz_data' in session:
        session.pop('quiz_data', None)
        current_app.logger.debug(f"Cleared quiz_data for session: {session['sid']}")

    form = QuizForm(personal_info=True, language=language, formdata=request.form if request.method == 'POST' else None)
    form.submit.label.text = trans('quiz_start_quiz', lang=language)

    if request.method == 'POST':
        if form.validate_on_submit():
            session['quiz_data'] = {
                'first_name': form.first_name.data,
                'email': form.email.data,
                'send_email': form.send_email.data
            }
            session.modified = True
            current_app.logger.info(f"Step 1 validated, session: {session['quiz_data']}")

            progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
            progress = progress_storage.filter_by_session(session['sid'])
            course_progress = next((p for p in progress if p['data'].get('course_id') == course_id), None)
            if not course_progress:
                progress_data = {
                    'course_id': course_id,
                    'completed_tasks': [0],
                    'progress_percentage': (1 / (len(partition_questions(QUESTIONS)) + 1)) * 100,
                    'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                progress_storage.append(progress_data, session_id=session['sid'])
            else:
                if 0 not in course_progress['data'].get('completed_tasks', []):
                    course_progress['data']['completed_tasks'].append(0)
                    course_progress['data']['progress_percentage'] = (len(course_progress['data']['completed_tasks']) / (len(partition_questions(QUESTIONS)) + 1)) * 100
                    course_progress['data']['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    progress_storage.update_by_id(course_progress['id'], course_progress['data'])
            current_app.logger.info(f"Task 0 (step1) completed for course {course_id}")

            return redirect(url_for('quiz.quiz_step', step_num=1, course_id=course_id))
        else:
            current_app.logger.error(f"Validation failed: {form.errors}")
            flash(trans('quiz_form_errors', lang=language, default='Please correct the errors in the form.'), 'error')

    return render_template(
        'quiz_step1.html',
        form=form,
        course_id=course_id,
        trans=trans,
        language=language,
        base_url=current_app.config.get('BASE_URL', '')
    )

@quiz_bp.route('/step/<int:step_num>', methods=['GET', 'POST'])
def quiz_step(step_num):
    if 'sid' not in session or 'quiz_data' not in session:
        flash(trans('quiz_session_expired', lang=session.get('language', 'en')), 'error')
        return redirect(url_for('quiz.step1', course_id=request.args.get('course_id', 'financial_quiz')))

    language = session.get('language', 'en')
    steps = partition_questions(QUESTIONS, 5)
    if step_num < 1 or step_num > len(steps):
        flash(trans('quiz_invalid_step', lang=language), 'error')
        return redirect(url_for('quiz.step1', course_id=request.args.get('course_id', 'financial_quiz')))

    questions = steps[step_num - 1]
    form = QuizForm(personal_info=False, step_num=step_num + 1, language=language, formdata=request.form if request.method == 'POST' else None)
    form.submit_label.text = trans('core_see_results', lang=language) if step_num == len(steps) else trans('core_continue', lang=language)
    form.back_label.text = trans('core_back', lang=language)

    if request.method == 'POST' and form.validate_on_submit():
        session['quiz_data'].update({f['id']: form[f['id']].data for f in questions})
        session['quiz_data']['send_email'] = form.send_email.data
        session.modified = True

        course_id = request.args.get('course_id', 'financial_quiz')
        progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
        progress = progress_storage.filter_by_session(session['sid'])
        course_progress = next((p for p in progress if p['data'].get('course_id') == course_id), None)
        if course_progress and step_num not in course_progress['data'].get('completed_tasks', []):
            course_progress['data']['completed_tasks'].append(step_num)
            progress_storage.update_by_id(course_progress['id'], course_progress['data'])

        if step_num < len(steps):
            return redirect(url_for('quiz.quiz_step', step_num=step_num + 1, course_id=course_id))
        
        answers = [(QUESTIONS[int(k.split('_')[1]) - 1], v) for k, v in session['quiz_data'].items() if k.startswith('question_')]
        personality, personality_desc, tip = assign_personality(answers, language)
        score = calculate_score(answers)
        chart_data = generate_quiz_summary_chart(answers, language)
        user_df = pd.DataFrame([{
            'Timestamp': datetime.utcnow(),
            'first_name': session['quiz_data'].get('first_name', ''),
            'email': session['quiz_data'].get('email', ''),
            'language': language,
            'personality': personality,
            'score': score,
            **{f'question_{i}': trans(QUESTIONS[i-1]['text_key'], lang=language) for i in range(1, 11)},
            **{f'answer_{i}': trans(session['quiz_data'].get(f'question_{i}', ''), lang=language) for i in range(1, 11)}
        }])

        storage_managers = current_app.config['STORAGE_MANAGERS']
        all_users_df = storage_managers['sheets'].fetch_data_from_filter(
            headers=storage_managers['PREDETERMINED_HEADERS_QUIZ'],
            worksheet_name='Quiz'
        )

        badges = assign_badges_quiz(user_df, all_users_df, language)
        data = [
            datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
            session['quiz_data'].get('first_name', ''),
            session['quiz_data'].get('email', ''),
            language,
            *[trans(QUESTIONS[i-1]['text_key'], lang=language) for i in range(1, 11)],
            *[trans(session['quiz_data'].get(f'question_{i}', ''), lang=language) for i in range(1, 11)],
            personality,
            str(score),
            ','.join(badges),
            str(session['quiz_data'].get('send_email', False)).lower()
        ]

        if not append_to_google_sheet(data, storage_managers['PREDETERMINED_HEADERS_QUIZ'], 'Quiz', language):
            flash(trans('quiz_google_sheets_error', lang=language), 'error')
            return redirect(url_for('quiz.quiz_step', step_num=step_num, course_id=course_id))

        records = []
        if not all_users_df.empty:
            user_records = all_users_df[all_users_df['email'] == session['quiz_data'].get('email', '')].sort_values('Timestamp')
            for idx, row in user_records.iterrows():
                records.append({
                    'created_at': row['Timestamp'].strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(row['Timestamp']) else 'N/A',
                    'personality': row['personality'],
                    'score': int(row['score']) if pd.notnull(row['score']) else 0,
                    'badges': row['badges'].split(',') if pd.notnull(row['badges']) and row['badges'] else []
                })

        latest_record = records[0] if records else {}
        insights, tips = generate_insights_and_tips(personality, language)
        results = {
            'first_name': session['quiz_data'].get('first_name', ''),
            'personality': personality,
            'score': score,
            'badges': badges,
            'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
            'chart_data': chart_data,
            'insights': insights,
            'tips': tips
        }
        session['quiz_results'] = {
            'latest_record': results,
            'records': records,
            'insights': insights,
            'tips': tips
        }

        if session['quiz_data'].get('send_email') and session['quiz_data'].get('email'):
            threading.Thread(
                target=send_quiz_email_async,
                args=(current_app._get_current_object(), 
                      session['quiz_data']['email'], 
                      session['quiz_data']['first_name'], 
                      personality, 
                      personality_desc, 
                      tip, 
                      answers, 
                      language)
            ).start()
            flash(trans('quiz_check_inbox', lang=language), 'success')

        flash(trans('quiz_submission_success', lang=language))
        return redirect(url_for('quiz.results', course_id=course_id))

    if 'quiz_data' in session:
        current_app.logger.debug(f"Prepopulating form with session quiz_data: {session['quiz_data']}")
        for q in questions:
            if q['id'] in session['quiz_data']:
                try:
                    form[q['id']].data = session['quiz_data'][q['id']]
                except AttributeError:
                    current_app.logger.warning(f"Field {q['id']} not found in form for pre-population")
        try:
            form.send_email.data = bool(session['quiz_data'].get('send_email', False))
        except AttributeError as e:
            current_app.logger.error(f"Error prepopulating send_email: {e}")

    response = make_response(render_template(
        'quiz_step.html',
        form=form,
        questions=questions,
        step_num=step_num,
        total_steps=len(steps),
        course_id=course_id,
        trans=trans,
        language=language,
        base_url=current_app.config.get('BASE_URL', '')
    ))
    return response

@quiz_bp.route('/results', methods=['GET'])
def results():
    language = session.get('language', 'en')
    course_id = request.args.get('course_id', 'financial_quiz')
    results = session.get('quiz_results', {})

    if not results:
        flash(trans('quiz_session_expired', lang=language), 'error')
        return redirect(url_for('quiz.step1', course_id=course_id))

    session.pop('quiz_data', None)
    session.pop('quiz_results', {})
    session['language'] = language
    session.modified = True

    response = make_response(render_template(
        'quiz_results.html',
        latest_record=results.get('latest_record', {}),
        records=results.get('records', []),
        insights=results.get('insights', []),
        tips=results.get('tips', []),
        chart_data=results.get('latest_record', {}).get('chart_data', {}),
        course_id=course_id,
        trans=trans,
        language=language,
        base_url=current_app.config.get('BASE_URL', '')
    ))
    return response

@quiz_bp.errorhandler(Exception)
def handle_error(e):
    current_app.logger.error(f"Global error: {str(e)} [session: {session.get('sid', 'unknown')}]}", exc_info=True)
    flash(trans('quiz_config_error', lang=session.get('language', 'en')), 'error')
    return redirect(url_for('quiz.step1', course_id=request.args.get('course_id', 'financial_quiz')))
