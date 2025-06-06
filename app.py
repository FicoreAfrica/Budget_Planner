import osu
import sys
import logging
import uuid
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template, request, session, redirect, url_for, flash, send_from_directory, has_request_context, g, current_app, make_response
from flask_wtf.csrf import CSRFError
from flask_login import current_user, login_required
from dotenv import load_dotenv
from extensions import db, login_manager, session as flask_session, csrf
from blueprints.auth import auth_bp
from translations import trans
from scheduler_setup import init_scheduler
from models import Course, FinancialHealth, Budget, Bill, NetWorth, EmergencyFund, LearningProgress, QuizResult, User, ToolUsage, Feedback
import json
from functools import wraps
from uuid import uuid4
from alembic.config import Config
from alembic import command
from logging.handlers import RotatingFileHandler

# Early print to confirm module loading
print("Loading app.py", file=sys.stderr, flush=True)

# Initialize a basic logger before app creation to catch early errors
early_logger = logging.getLogger('ficore_early')
early_logger.setLevel(logging.DEBUG)
early_stream_handler = logging.StreamHandler(sys.stderr)
early_stream_handler.setLevel(logging.DEBUG)
early_stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
early_logger.addHandler(early_stream_handler)
early_logger.debug("Early logger initialized")

try:
    # Load environment variables
    load_dotenv()
    early_logger.debug("Environment variables loaded")
except Exception as e:
    print(f"Error loading environment variables: {str(e)}", file=sys.stderr, flush=True)
    early_logger.error(f"Error loading environment variables: {str(e)}", exc_info=True)
    raise

# Set up main logger
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

def setup_logging(app):
    print("Setting up logging", file=sys.stderr, flush=True)
    # StreamHandler for stderr with immediate flushing
    class FlushingStreamHandler(logging.StreamHandler):
        def emit(self, record):
            super().emit(record)
            self.flush()
    
    stream_handler = FlushingStreamHandler(sys.stderr)
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)
    logger.debug(f"Logger level: {root_logger.getEffectiveLevel()}")
    
    # FileHandler with rotation
    log_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(log_dir, exist_ok=True)
    try:
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, 'storage.log'),
            maxBytes=10*1024*1024,
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        logger.info("Logging setup complete with rotating file handler")
        if os.path.exists(os.path.join(log_dir, 'storage.log')):
            logger.debug(f"Log file exists: {os.path.join(log_dir, 'storage.log')}")
        else:
            logger.warning(f"Log file does not exist: {os.path.join(log_dir, 'storage.log')}")
    except (PermissionError, OSError) as e:
        logger.warning(f"Failed to set up file logging: {str(e)}. Relying on stream handler.")
    
    # Configure Gunicorn logging
    gunicorn_logger = logging.getLogger('gunicorn')
    gunicorn_logger.setLevel(logging.DEBUG)
    gunicorn_logger.handlers = [stream_handler]
    logger.debug(f"Gunicorn logger level: {gunicorn_logger.getEffectiveLevel()}")
    logger.info("Gunicorn logger configured to use stream handler")

def setup_session(app):
    session_dir = os.path.join(os.path.dirname(__file__), 'data', 'sessions')
    try:
        os.makedirs(session_dir, exist_ok=True)
        logger.info(f"Session directory ensured at {session_dir}")
    except OSError as e:
        logger.error(f"Failed to create session directory {session_dir}: {str(e)}. Using in-memory sessions.")
        app.config['SESSION_TYPE'] = 'null'
        return
    app.config['SESSION_FILE_DIR'] = session_dir
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
    app.config['SESSION_USE_SIGNER'] = True
    logger.info(f"Session configured: type={app.config['SESSION_TYPE']}, dir={session_dir}, lifetime={app.config['PERMANENT_SESSION_LIFETIME']}")

def initialize_courses_data(app):
    with app.app_context():
        if Course.query.count() == 0:
            for course in SAMPLE_COURSES:
                db_course = Course(**course)
                db.session.add(db_course)
            db.session.commit()
            logger.info(f"Initialized {len(SAMPLE_COURSES)} courses in database")
        app.config['COURSES'] = [course.to_dict() for course in Course.query.all()]

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
        'description_ha': 'Gwada ilimin ku ya na kudi.',
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

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash(trans('admin_access_denied', default='Access denied: Admin privileges required'), 'danger')
            logger.warning(f"Unauthorized admin access attempt by user {current_user.username}")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def log_tool_usage(app, tool_name):
    valid_tools = [
        'register', 'login', 'logout',
        'financial_health', 'budget', 'bill', 'net_worth',
        'emergency_fund', 'learning_hub', 'quiz'
    ]
    if tool_name not in valid_tools:
        logger.error(f"Invalid tool_name provided: {tool_name}")
        return
    try:
        usage_entry = ToolUsage(
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session.get('sid', str(uuid.uuid4())),
            tool_name=tool_name
        )
        db.session.add(usage_entry)
        db.session.commit()
        logger.info(f"Successfully logged tool usage: tool={tool_name}, session={session['sid']}, user_id={current_user.id if current_user.is_authenticated else 'anonymous'}")
    except Exception as e:
        logger.error(f"Error logging tool usage for {tool_name}: {str(e)}")
        db.session.rollback()

