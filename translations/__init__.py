import logging
from flask import session, has_request_context
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

# Mapping of key prefixes to their respective modules
KEY_PREFIX_TO_MODULE = {
    'quiz_': 'translations_quiz',
    'mailersend_': 'translations_mailersend',
    'bill_': 'translations_bill',
    'budget_': 'translations_budget',
    'courses_': 'translations_courses',
    'dashboard_': 'translations_dashboard',
    'emergency_fund_': 'translations_emergency_fund',
    'financial_health_': 'translations_financial_health',
    'net_worth_': 'translations_net_worth',
    'core_': 'translations_core',
}

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
    Logs a warning if the key is not found in the expected module.
    Supports string formatting with kwargs.
    """
    # Default to 'en' if lang is None and we're not in a request context
    if lang is None:
        if has_request_context():
            lang = session.get('lang', 'en')
        else:
            lang = 'en'  # Default to English during initialization or outside request context
    
    # Debug logging for the translation request
    session_id = session.get('session_id', 'no-session-id') if has_request_context() else 'no-session-id'
    logger.debug(f"Translation request: key={key}, lang={lang} [session: {session_id}]")
    
    # Validate language
    if lang not in TRANSLATIONS:
        logger.warning(f"Language {lang} not found in translations, falling back to 'en' [session: {session_id}]")
        lang = 'en'
    
    # Get the translation, falling back to English, then the key itself
    translation = TRANSLATIONS.get(lang, {}).get(key, TRANSLATIONS['en'].get(key, key))
    
    # Check if the translation is the key itself (indicating a missing translation)
    if translation == key:
        # Determine which module should define this key based on its prefix
        expected_module = 'unknown_module'
        for prefix, module in KEY_PREFIX_TO_MODULE.items():
            if key.startswith(prefix):
                expected_module = module
                break
        logger.warning(f"Missing translation for key={key} in lang={lang}, expected in module {expected_module} [session: {session_id}]")
    
    # Log the translation result
    logger.debug(f"Translation result: key={key}, lang={lang}, result={translation} [session: {session_id}]")

    # Apply string formatting if kwargs provided
    try:
        return translation.format(**kwargs) if kwargs else translation
    except (KeyError, ValueError) as e:
        logger.warning(f"String formatting failed for key={key}, lang={lang}, kwargs={kwargs}: {str(e)} [session: {session_id}]")
        return translation

def get_translations(lang: str = None) -> Dict[str, str]:
    """
    Return the combined translations dictionary for the specified language.
    Falls back to English if the language is not found.
    """
    # Default to 'en' if lang is None and we're not in a request context
    if lang is None:
        if has_request_context():
            lang = session.get('lang', 'en')
        else:
            lang = 'en'  # Default to English during initialization or outside request context
    
    if lang not in TRANSLATIONS:
        logger.warning(f"Language {lang} not found, returning English translations")
        lang = 'en'
    
    return TRANSLATIONS[lang]
