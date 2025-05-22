import logging
from flask import session
from .translations_core import CORE_TRANSLATIONS
from .translations_dashboard import DASHBOARD_TRANSLATIONS
from .translations_financial_health import FINANCIAL_HEALTH_TRANSLATIONS
from .translations_budget import BUDGET_TRANSLATIONS
from .translations_quiz import QUIZ_TRANSLATIONS
from .translations_bill import BILL_TRANSLATIONS
from .translations_net_worth import NET_WORTH_TRANSLATIONS
from .translations_emergency_fund import EMERGENCY_FUND_TRANSLATIONS
from .translations_courses import COURSES_TRANSLATIONS
from .translations_mailersend import MAILERSEND_TRANSLATIONS

TRANSLATIONS = {}
TRANSLATIONS.update(CORE_TRANSLATIONS)
TRANSLATIONS.update(DASHBOARD_TRANSLATIONS)
TRANSLATIONS.update(FINANCIAL_HEALTH_TRANSLATIONS)
TRANSLATIONS.update(BUDGET_TRANSLATIONS)
TRANSLATIONS.update(QUIZ_TRANSLATIONS)
TRANSLATIONS.update(BILL_TRANSLATIONS)
TRANSLATIONS.update(NET_WORTH_TRANSLATIONS)
TRANSLATIONS.update(EMERGENCY_FUND_TRANSLATIONS)
TRANSLATIONS.update(COURSES_TRANSLATIONS)
TRANSLATIONS.update(MAILERSEND_TRANSLATIONS)

def trans(key, lang=None):
    """
    Retrieve a translation for the given key in the specified language.
    If lang is None, use the language from the session, defaulting to 'en'.
    """
    if lang is None:
        lang = session.get('lang', 'en')
    return TRANSLATIONS.get(lang, {}).get(key, key)

def get_translations(lang):
    """
    Retrieve all translations for the specified language.
    """
    return TRANSLATIONS.get(lang, {})
