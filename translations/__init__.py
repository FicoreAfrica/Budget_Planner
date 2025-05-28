import logging
from flask import session, has_request_context, g
from typing import Dict, Any

# Set up logger to match app.py's configuration
logger = logging.getLogger('ficore_app.translations')
logger.setLevel(logging.INFO)

# Explicitly import translation modules
try:
    from .translations_core import translations as translations_core
    from .translations_quiz import translations as translations_quiz
    from .translations_mailersend import translations as translations_mailersend
    from .translations_bill import translations as translations_bill
    from .translations_budget import translations as translations_budget
    from .translations_dashboard import translations as translations_dashboard
    from .translations_emergency_fund import translations as translations_emergency_fund
    from .translations_financial_health import translations as translations_financial_health
    from .translations_net_worth import translations as translations_net_worth
    from .translations_learning_hub import translations as translations_learning_hub
except ImportError as e:
    logger.error(f"Failed to import translation module: {e}")
    raise

# Map module names to their translation dictionaries
translation_modules = {
    'core': translations_core,
    'quiz': translations_quiz,
    'mailersend': translations_mailersend,
    'bill': translations_bill,
    'budget': translations_budget,
    'dashboard': translations_dashboard,
    'emergency_fund': translations_emergency_fund,
    'financial_health': translations_financial_health,
    'net_worth': translations_net_worth,
    'learning_hub': translations_learning_hub
}

# Map key prefixes to module names
KEY_PREFIX_TO_MODULE = {
    'core_': 'core',
    'quiz_': 'quiz',
    'mailersend_': 'mailersend',
    'bill_': 'bill',
    'budget_': 'budget',
    'dashboard_': 'dashboard',
    'emergency_fund_': 'emergency_fund',
    'financial_health_': 'financial_health',
    'net_worth_': 'net_worth',
    'learning_hub_': 'learning_hub'
}

# Log loaded translations for each module
for module_name, translations in translation_modules.items():
    for lang in ['en', 'ha']:
        lang_dict = translations.get(lang, {})
        logger.info(f"Loaded {len(lang_dict)} translations from module '{module_name}' for lang='{lang}'")
        if 'Yes' in lang_dict:
            logger.info(f"Confirmed 'Yes' key in module '{module_name}' for lang='{lang}'")
        if 'core_ficore_africa' in lang_dict:
            logger.info(f"Confirmed 'core_ficore_africa' key in module '{module_name}' for lang='{lang}'")

def trans(key: str, lang: str = None, **kwargs: Any) -> str:
    """
    Translate a key using the appropriate module's translation dictionary.
    Falls back to English or the key itself if translation is missing.
    Logs debug info for key lookups and warnings for missing translations.
    Supports string formatting with kwargs.
    """
    # Use g.log if in request context, else fallback to default logger
    current_logger = g.get('log', logger) if has_request_context() else logger
    session_id = session.get('sid', 'no-session-id') if has_request_context() else 'no-session-id'

    # Default to session language or 'en'
    if lang is None:
        lang = session.get('lang', 'en') if has_request_context() else 'en'
    
    current_logger.debug(f"Translation request: key={key}, lang={lang} [session: {session_id}]")

    # Determine module based on key prefix
    module_name = 'core'  # Default module
    for prefix, mod in KEY_PREFIX_TO_MODULE.items():
        if key.startswith(prefix):
            module_name = mod
            break

    module = translation_modules.get(module_name, translation_modules['core'])
    lang_dict = module.get(lang, {})
    
    # Log available keys for debugging
    current_logger.debug(
        f"Looking up key={key} in module={module_name}, lang={lang}, "
        f"available keys={list(lang_dict.keys())} [session: {session_id}]"
    )

    # Get translation
    translation = lang_dict.get(key, None)

    # Fallback to English if not found
    if translation is None:
        en_dict = module.get('en', {})
        translation = en_dict.get(key, key)
        if translation == key:
            current_logger.debug(
                f"Key={key} not found in module={module_name} for lang={lang} or en [session: {session_id}]"
            )

    # Log warning if translation is missing
    if translation == key:
        current_logger.warning(
            f"Missing translation for key={key} in lang={lang}, "
            f"expected in module translations_{module_name} [session: {session_id}]"
        )

    # Log translation result
    current_logger.debug(
        f"Translation result: key={key}, lang={lang}, result={translation} [session: {session_id}]"
    )

    # Apply string formatting
    try:
        return translation.format(**kwargs) if kwargs else translation
    except (KeyError, ValueError) as e:
        current_logger.warning(
            f"String formatting failed for key={key}, lang={lang}, kwargs={kwargs}: {e} [session: {session_id}]"
        )
        return translation

def get_translations(lang: str = None) -> Dict[str, str]:
    """
    Return a dictionary with a trans callable for the specified language.
    """
    if lang is None:
        lang = session.get('lang', 'en') if has_request_context() else 'en'
    if lang not in ['en', 'ha']:
        logger.warning(f"Invalid language {lang}, falling back to 'en'")
        lang = 'en'
    return {
        'trans': lambda key, **kwargs: trans(key, lang=lang, **kwargs)
    }
