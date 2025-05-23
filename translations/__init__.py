import logging
from flask import session
from typing import Dict, Any

# Set up logger to match app.py's logging configuration
logger = logging.getLogger('ficore_app.translations')
logger.setLevel(logging.DEBUG)

# Initialize TRANSLATIONS dictionary
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    'en': {},
    'ha': {},
}

# List of translation modules to import
translation_modules = [
    ('translations_quiz', 'QUIZ_TRANSLATIONS'),
    ('translations_mailersend', 'MAILERSEND_TRANSLATIONS'),
    ('translations_bill', 'BILL_TRANSLATIONS'),
    ('translations_budget', 'BUDGET_TRANSLATIONS'),
    ('translations_courses', 'COURSES_TRANSLATIONS'),
    ('translations_dashboard', 'DASHBOARD_TRANSLATIONS'),
    ('translations_emergency_fund', 'EMERGENCY_FUND_TRANSLATIONS'),
    ('translations_financial_health', 'FINANCIAL_HEALTH_TRANSLATIONS'),
    ('translations_net_worth', 'NET_WORTH_TRANSLATIONS'),
    ('translations_core', 'CORE_TRANSLATIONS'),
]

# Dynamically import each translation module and combine translations
for module_name, translations_var in translation_modules:
    try:
        module = __import__(f"translations.{module_name}", fromlist=[translations_var])
        translations = getattr(module, translations_var)
        for lang in ['en', 'ha']:
            if lang in translations:
                TRANSLATIONS[lang].update(translations[lang])
                logger.debug(f"Loaded {len(translations[lang])} translations from {module_name} for language '{lang}'")
    except ImportError as e:
        logger.error(f"Failed to import {module_name}: {str(e)}")
    except AttributeError as e:
        logger.error(f"Failed to access {translations_var} in {module_name}: {str(e)}")

# Log the total number of translations loaded
for lang in TRANSLATIONS:
    logger.debug(f"Total loaded {len(TRANSLATIONS[lang])} translations for language '{lang}'")

def trans(key: str, lang: str = None, **kwargs: Any) -> str:
    """
    Translate a key using the appropriate language dictionary.
    Falls back to English or the key itself if translation is missing.
    Supports string formatting with kwargs.
    """
    if lang is None:
        lang = session.get('lang', 'en')
    
    # Debug logging
    logger.debug(f"Translation request: key={key}, lang={lang}")
    if lang not in TRANSLATIONS:
        logger.warning(f"Language {lang} not found in translations, falling back to 'en'")
        lang = 'en'
    
    translation = TRANSLATIONS.get(lang, {}).get(key, TRANSLATIONS['en'].get(key, key))
    logger.debug(f"Translation result: key={key}, lang={lang}, result={translation}")

    # Apply string formatting if kwargs provided
    try:
        return translation.format(**kwargs) if kwargs else translation
    except (KeyError, ValueError) as e:
        logger.warning(f"String formatting failed for key={key}, lang={lang}, kwargs={kwargs}: {str(e)}")
        return translation

def get_translations(lang: str = None) -> Dict[str, str]:
    """
    Return the combined translations dictionary for the specified language.
    Falls back to English if the language is not found.
    """
    if lang is None:
        lang = session.get('lang', 'en')
    
    if lang not in TRANSLATIONS:
        logger.warning(f"Language {lang} not found, returning English translations")
        lang = 'en'
    
    return TRANSLATIONS[lang]
