import logging
from flask import session, has_request_context
from typing import Dict, Any

# Set up logger to match app.py's logging configuration
logger = logging.getLogger('ficore_app.translations')
logger.setLevel(logging.INFO)

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
    ('translations_dashboard', 'DASHBOARD_TRANSLATIONS'),
    ('translations_emergency_fund', 'EMERGENCY_FUND_TRANSLATIONS'),
    ('translations_financial_health', 'FINANCIAL_HEALTH_TRANSLATIONS'),
    ('translations_net_worth', 'NET_WORTH_TRANSLATIONS'),
    ('translations_core', 'CORE_TRANSLATIONS'),
    ('translations_learning_hub', 'LEARNING_HUB_TRANSLATIONS'),
]

# Mapping of key prefixes to their respective modules
KEY_PREFIX_TO_MODULE = {
    'quiz_': 'translations_quiz',
    'mailersend_': 'translations_mailersend',
    'bill_': 'translations_bill',
    'budget_': 'translations_budget',
    'dashboard_': 'translations_dashboard',
    'emergency_fund_': 'translations_emergency_fund',
    'financial_health_': 'translations_financial_health',
    'net_worth_': 'translations_net_worth',
    'core_': 'translations_core',
    'learning_hub_': 'translations_learning_hub',
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
    Logs a warning if the key is not found in any module.
    Supports string formatting with kwargs.
    """
    # Default to 'en' if lang is None, using 'lang' from session to match bill/quiz blueprints
    if lang is None:
        lang = session.get('lang', 'en') if has_request_context() else 'en'

    # Use 'sid' to match blueprint session key
    session_id = session.get('sid', 'no-session-id') if has_request_context() else 'no-session-id'
    logger.debug(f"Translation request: key={key}, lang={lang} [session: {session_id}]")

    # Validate language
    if lang not in TRANSLATIONS:
        logger.warning(f"Language {lang} not found in translations, falling back to 'en' [session: {session_id}]")
        lang = 'en'

    # Get the translation from the combined TRANSLATIONS dictionary
    translation = TRANSLATIONS.get(lang, {}).get(key, None)

    # If not found, try English as fallback
    if translation is None:
        translation = TRANSLATIONS['en'].get(key, key)

    # Check if the translation is the key itself (indicating a missing translation)
    if translation == key:
        # Determine expected module based on prefix
        expected_module = 'unknown_module'
        for prefix, module in KEY_PREFIX_TO_MODULE.items():
            if key.startswith(prefix):
                expected_module = module
                break
        else:
            # For generic keys (no prefix), check all modules
            for module_name, _ in translation_modules:
                try:
                    module = __import__(f"translations.{module_name}", fromlist=[''])
                    translations = getattr(module, next(v for n, v in translation_modules if n == module_name))
                    if key in translations.get(lang, {}):
                        translation = translations[lang][key]
                        expected_module = module_name
                        break
                    elif key in translations.get('en', {}):
                        translation = translations['en'][key]
                        expected_module = module_name
                        break
                except (ImportError, AttributeError) as e:
                    logger.debug(f"Skipped module {module_name} for generic key check: {str(e)}")

        # Log warning if still not found
        if translation == key:
            logger.warning(
                f"Missing translation for key={key} in lang={lang}, "
                f"expected in module {expected_module} [session: {session_id}]"
            )

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
    if lang is None:
        lang = session.get('lang', 'en') if has_request_context() else 'en'

    if lang not in TRANSLATIONS:
        logger.warning(f"Language {lang} not found, returning English translations")
        lang = 'en'

    return TRANSLATIONS[lang]
