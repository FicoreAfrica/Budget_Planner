import os
import sys
import logging
import uuid
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template, request, session, redirect, url_for, flash, send_from_directory, has_request_context, g, current_app, make_response
from flask_wtf.csrf import CSRFError, generate_csrf
from flask_login import LoginManager, current_user, login_required
from flask_pymongo import PyMongo
from dotenv import load_dotenv
from extensions import login_manager, session as flask_session, csrf
from blueprints.auth import auth_bp
from translations import trans
from scheduler_setup import init_scheduler
from models import create_user, get_user_by_email, log_tool_usage
import json
from functools import wraps
from uuid import uuid4
from werkzeug.security import generate_password_hash

# Load environment variables
load_dotenv()

# Set up logging
root_logger = logging.getLogger('ficore_app')
root_logger.setLevel(logging.DEBUG)

class SessionFormatter(logging.Formatter):
    def format(self, record):
        record.session_id = getattr(record, 'session_id', 'no-session-id')
        return super().format(record)

formatter = SessionFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s [session: %(session_id)s]')

class SessionAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        kwargs['extra'] = kwargs.get('extra', {})
        session_id = kwargs['extra'].get('session_id', 'no-session-id')
        if has_request_context():
            session_id = session.get('sid', 'no-session-id')
        kwargs['extra']['session_id'] = session_id
        return msg, kwargs

logger = SessionAdapter(root_logger, {})

# Define admin_required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.signin', next=request.url))
        if current_user.role != 'admin':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def setup_logging(app):
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    root_logger.handlers = []
    root_logger.addHandler(handler)
    
    flask_logger = logging.getLogger('flask')
    werkzeug_logger = logging.getLogger('werkzeug')
    flask_logger.handlers = []
    werkzeug_logger.handlers = []
    flask_logger.addHandler(handler)
    werkzeug_logger.addHandler(handler)
    flask_logger.setLevel(logging.DEBUG)
    werkzeug_logger.setLevel(logging.DEBUG)
    
    logger.info("Logging setup complete with StreamHandler for ficore_app, flask, and werkzeug")

def setup_session(app):
    try:
        app.config['SESSION_TYPE'] = 'memory'
        app.config['SESSION_PERMANENT'] = True
        app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
        app.config['SESSION_USE_SIGNER'] = True
        flask_session.init_app(app)
        logger.info(f"Session configured: type={app.config['SESSION_TYPE']}, lifetime={app.config['PERMANENT_SESSION_LIFETIME']}")
    except Exception as e:
        logger.error(f"Failed to configure session: {str(e)}", exc_info=True)
        raise

def initialize_courses_data(app, mongo):
    try:
        courses_collection = mongo.db.courses
        if courses_collection.count_documents({}) == 0:
            for course in SAMPLE_COURSES:
                courses_collection.insert_one(course)
            logger.info("Initialized courses in MongoDB")
        app.config['COURSES'] = list(courses_collection.find({}, {'_id': 0}))
    except Exception as e:
        logger.error(f"Failed to initialize courses: {str(e)}", exc_info=True)
        app.config['COURSES'] = SAMPLE_COURSES  # Fallback

# Constants
SAMPLE_COURSES = [
    {
        'id': 'budgeting_learning_101',
        'title_key': 'learning_hub_course_budgeting101_title',
        'title_en': 'Budgeting Learning 101',
        'title_ha': 'Tsarin Kudi 101',
        'description_en': 'Learn the basics of budgeting.',
        'description_ha': 'Koyon asalin tsarin kudi.',
        'is_premium': False
    },
    {
        'id': 'financial_quiz',
        'title_key': 'learning_hub_course_financial_quiz_title',
        'title_en': 'Financial Quiz',
        'title_ha': 'Jarabawar Kudi',
        'description_en': 'Test your financial knowledge.',
        'description_ha': 'Gwada ilimin ku na kudi.',
        'is_premium': False
    },
    {
        'id': 'savings_basics',
        'title_key': 'learning_hub_course_savings_basics_title',
        'title_en': 'Savings Basics',
        'title_ha': 'Asalin Tattara Kudi',
        'description_en': 'Understand how to save effectively.',
        'description_ha': 'Fahimci yadda ake tattara kudi yadda ya kamata.',
        'is_premium': False
    }
]

