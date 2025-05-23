import logging
from flask import session
from .translations_quiz import QUIZ_TRANSLATIONS
from .translations_mailersend import MAILERSEND_TRANSLATIONS
from .translations_bill import BILL_TRANSLATIONS
from .translations_budget import BUDGET_TRANSLATIONS
from .translations_courses import COURSES_TRANSLATIONS
from .translations_dashboard import DASHBOARD_TRANSLATIONS
from .translations_emergency_fund import EMERGENCY_FUND_TRANSLATIONS
from .translations_financial_health import FINANCIAL_HEALTH_TRANSLATIONS
from .translations_net_worth import NET_WORTH_TRANSLATIONS
from .translations_core import CORE_TRANSLATIONS

def trans(key, lang=None, **kwargs):
    """
    Translate a key using the appropriate language dictionary.
    Falls back to English or the key itself if translation is missing.
    Supports string formatting with kwargs.
    """
    if lang is None:
        lang = session.get('lang', 'en')
    
    # Combine translations from all modules
    translations = {
        'en': {
            **CORE_TRANSLATIONS.get('en', {}),
            **QUIZ_TRANSLATIONS.get('en', {}),
            **MAILERSEND_TRANSLATIONS.get('en', {}),
            **BILL_TRANSLATIONS.get('en', {}),
            **BUDGET_TRANSLATIONS.get('en', {}),
            **COURSES_TRANSLATIONS.get('en', {}),
            **DASHBOARD_TRANSLATIONS.get('en', {}),
            **EMERGENCY_FUND_TRANSLATIONS.get('en', {}),
            **FINANCIAL_HEALTH_TRANSLATIONS.get('en', {}),
            **NET_WORTH_TRANSLATIONS.get('en', {})
        },
        'ha': {
            **CORE_TRANSLATIONS.get('ha', {}),
            **QUIZ_TRANSLATIONS.get('ha', {}),
            **MAILERSEND_TRANSLATIONS.get('ha', {}),
            **BILL_TRANSLATIONS.get('ha', {}),
            **BUDGET_TRANSLATIONS.get('ha', {}),
            **COURSES_TRANSLATIONS.get('ha', {}),
            **DASHBOARD_TRANSLATIONS.get('ha', {}),
            **EMERGENCY_FUND_TRANSLATIONS.get('ha', {}),
            **FINANCIAL_HEALTH_TRANSLATIONS.get('ha', {}),
            **NET_WORTH_TRANSLATIONS.get('ha', {})
        }
    }

    # Get translation, fallback to English, then key
    # Debug logging
    logging.debug(f"Translation request: key={key}, lang={lang}")
    if lang not in translations:
        logging.warning(f"Language {lang} not found in translations, falling back to 'en'")
        lang = 'en'
    
    translation = translations.get(lang, {}).get(key, translations['en'].get(key, key))
    logging.debug(f"Translation result: key={key}, lang={lang}, result={translation}")

    # Apply string formatting if kwargs provided
    try:
        return translation.format(**kwargs) if kwargs else translation
    except (KeyError, ValueError) as e:
        logging.warning(f"String formatting failed for key={key}, lang={lang}, kwargs={kwargs}: {str(e)}")
        return translation

def get_translations(lang=None):
    """
    Return the combined translations dictionary for the specified language.
    Falls back to English if the language is not found.
    """
    if lang is None:
        lang = session.get('lang', 'en')
    
    translations = {
        'en': {
            **CORE_TRANSLATIONS.get('en', {}),
            **QUIZ_TRANSLATIONS.get('en', {}),
            **MAILERSEND_TRANSLATIONS.get('en', {}),
            **BILL_TRANSLATIONS.get('en', {}),
            **BUDGET_TRANSLATIONS.get('en', {}),
            **COURSES_TRANSLATIONS.get('en', {}),
            **DASHBOARD_TRANSLATIONS.get('en', {}),
            **EMERGENCY_FUND_TRANSLATIONS.get('en', {}),
            **FINANCIAL_HEALTH_TRANSLATIONS.get('en', {}),
            **NET_WORTH_TRANSLATIONS.get('en', {})
        },
        'ha': {
            **CORE_TRANSLATIONS.get('ha', {}),
            **QUIZ_TRANSLATIONS.get('ha', {}),
            **MAILERSEND_TRANSLATIONS.get('ha', {}),
            **BILL_TRANSLATIONS.get('ha', {}),
            **BUDGET_TRANSLATIONS.get('ha', {}),
            **COURSES_TRANSLATIONS.get('ha', {}),
            **DASHBOARD_TRANSLATIONS.get('ha', {}),
            **EMERGENCY_FUND_TRANSLATIONS.get('ha', {}),
            **FINANCIAL_HEALTH_TRANSLATIONS.get('ha', {}),
            **NET_WORTH_TRANSLATIONS.get('ha', {})
        }
    }

    if lang not in translations:
        logging.warning(f"Language {lang} not found, returning English translations")
        lang = 'en'
    
    return translations[lang]

def register_trans(app):
    """Register the trans function as a Jinja context processor."""
    @app.context_processor
    def inject_trans():
        return dict(trans=trans)