def run_migrations():
    """Run Alembic migrations to ensure the database schema is up-to-date."""
    try:
        alembic_cfg = Config(os.path.join(os.path.dirname(__file__), 'alembic.ini'))
        alembic_path = os.path.join(os.path.dirname(__file__), 'migrations')
        if not os.path.exists(alembic_path):
            logger.critical(f"Migration directory {alembic_path} does not exist. Please initialize migrations.")
            print(f"Migration directory {alembic_path} does not exist", file=sys.stderr, flush=True)
            raise FileNotFoundError(f"Migration directory {alembic_path} not found")
        scripts = os.listdir(alembic_path)
        logger.info(f"Found migration scripts: {scripts}")
        alembic_cfg.set_main_option('script_location', alembic_path)
        logger.info("Starting Alembic migrations...")
        command.upgrade(alembic_cfg, 'head')
        logger.info("Successfully applied database migrations")
    except Exception as e:
        logger.critical(f"Failed to apply database migrations: {str(e)}", exc_info=True)
        print(f"Failed to apply database migrations: {str(e)}", file=sys.stderr, flush=True)
        raise

def initialize_database(app):
    """Initialize the database by running migrations and setting up the admin user."""
    with app.app_context():
        try:
            run_migrations()
        except Exception as e:
            logger.critical(f"Migration failed: {str(e)}", exc_info=True)
            print(f"Migration failed: {str(e)}", file=sys.stderr, flush=True)
            logger.warning("Skipping admin user initialization due to migration failure")
            return
        admin_email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'defaultadminpassword')
        if admin_password == 'defaultadminpassword':
            logger.warning("Using default admin password. Set ADMIN_PASSWORD environment variable in production.")
        try:
            admin_user = User.query.filter_by(email=admin_email).first()
            if not admin_user:
                admin_user = User(
                    username='admin',
                    email=admin_email,
                    created_at=datetime.utcnow(),
                    is_admin=True
                )
                admin_user.set_password(admin_password)
                db.session.add(admin_user)
                logger.info(f"Created admin user with email {admin_email}")
            elif not admin_user.is_admin:
                admin_user.is_admin = True
                logger.info(f"Assigned admin role to existing user {admin_email}")
            db.session.commit()
        except Exception as e:
            logger.critical(f"Failed to initialize admin user: {str(e)}", exc_info=True)
            print(f"Failed to initialize admin user: {str(e)}", file=sys.stderr, flush=True)
            db.session.rollback()