def create_app():
    app = Flask(__name__, template_folder='templates')
    
    # Set Flask secret key
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-please-change-me')
    if not os.getenv('FLASK_SECRET_KEY'):
        logger.warning("FLASK_SECRET_KEY not set. Using fallback for development. Set it in production.")
    
    # Configure logging
    logger.info("Starting app creation")
    setup_logging(app)
    setup_session(app)
    app.config['BASE_URL'] = os.getenv('BASE_URL', 'http://localhost:5000')
    csrf.init_app(app)

    # Configure MongoDB
    mongo_uri = os.getenv('MONGODB_URI')
    if not mongo_uri:
        logger.error("MONGODB_URI environment variable not set. Cannot connect to MongoDB.")
        raise ValueError("MONGODB_URI environment variable is required.")
    app.config['MONGO_URI'] = mongo_uri
    mongo = PyMongo(app)
    logger.info("MongoDB configured with Flask-PyMongo")

    # Create MongoDB indexes
    try:
        mongo.db.users.create_index('email', unique=True)
        mongo.db.users.create_index('referral_code', unique=True)
        mongo.db.courses.create_index('id', unique=True)
        mongo.db.content_metadata.create_index([('course_id', 1), ('lesson_id', 1)])
        mongo.db.financial_health.create_index('session_id')
        mongo.db.financial_health.create_index('user_id')
        mongo.db.budgets.create_index('session_id')
        mongo.db.budgets.create_index('user_id')
        mongo.db.bills.create_index('session_id')
        mongo.db.bills.create_index('user_id')
        mongo.db.net_worth.create_index('session_id')
        mongo.db.net_worth.create_index('user_id')
        mongo.db.emergency_funds.create_index('session_id')
        mongo.db.emergency_funds.create_index('user_id')
        mongo.db.learning_progress.create_index([('user_id', 1), ('course_id', 1)], unique=True)
        mongo.db.learning_progress.create_index([('session_id', 1), ('course_id', 1)], unique=True)
        mongo.db.learning_progress.create_index('session_id')
        mongo.db.learning_progress.create_index('user_id')
        mongo.db.quiz_results.create_index('session_id')
        mongo.db.quiz_results.create_index('user_id')
        mongo.db.feedback.create_index('session_id')
        mongo.db.feedback.create_index('user_id')
        mongo.db.tool_usage.create_index('session_id')
        mongo.db.tool_usage.create_index('user_id')
        mongo.db.tool_usage.create_index('tool_name')
        logger.info("MongoDB indexes created")
    except Exception as e:
        logger.error(f"Failed to create MongoDB indexes: {str(e)}", exc_info=True)
        raise

    # Initialize Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.signin'

    @login_manager.user_loader
    def load_user(user_id):
        try:
            from models import get_user
            user = get_user(mongo, user_id)
            if user:
                return user
            return None
        except Exception as e:
            logger.error(f"Error loading user {user_id}: {str(e)}")
            return None

    # Initialize scheduler
    try:
        init_scheduler(app)
        logger.info("Scheduler initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {str(e)}")

    # Initialize database
    with app.app_context():
        initialize_courses_data(app, mongo)
        logger.info("MongoDB collections initialized")

        # Check and create admin user
        admin_email = os.getenv('ADMIN_EMAIL')
        admin_password = os.getenv('ADMIN_PASSWORD')
        if admin_email and admin_password:
            admin_user = get_user_by_email(mongo, admin_email)
            if not admin_user:
                admin_user = create_user(mongo, {
                    'username': 'admin_' + str(uuid.uuid4())[:8],
                    'email': admin_email,
                    'password_hash': generate_password_hash(admin_password),
                    'is_admin': True,
                    'role': 'admin',
                    'created_at': datetime.utcnow(),
                    'lang': 'en'
                })
                logger.info(f"Admin user created with email: {admin_email}")
            else:
                logger.info(f"Admin user already exists with email: {admin_email}")
        else:
            logger.warning("ADMIN_EMAIL or ADMIN_PASSWORD not set in environment variables.")

    # Register blueprints
    from blueprints.financial_health import financial_health_bp
    from blueprints.budget import budget_bp
    from blueprints.quiz import quiz_bp
    from blueprints.bill import bill_bp
    from blueprints.net_worth import net_worth_bp
    from blueprints.emergency_fund import emergency_fund_bp
    from blueprints.learning_hub import learning_hub_bp
    from blueprints.auth import auth_bp
    from blueprints.admin import admin_bp

    app.register_blueprint(financial_health_bp, template_folder='templates/HEALTHSCORE')
    app.register_blueprint(budget_bp, template_folder='templates/BUDGET')
    app.register_blueprint(quiz_bp, template_folder='templates/QUIZ')
    app.register_blueprint(bill_bp, template_folder='templates/BILL')
    app.register_blueprint(net_worth_bp, template_folder='templates/NETWORTH')
    app.register_blueprint(emergency_fund_bp, template_folder='templates/EMERGENCYFUND')
    app.register_blueprint(learning_hub_bp, template_folder='templates/LEARNINGHUB')
    app.register_blueprint(auth_bp, template_folder='templates/auth')
    app.register_blueprint(admin_bp, template_folder='templates/admin')

    def translate(key, lang='en', logger=logger, **kwargs):
        translation = trans(key, lang=lang, **kwargs)
        if translation == key and app.debug:
            logger.warning(f"Missing translation for key='{key}' in lang='{lang}'")
        return translation

    app.jinja_env.filters['trans'] = lambda key, **kwargs: translate(
        key,
        lang=kwargs.get('lang', session.get('lang', 'en')),
        logger=g.get('logger', logger) if has_request_context() else logger,
        **{k: v for k, v in kwargs.items() if k != 'lang'}
    )

    @app.template_filter('safe_nav')
    def safe_nav(value):
        try:
            return value
        except Exception as e:
            logger.error(f"Navigation rendering error: {str(e)}", exc_info=True)
            return ''

    @app.template_filter('format_number')
    def format_number(value):
        try:
            if isinstance(value, (int, float)):
                return f"{float(value):,.2f}"
            return str(value)
        except (ValueError, TypeError) as e:
            logger.warning(f"Error formatting number {value}: {str(e)}")
            return str(value)

    @app.template_filter('format_datetime')
    def format_datetime(value):
        if isinstance(value, datetime):
            return value.strftime('%B %d, %Y, %I:%M %p')
        return value

    @app.template_filter('format_currency')
    def format_currency(value):
        try:
            value = float(value)
            if value.is_integer():
                return f"₦{int(value):,}"
            return f"₦{value:,.2f}"
        except (TypeError, ValueError):
            return value

    @app.before_request
    def setup_session_and_language():
        try:
            logger.info(f"Starting before_request for path: {request.path}")
            if 'sid' not in session:
                session['sid'] = str(uuid.uuid4())
                logger.info(f"New session ID generated: {session['sid']}")
            if 'lang' not in session:
                session['lang'] = request.accept_languages.best_match(['en', 'ha'], 'en')
                logger.info(f"Set default language to {session['lang']}")
            g.logger = logger
            g.logger.info(f"Request processed for path: {request.path}")
        except Exception as e:
            logger.error(f"Before request error for path {request.path}: {str(e)}", exc_info=True)
            raise

    @app.context_processor
    def inject_translations():
        lang = session.get('lang', 'en')
        def context_trans(key, **kwargs):
            used_lang = kwargs.pop('lang', lang)
            return translate(key, lang=used_lang, logger=g.get('logger', logger), **kwargs)
        return {
            'trans': context_trans,
            'current_year': datetime.now().year,
            'LINKEDIN_URL': os.getenv('LINKEDIN_URL', '#'),
            'TWITTER_URL': os.getenv('TWITTER_URL', '#'),
            'FACEBOOK_URL': os.getenv('FACEBOOK_URL', '#'),
            'FEEDBACK_FORM_URL': os.getenv('FEEDBACK_FORM_URL', '#'),
            'WAITLIST_FORM_URL': os.getenv('WAITLIST_FORM_URL', '#'),
            'CONSULTANCY_FORM_URL': os.getenv('CONSULTANCY_FORM_URL', '#'),
            'current_lang': lang,
            'current_user': current_user if has_request_context() else None,
            'csrf_token': generate_csrf
        }

    def ensure_session_id(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'sid' not in session:
                session['sid'] = str(uuid4())
                logger.info(f"New session ID generated: {session['sid']}")
            return f(*args, **kwargs)
        return decorated_function

    @app.route('/')
    def index():
        lang = session.get('lang', 'en')
        logger.info("Serving index page")
        try:
            courses = current_app.config.get('COURSES', SAMPLE_COURSES)
            logger.info(f"Retrieved {len(courses)} courses")
            return render_template(
                'index.html',
                t=translate,
                courses=courses,
                lang=lang,
                sample_courses=SAMPLE_COURSES
            )
        except Exception as e:
            logger.error(f"Error in index route: {str(e)}", exc_info=True)
            flash(translate('learning_hub_error_message', default='An error occurred', lang=lang), 'danger')
            return render_template('error.html', t=translate, lang=lang, error=str(e)), 500

    @app.route('/set_language/<lang>')
    def set_language(lang):
        valid_langs = ['en', 'ha']
        new_lang = lang if lang in valid_langs else 'en'
        session['lang'] = new_lang
        logger.info(f"Language set to {new_lang}")
        flash(translate('learning_hub_success_language_updated', default='Language updated successfully', lang=new_lang) if new_lang in valid_langs else translate('Invalid language', default='Invalid language', lang=new_lang), 'success' if new_lang in valid_langs else 'danger')
        return redirect(request.referrer or url_for('index'))

    @app.route('/acknowledge_consent', methods=['POST'])
    def acknowledge_consent():
        if request.method != 'POST':
            logger.warning(f"Invalid method {request.method} for consent acknowledgement")
            return '', 400
        session['consent_acknowledged'] = {
            'status': True,
            'timestamp': datetime.utcnow().isoformat(),
            'ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent')
        }
        logger.info(f"Consent acknowledged for session {session['sid']} from IP {request.remote_addr}")
        response = make_response('')
        response.headers['Content-Type'] = None
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.route('/favicon.ico')
    def favicon():
        logger.info("Serving favicon.ico")
        return send_from_directory(os.path.join(app.root_path, 'static', 'data'), 'favicon-32x32.png', mimetype='image/png')

    @app.route('/general_dashboard')
    @ensure_session_id
    def general_dashboard():
        lang = session.get('lang', 'en')
        logger.info("Serving general dashboard")
        data = {}
        try:
            from models import get_financial_health, get_budgets, get_bills, get_net_worth, get_emergency_funds, get_learning_progress, get_quiz_results, to_dict_financial_health, to_dict_budget, to_dict_bill, to_dict_net_worth, to_dict_emergency_fund, to_dict_learning_progress, to_dict_quiz_result
            filter_kwargs = {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session['sid']}

            # Financial Health
            fh_records = get_financial_health(mongo, filter_kwargs)
            fh_records = [to_dict_financial_health(fh) for fh in fh_records]
            data['financial_health'] = fh_records[0] if fh_records else {'score': None, 'status': None}

            # Budget
            budget_records = get_budgets(mongo, filter_kwargs)
            budget_records = [to_dict_budget(b) for b in budget_records]
            data['budget'] = budget_records[0] if budget_records else {'surplus_deficit': None, 'savings_goal': None}

            # Bills
            bills = get_bills(mongo, filter_kwargs)
            bills = [to_dict_bill(b) for b in bills]
            total_amount = sum(bill['amount'] for bill in bills) if bills else 0
            unpaid_amount = sum(bill['amount'] for bill in bills if bill['status'].lower() != 'paid') if bills else 0
            data['bills'] = {'bills': bills, 'total_amount': total_amount, 'unpaid_amount': unpaid_amount}

            # Net Worth
            nw_records = get_net_worth(mongo, filter_kwargs)
            nw_records = [to_dict_net_worth(nw) for nw in nw_records]
            data['net_worth'] = nw_records[0] if nw_records else {'net_worth': None, 'total_assets': None}

            # Emergency Fund
            ef_records = get_emergency_funds(mongo, filter_kwargs)
            ef_records = [to_dict_emergency_fund(ef) for ef in ef_records]
            data['emergency_fund'] = ef_records[0] if ef_records else {'target_amount': None, 'savings_gap': None}

            # Learning Progress
            lp_records = get_learning_progress(mongo, filter_kwargs)
            data['learning_progress'] = {lp['course_id']: to_dict_learning_progress(lp) for lp in lp_records} if lp_records else {}

            # Quiz Result
            quiz_records = get_quiz_results(mongo, filter_kwargs)
            quiz_records = [to_dict_quiz_result(qr) for qr in quiz_records]
            data['quiz'] = quiz_records[0] if quiz_records else {'personality': None, 'score': None}

            logger.info(f"Retrieved data for session {session['sid']}")
            return render_template('general_dashboard.html', data=data, t=translate, lang=lang)
        except Exception as e:
            logger.error(f"Error in general_dashboard: {str(e)}", exc_info=True)
            flash(translate('global_error_message', default='An error occurred', lang=lang), 'danger')
            default_data = {
                'financial_health': {'score': None, 'status': None},
                'budget': {'surplus_deficit': None, 'savings_goal': None},
                'bills': {'bills': [], 'total_amount': 0, 'unpaid_amount': 0},
                'net_worth': {'net_worth': None, 'total_assets': None},
                'emergency_fund': {'target_amount': None, 'savings_gap': None},
                'learning_progress': {},
                'quiz': {'personality': None, 'score': None}
            }
            return render_template('general_dashboard.html', data=default_data, t=translate, lang=lang), 500

    @app.route('/logout')
    def logout():
        lang = session.get('lang', 'en')
        logger.info("Logging out user")
        try:
            session_lang = session.get('lang', 'en')
            session.clear()
            session['lang'] = session_lang
            flash(translate('learning_hub_success_logout', default='Successfully logged out', lang=lang), 'success')
            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Error in logout: {str(e)}", exc_info=True)
            flash(translate('global_error_message', default='An error occurred', lang=lang), 'danger')
            return redirect(url_for('index'))

    @app.route('/about')
    def about():
        lang = session.get('lang', 'en')
        logger.info("Serving about page")
        return render_template('about.html', t=translate, lang=lang)

    @app.route('/health')
    def health():
        logger.info("Health check")
        status = {"status": "healthy"}
        try:
            mongo.db.command('ping')
            return jsonify(status), 200
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}", exc_info=True)
            status["status"] = "unhealthy"
            status["details"] = str(e)
            return jsonify(status), 500

    @app.errorhandler(500)
    def handle_internal_error(error):
        lang = session.get('lang', 'en') if 'lang' in session else 'en'
        logger.error(f"Server error: {str(error)}", exc_info=True)
        return jsonify({'error': 'Internal server error', 'details': str(error)}), 500

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        lang = session.get('lang', 'en') if 'lang' in session else 'en'
        logger.error(f"CSRF error: {str(error)}")
        return jsonify({'error': 'CSRF token invalid'}), 400

    @app.errorhandler(404)
    def page_not_found(e):
        lang = session.get('lang', 'en') if 'lang' in session else 'en'
        logger.error(f"404 error: {str(e)}")
        return jsonify({'error': '404 not found'}), 404

    @app.route('/static/<path:filename>')
    def static_files(filename):
        return send_from_directory('static', filename)

    @app.route('/feedback', methods=['GET', 'POST'])
    @ensure_session_id
    def feedback():
        lang = session.get('lang', 'en')
        logger.info("Handling feedback request")
        tool_options = [
            'financial_health', 'budget', 'bill', 'net_worth',
            'emergency_fund', 'learning_hub', 'quiz'
        ]
        if request.method == 'GET':
            logger.info("Rendering feedback template")
            return render_template('feedback.html', t=translate, lang=lang, tool_options=tool_options)
        try:
            from models import create_feedback
            tool_name = request.form.get('tool_name')
            rating = request.form.get('rating')
            comment = request.form.get('comment', '')
            if not tool_name or tool_name not in tool_options:
                flash(translate('core_feedback_invalid_tool', default='Please select a valid tool', lang=lang), 'error')
                logger.error(f"Invalid feedback tool: {tool_name}")
                return render_template('feedback.html', t=translate, lang=lang, tool_options=tool_options)
            if not rating or not rating.isdigit() or int(rating) < 1 or int(rating) > 5:
                logger.error(f"Invalid feedback rating: {rating}")
                flash(translate('core_feedback_invalid_rating', default='Please provide a rating between 1 and 5', lang=lang), 'error')
                return render_template('feedback.html', t=translate, lang=lang, tool_options=tool_options)
            feedback_entry = create_feedback(mongo, {
                'user_id': current_user.id if current_user.is_authenticated else None,
                'session_id': session['sid'],
                'tool_name': tool_name,
                'rating': int(rating),
                'comment': comment.strip() or None
            })
            logger.info(f"Feedback submitted: tool={tool_name}, rating={rating}, session={session['sid']}")
            flash(translate('core_feedback_success', default='Thank you for your feedback!', lang=lang), 'success')
            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Error processing feedback: {str(e)}")
            flash(translate('core_global_error', default='Error occurred while submitting feedback', lang=lang), 'error')
            return render_template('feedback.html', t=translate, lang=lang, tool_options=tool_options), 500

    logger.info("App creation completed")
    return app, mongo

# Create the Flask app instance for Gunicorn
app, mongo = create_app()

if __name__ == "__main__":
    try:
        app.run(debug=True)
    except Exception as e:
        logger.error(f"Error running app: {str(e)}")
        raise