def create_app():
    print("Starting create_app", file=sys.stderr, flush=True)
    app = Flask(__name__, template_folder='templates')
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-please-change-me')
    if not os.environ.get('FLASK_SECRET_KEY'):
        logger.warning("FLASK_SECRET_KEY not set. Using fallback for development. Set it in production.")
        print("FLASK_SECRET_KEY not set", file=sys.stderr, flush=True)
    
    logger.info("Starting app creation")
    setup_logging(app)
    setup_session(app)
    app.config['BASE_URL'] = os.environ.get('BASE_URL', 'http://localhost:5000')
    flask_session.init_app(app)
    csrf.init_app(app)

    # Configure SQLite database
    db_dir = os.path.join(os.path.dirname(__file__), 'data')
    try:
        os.makedirs(db_dir, exist_ok=True)
        logger.info(f"Database directory ensured at {db_dir}")
    except OSError as e:
        logger.critical(f"Failed to create database directory {db_dir}: {str(e)}")
        print(f"Failed to create database directory {db_dir}: {str(e)}", file=sys.stderr, flush=True)
        raise
    db_path = os.path.join(db_dir, 'ficore.db')
    db_url = os.environ.get('DATABASE_URL', f'sqlite:///{db_path}')
    if not os.environ.get('DATABASE_URL'):
        logger.warning("DATABASE_URL not set. Using SQLite default.")
        print("DATABASE_URL not set", file=sys.stderr, flush=True)
    logger.info(f"Using database URL: {db_url}")
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    # Initialize Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.signin'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Initialize scheduler
    try:
        init_scheduler(app)
        logger.info("Scheduler initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {str(e)}")
        print(f"Failed to initialize scheduler: {str(e)}", file=sys.stderr, flush=True)

    # Initialize database and admin user
    try:
        initialize_database(app)
        initialize_courses_data(app)
        logger.info("Database and courses initialized successfully")
    except Exception as e:
        logger.critical(f"Failed to initialize database: {str(e)}", exc_info=True)
        print(f"Failed to initialize database: {str(e)}", file=sys.stderr, flush=True)

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

    app.register_blueprint(financial_health_bp, template_folder='templates/financial_health')
    app.register_blueprint(budget_bp, template_folder='templates/budget')
    app.register_blueprint(quiz_bp, template_folder='templates/quiz')
    app.register_blueprint(bill_bp, template_folder='templates/bill')
    app.register_blueprint(net_worth_bp, template_folder='templates/net_worth')
    app.register_blueprint(emergency_fund_bp, template_folder='templates/emergency_fund')
    app.register_blueprint(learning_hub_bp, template_folder='templates/learning_hub')
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
            if 'sid' not in session:
                session['sid'] = str(uuid.uuid4())
                session.permanent = True
                session.modified = True
                logger.info(f"New session ID generated: {session['sid']}")
            if 'lang' not in session:
                session['lang'] = request.accept_languages.best_match(['en', 'ha'], 'en')
                logger.info(f"Set default language to {session['lang']}")
            g.logger = logger
            logger.info(
                f"Request: method={request.method}, path={request.path}, "
                f"remote_addr={request.remote_addr}, user_agent={request.headers.get('User-Agent')}, "
                f"session_id={session['sid']}, user_id={current_user.id if current_user.is_authenticated else 'anonymous'}"
            )
        except Exception as e:
            logger.error(f"Before request error: {str(e)}", exc_info=True)
            print(f"Before request error: {str(e)}", file=sys.stderr, flush=True)

    @app.after_request
    def log_response(response):
        logger.info(
            f"Response: status={response.status_code}, path={request.path}, "
            f"session_id={session.get('sid', 'no-session-id')}"
        )
        return response

    @app.context_processor
    def inject_translations():
        lang = session.get('lang', 'en')
        def context_trans(key, **kwargs):
            used_lang = kwargs.pop('lang', lang)
            return translate(key, lang=used_lang, logger=g.get('logger', logger), **kwargs)
        return {
            'trans': context_trans,
            'current_year': datetime.now().year,
            'LINKEDIN_URL': os.environ.get('LINKEDIN_URL', '#'),
            'TWITTER_URL': os.environ.get('TWITTER_URL', '#'),
            'FACEBOOK_URL': os.environ.get('FACEBOOK_URL', '#'),
            'FEEDBACK_FORM_URL': os.environ.get('FEEDBACK_FORM_URL', url_for('feedback')),
            'WAITLIST_FORM_URL': os.environ.get('WAITLIST_FORM_URL', '#'),
            'CONSULTANCY_FORM_URL': os.environ.get('CONSULTANCY_FORM_URL', '#'),
            'current_lang': lang,
            'current_user': current_user if has_request_context() else None,
            'csrf_token': csrf._get_token if hasattr(csrf, '_get_token') else lambda: ''
        }

    def ensure_session_id(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'sid' not in session:
                session['sid'] = str(uuid4())
                session.permanent = True
                session.modified = True
                logger.info(f"New session ID generated: {session['sid']}")
            return f(*args, **kwargs)
        return decorated_function

    @app.route('/')
    def index():
        print("Entering index route", file=sys.stderr, flush=True)
        lang = session.get('lang', 'en')
        logger.info("Serving index page")
        try:
            courses = current_app.config['COURSES'] or SAMPLE_COURSES
            logger.info(f"Retrieved {len(courses)} courses")
            processed_courses = courses
        except Exception as e:
            logger.error(f"Error retrieving courses: {str(e)}", exc_info=True)
            print(f"Error in index route: {str(e)}", file=sys.stderr, flush=True)
            processed_courses = SAMPLE_COURSES
            flash(translate('learning_hub_error_message', default='An error occurred', lang=lang), 'danger')
        print("Rendering index template", file=sys.stderr, flush=True)
        return render_template(
            'index.html',
            t=translate,
            courses=processed_courses,
            lang=lang,
            sample_courses=SAMPLE_COURSES
        )

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
        response = make_response('', 204)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.route('/favicon.ico')
    def favicon():
        logger.info("Serving favicon.ico")
        return send_from_directory(os.path.join(app.root_path, 'static', 'img'), 'favicon-32x32.png', mimetype='image/png')

    @app.route('/general_dashboard')
    @ensure_session_id
    def general_dashboard():
        print("Entering general_dashboard route", file=sys.stderr, flush=True)
        lang = session.get('lang', 'en')
        logger.info("Serving general dashboard")
        data = {}
        try:
            filter_kwargs = {'user_id': current_user.id} if current_user.is_authenticated else {'session_id': session['sid']}

            # Financial Health
            fh_records = FinancialHealth.query.filter_by(**filter_kwargs).order_by(FinancialHealth.created_at.desc()).all()
            if not fh_records:
                logger.warning(f"No FinancialHealth records found for filter: {filter_kwargs}")
            data['financial_health'] = {
                'score': fh_records[0].score,
                'status': fh_records[0].status
            } if fh_records else {'score': None, 'status': None}

            # Budget
            budget_records = Budget.query.filter_by(**filter_kwargs).order_by(Budget.created_at.desc()).all()
            if not budget_records:
                logger.warning(f"No Budget records found for filter: {filter_kwargs}")
            data['budget'] = {
                'surplus_deficit': budget_records[0].surplus_deficit,
                'savings_goal': budget_records[0].savings_goal
            } if budget_records else {'surplus_deficit': None, 'savings_goal': None}

            # Bills
            bills = Bill.query.filter_by(**filter_kwargs).all()
            if not bills:
                logger.warning(f"No Bill records found for filter: {filter_kwargs}")
            total_amount = sum(bill.amount for bill in bills)
            unpaid_amount = sum(bill.amount for bill in bills if bill.status.lower() != 'paid')
            data['bills'] = {
                'bills': [bill.to_dict() for bill in bills],
                'total_amount': total_amount,
                'unpaid_amount': unpaid_amount
            }

            # Net Worth
            nw_records = NetWorth.query.filter_by(**filter_kwargs).order_by(NetWorth.created_at.desc()).all()
            if not nw_records:
                logger.warning(f"No NetWorth records found for filter: {filter_kwargs}")
            data['net_worth'] = {
                'net_worth': nw_records[0].net_worth,
                'total_assets': nw_records[0].total_assets
            } if nw_records else {'net_worth': None, 'total_assets': None}

            # Emergency Fund
            ef_records = EmergencyFund.query.filter_by(**filter_kwargs).order_by(EmergencyFund.created_at.desc()).all()
            if not ef_records:
                logger.warning(f"No EmergencyFund records found for filter: {filter_kwargs}")
            data['emergency_fund'] = {
                'target_amount': ef_records[0].target_amount,
                'savings_gap': ef_records[0].savings_gap
            } if ef_records else {'target_amount': None, 'savings_gap': None}

            # Learning Progress
            lp_records = LearningProgress.query.filter_by(**filter_kwargs).all()
            if not lp_records:
                logger.warning(f"No LearningProgress records found for filter: {filter_kwargs}")
            data['learning_progress'] = {lp.course_id: lp.to_dict() for lp in lp_records}

            # Quiz Result
            quiz_records = QuizResult.query.filter_by(**filter_kwargs).order_by(QuizResult.created_at.desc()).all()
            if not quiz_records:
                logger.warning(f"No QuizResult records found for filter: {filter_kwargs}")
            data['quiz'] = {
                'personality': quiz_records[0].personality,
                'score': quiz_records[0].score
            } if quiz_records else {'personality': None, 'score': None}

            logger.info(f"Retrieved data for session {session['sid']}")
            print("Rendering general_dashboard template", file=sys.stderr, flush=True)
            return render_template('general_dashboard.html', data=data, t=translate, lang=lang)
        except Exception as e:
            logger.error(f"Error in general_dashboard: {str(e)}", exc_info=True)
            print(f"Error in general_dashboard: {str(e)}", file=sys.stderr, flush=True)
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

    @app.route('/feedback', methods=['GET', 'POST'])
    @ensure_session_id
    def feedback():
        lang = session.get('lang', 'en')
        logger.info("Handling feedback route")
        tool_options = [
            'financial_health', 'budget', 'bill', 'net_worth',
            'emergency_fund', 'learning_hub', 'quiz'
        ]
        if request.method == 'GET':
            return render_template('feedback.html', t=translate, lang=lang, tool_options=tool_options)
        try:
            tool_name = request.form.get('tool_name')
            rating = request.form.get('rating')
            comment = request.form.get('comment', '')
            if not tool_name or tool_name not in tool_options:
                flash(translate('feedback_invalid_tool', default='Please select a valid tool', lang=lang), 'error')
                logger.error(f"Invalid feedback tool: {tool_name}")
                return render_template('feedback.html', t=translate, lang=lang, tool_options=tool_options)
            if not rating or not rating.is_digit() or int(rating) < 1 or int(rating) > 5:
                logger.error(f"Invalid feedback rating: {rating}")
                flash(translate('feedback_invalid_rating', default='Please provide a rating between 1 and 5', lang=lang), 'error')
                return render_template('feedback.html', t=translate, lang=lang, tool_options=tool_options)
            feedback_entry = Feedback(
                user_id=current_user.id if current_user.is_authenticated else None,
                session_id=session['sid'],
                tool_name=tool_name,
                rating=int(rating),
                comment=comment.strip() or None
            )
            db.session.add(feedback_entry)
            db.session.commit()
            logger.info(f"Feedback submitted: tool={tool_name}, rating={rating}, session={session['sid']}")
            flash(translate('feedback_success', default='Thank you for your feedback!', lang=lang), 'success')
            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Error processing feedback: {str(e)}", exc_info=True)
            print(f"Error processing feedback: {str(e)}", file=sys.stderr, flush=True)
            flash(translate('global_error', default='Error occurred while submitting feedback', lang=lang), 'error')
            return render_template('feedback.html', t=translate, lang=lang, tool_options=tool_options), 500

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
            print(f"Error in logout: {str(e)}", file=sys.stderr, flush=True)
            flash(translate('global_error', default='An error occurred', lang=lang), 'error')
            return redirect(url_for('index'))

    @app.route('/about')
    def about():
        lang = session.get('lang', 'en')
        logger.info("Serving about page")
        return render_template('about.html', t=translate, lang=lang)

    @app.route('/health')
    def health():
        logger.info("Health check requested")
        status = {"status": "healthy"}
        try:
            with app.app_context():
                db.session.execute('SELECT 1')
                logger.debug("Database connection successful")
            if not os.path.exists(os.path.join(os.path.dirname(__file__), 'data', 'storage.log')):
                status["status"] = "warning"
                status["warning"] = "Log file data/storage.log not found"
                logger.warning("Log file data/storage.log not found")
            logger.info("Health check completed successfully")
            return jsonify(status), 200
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}", exc_info=True)
            print(f"Health check failed: {str(e)}", file=sys.stderr, flush=True)
            status["status"] = "unhealthy"
            status["error"] = str(e)
            return jsonify(status), 500

    @app.route('/debug_log')
    def debug_log():
        """Debug route to test logging."""
        logger.debug("Debug log test")
        logger.info("Info log test")
        logger.warning("Warning log test")
        logger.error("Error log test")
        print("Debug log route executed", file=sys.stderr, flush=True)
        return jsonify({"message": "Logged debug messages"})

    @app.errorhandler(Exception)
    def handle_exception(e):
        lang = session.get('lang', 'en')
        logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
        print(f"Caught unhandled exception: {str(e)}", file=sys.stderr, flush=True)
        return jsonify({'error': 'Internal server error'}), 500

    @app.errorhandler(CSRFError)
    def handle_csrf(e):
        lang = session.get('lang', 'en')
        logger.error(f"CSRF error: {str(e)}", exc_info=True)
        print(f"CSRF error: {str(e)}", file=sys.stderr, flush=True)
        return jsonify({'error': 'CSRF token invalid'}), 400

    @app.errorhandler(404)
    def page_not_found(e):
        lang = session.get('lang', 'en')
        logger.error(f"404 error: {request.path}", exc_info=True)
        print(f"404 error: {request.path}", file=sys.stderr, flush=True)
        return jsonify({'error': '404 Not Found'}), 404

    @app.route('/static/<path:filename>')
    def static_files(filename):
        response = send_from_directory('static', filename)
        return response

    logger.info("App creation completed successfully")
    print("App creation completed", file=sys.stderr, flush=True)
    return app

try:
    print("Attempting to create app", file=sys.stderr, flush=True)
    app = create_app()
except Exception as e:
    print(f"Error creating app: {str(e)}", file=sys.stderr, flush=True)
    early_logger.error(f"Error creating app: {str(e)}", exc_info=True)
    raise