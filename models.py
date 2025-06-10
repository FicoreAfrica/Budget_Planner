import uuid
from datetime import datetime, date
import json
from flask import current_app, session
from flask_login import UserMixin
from collections import namedtuple

# User helper functions
def create_user(mongo, user_data):
    """Create a new user in the users collection."""
    user = {
        'id': user_data.get('id', int(uuid.uuid4().int & (1<<31)-1)),  # 31-bit positive integer ID
        'username': user_data['username'],
        'email': user_data['email'],
        'password_hash': user_data['password_hash'],
        'created_at': user_data.get('created_at', datetime.utcnow()),
        'lang': user_data.get('lang', 'en'),
        'referral_code': user_data.get('referral_code', str(uuid.uuid4())),
        'is_admin': user_data.get('is_admin', False),
        'role': user_data.get('role', 'user'),
        'referred_by_id': user_data.get('referred_by_id'),
    }
    mongo.db.users.insert_one(user)
    return user

def get_user(mongo, user_id):
    """Retrieve a user by ID."""
    user = mongo.db.users.find_one({'id': int(user_id)}, {'_id': 0})
    if user:
        User = namedtuple('User', user.keys())
        return User(**user)
    return None

def get_user_by_email(mongo, email):
    """Retrieve a user by email."""
    return mongo.db.users.find_one({'email': email}, {'_id': 0})

def update_user(mongo, user_id, updates):
    """Update user fields."""
    mongo.db.users.update_one({'id': int(user_id)}, {'$set': updates})

# Course helper functions
def create_course(mongo, course_data):
    """Create a new course in the courses collection."""
    course = {
        'id': course_data['id'],
        'title_key': course_data['title_key'],
        'title_en': course_data['title_en'],
        'title_ha': course_data['title_ha'],
        'description_en': course_data['description_en'],
        'description_ha': course_data['description_ha'],
        'is_premium': course_data.get('is_premium', False)
    }
    mongo.db.courses.insert_one(course)
    return course

def get_course(mongo, course_id):
    """Retrieve a course by ID."""
    return mongo.db.courses.find_one({'id': course_id}, {'_id': 0})

def get_all_courses(mongo):
    """Retrieve all courses."""
    return list(mongo.db.courses.find({}, {'_id': 0}))

def to_dict_course(course):
    """Convert course document to dict."""
    return {
        'id': course['id'],
        'title_key': course['title_key'],
        'title_en': course['title_en'],
        'title_ha': course['title_ha'],
        'description_en': course['description_en'],
        'description_ha': course['description_ha'],
        'is_premium': course['is_premium']
    }

# ContentMetadata helper functions
def create_content_metadata(mongo, metadata):
    """Create content metadata."""
    metadata_doc = {
        'id': int(uuid.uuid4().int & (1<<31)-1),
        'course_id': metadata['course_id'],
        'lesson_id': metadata['lesson_id'],
        'content_type': metadata['content_type'],
        'content_path': metadata['content_path'],
        'uploaded_by': metadata.get('uploaded_by'),
        'upload_date': metadata.get('upload_date', datetime.utcnow())
    }
    mongo.db.content_metadata.insert_one(metadata_doc)
    return metadata_doc

def get_content_metadata(mongo, metadata_id):
    """Retrieve content metadata by ID."""
    return mongo.db.content_metadata.find_one({'id': metadata_id}, {'_id': 0})

# FinancialHealth helper functions
def create_financial_health(mongo, fh_data):
    """Create a financial health record."""
    fh = {
        'id': str(uuid.uuid4()),
        'user_id': fh_data.get('user_id'),
        'session_id': fh_data['session_id'],
        'created_at': fh_data.get('created_at', datetime.utcnow()),
        'first_name': fh_data.get('first_name'),
        'email': fh_data.get('email'),
        'user_type': fh_data.get('user_type'),
        'send_email': fh_data.get('send_email', False),
        'income': fh_data.get('income'),
        'expenses': fh_data.get('expenses'),
        'debt': fh_data.get('debt'),
        'interest_rate': fh_data.get('interest_rate'),
        'debt_to_income': fh_data.get('debt_to_income'),
        'savings_rate': fh_data.get('savings_rate'),
        'interest_burden': fh_data.get('interest_burden'),
        'score': fh_data.get('score'),
        'status': fh_data.get('status'),
        'status_key': fh_data.get('status_key'),
        'badges': json.dumps(fh_data.get('badges', [])),
        'step': fh_data.get('step')
    }
    mongo.db.financial_health.insert_one(fh)
    return fh

def get_financial_health(mongo, filters):
    """Retrieve financial health records by filters."""
    return list(mongo.db.financial_health.find(filters, {'_id': 0}))

def to_dict_financial_health(fh):
    """Convert financial health document to dict."""
    try:
        badges = json.loads(fh['badges']) if fh.get('badges') else []
    except json.JSONDecodeError:
        current_app.logger.error(f"Invalid JSON in badges for FinancialHealth ID {fh['id']}")
        badges = []
    return {
        'id': fh['id'],
        'user_id': fh['user_id'],
        'session_id': fh['session_id'],
        'created_at': fh['created_at'].isoformat() + "Z" if isinstance(fh['created_at'], datetime) else fh['created_at'],
        'first_name': fh['first_name'],
        'email': fh['email'],
        'user_type': fh['user_type'],
        'send_email': fh['send_email'],
        'income': fh['income'],
        'expenses': fh['expenses'],
        'debt': fh['debt'],
        'interest_rate': fh['interest_rate'],
        'debt_to_income': fh['debt_to_income'],
        'savings_rate': fh['savings_rate'],
        'interest_burden': fh['interest_burden'],
        'score': fh['score'],
        'status': fh['status'],
        'status_key': fh['status_key'],
        'badges': badges,
        'step': fh['step']
    }

# Budget helper functions
def create_budget(mongo, budget_data):
    """Create a budget record."""
    budget = {
        'id': str(uuid.uuid4()),
        'user_id': budget_data.get('user_id'),
        'session_id': budget_data['session_id'],
        'created_at': budget_data.get('created_at', datetime.utcnow()),
        'user_email': budget_data.get('user_email'),
        'income': budget_data.get('income', 0.0),
        'fixed_expenses': budget_data.get('fixed_expenses', 0.0),
        'variable_expenses': budget_data.get('variable_expenses', 0.0),
        'savings_goal': budget_data.get('savings_goal', 0.0),
        'surplus_deficit': budget_data.get('surplus_deficit'),
        'housing': budget_data.get('housing', 0.0),
        'food': budget_data.get('food', 0.0),
        'transport': budget_data.get('transport', 0.0),
        'dependents': budget_data.get('dependents', 0.0),
        'miscellaneous': budget_data.get('miscellaneous', 0.0),
        'others': budget_data.get('others', 0.0)
    }
    mongo.db.budgets.insert_one(budget)
    return budget

def get_budgets(mongo, filters):
    """Retrieve budget records by filters."""
    return list(mongo.db.budgets.find(filters, {'_id': 0}))

def to_dict_budget(budget):
    """Convert budget document to dict."""
    return {
        'id': budget['id'],
        'user_id': budget['user_id'],
        'session_id': budget['session_id'],
        'created_at': budget['created_at'].isoformat() + "Z" if isinstance(budget['created_at'], datetime) else budget['created_at'],
        'user_email': budget['user_email'],
        'income': budget['income'],
        'fixed_expenses': budget['fixed_expenses'],
        'variable_expenses': budget['variable_expenses'],
        'savings_goal': budget['savings_goal'],
        'surplus_deficit': budget['surplus_deficit'],
        'housing': budget['housing'],
        'food': budget['food'],
        'transport': budget['transport'],
        'dependents': budget['dependents'],
        'miscellaneous': budget['miscellaneous'],
        'others': budget['others']
    }

# Bill helper functions
def create_bill(mongo, bill_data):
    """Create a bill record."""
    bill = {
        'id': str(uuid.uuid4()),
        'user_id': bill_data.get('user_id'),
        'session_id': bill_data['session_id'],
        'created_at': bill_data.get('created_at', datetime.utcnow()),
        'user_email': bill_data.get('user_email'),
        'first_name': bill_data.get('first_name'),
        'bill_name': bill_data['bill_name'],
        'amount': bill_data['amount'],
        'due_date': bill_data['due_date'].strftime('%Y-%m-%d') if isinstance(bill_data['due_date'], date) else bill_data['due_date'],
        'frequency': bill_data['frequency'],
        'category': bill_data['category'],
        'status': bill_data['status'],
        'send_email': bill_data.get('send_email', False),
        'reminder_days': bill_data.get('reminder_days')
    }
    mongo.db.bills.insert_one(bill)
    return bill

def get_bills(mongo, filters):
    """Retrieve bill records by filters."""
    return list(mongo.db.bills.find(filters, {'_id': 0}))

def to_dict_bill(bill):
    """Convert bill document to dict."""
    return {
        'id': bill['id'],
        'user_id': bill['user_id'],
        'session_id': bill['session_id'],
        'created_at': bill['created_at'].isoformat() + "Z" if isinstance(bill['created_at'], datetime) else bill['created_at'],
        'user_email': bill['user_email'],
        'first_name': bill['first_name'],
        'bill_name': bill['bill_name'],
        'amount': bill['amount'],
        'due_date': bill['due_date'],
        'frequency': bill['frequency'],
        'category': bill['category'],
        'status': bill['status'],
        'send_email': bill['send_email'],
        'reminder_days': bill['reminder_days']
    }

# NetWorth helper functions
def create_net_worth(mongo, nw_data):
    """Create a net worth record."""
    nw = {
        'id': str(uuid.uuid4()),
        'user_id': nw_data.get('user_id'),
        'session_id': nw_data['session_id'],
        'created_at': nw_data.get('created_at', datetime.utcnow()),
        'first_name': nw_data.get('first_name'),
        'email': nw_data.get('email'),
        'send_email': nw_data.get('send_email', False),
        'cash_savings': nw_data.get('cash_savings'),
        'investments': nw_data.get('investments'),
        'property': nw_data.get('property'),
        'loans': nw_data.get('loans'),
        'total_assets': nw_data.get('total_assets'),
        'total_liabilities': nw_data.get('total_liabilities'),
        'net_worth': nw_data.get('net_worth'),
        'badges': json.dumps(nw_data.get('badges', []))
    }
    mongo.db.net_worth.insert_one(nw)
    return nw

def get_net_worth(mongo, filters):
    """Retrieve net worth records by filters."""
    return list(mongo.db.net_worth.find(filters, {'_id': 0}))

def to_dict_net_worth(nw):
    """Convert net worth document to dict."""
    try:
        badges = json.loads(nw['badges']) if nw.get('badges') else []
    except json.JSONDecodeError:
        current_app.logger.error(f"Invalid JSON in badges for NetWorth ID {nw['id']}")
        badges = []
    return {
        'id': nw['id'],
        'user_id': nw['user_id'],
        'session_id': nw['session_id'],
        'created_at': nw['created_at'].isoformat() + "Z" if isinstance(nw['created_at'], datetime) else nw['created_at'],
        'first_name': nw['first_name'],
        'email': nw['email'],
        'send_email': nw['send_email'],
        'cash_savings': nw['cash_savings'],
        'investments': nw['investments'],
        'property': nw['property'],
        'loans': nw['loans'],
        'total_assets': nw['total_assets'],
        'total_liabilities': nw['total_liabilities'],
        'net_worth': nw['net_worth'],
        'badges': badges
    }

# EmergencyFund helper functions
def create_emergency_fund(mongo, ef_data):
    """Create an emergency fund record."""
    ef = {
        'id': str(uuid.uuid4()),
        'user_id': ef_data.get('user_id'),
        'session_id': ef_data['session_id'],
        'created_at': ef_data.get('created_at', datetime.utcnow()),
        'first_name': ef_data.get('first_name'),
        'email': ef_data.get('email'),
        'email_opt_in': ef_data.get('email_opt_in', False),
        'lang': ef_data.get('lang'),
        'monthly_expenses': ef_data.get('monthly_expenses'),
        'monthly_income': ef_data.get('monthly_income'),
        'current_savings': ef_data.get('current_savings'),
        'risk_tolerance_level': ef_data.get('risk_tolerance_level'),
        'dependents': ef_data.get('dependents'),
        'timeline': ef_data.get('timeline'),
        'recommended_months': ef_data.get('recommended_months'),
        'target_amount': ef_data.get('target_amount'),
        'savings_gap': ef_data.get('savings_gap'),
        'monthly_savings': ef_data.get('monthly_savings'),
        'percent_of_income': ef_data.get('percent_of_income'),
        'badges': json.dumps(ef_data.get('badges', []))
    }
    mongo.db.emergency_funds.insert_one(ef)
    return ef

def get_emergency_funds(mongo, filters):
    """Retrieve emergency fund records by filters."""
    return list(mongo.db.emergency_funds.find(filters, {'_id': 0}))

def to_dict_emergency_fund(ef):
    """Convert emergency fund document to dict."""
    try:
        badges = json.loads(ef['badges']) if ef.get('badges') else []
    except json.JSONDecodeError:
        current_app.logger.error(f"Invalid JSON in badges for EmergencyFund ID {ef['id']}")
        badges = []
    return {
        'id': ef['id'],
        'user_id': ef['user_id'],
        'session_id': ef['session_id'],
        'created_at': ef['created_at'].isoformat() + "Z" if isinstance(ef['created_at'], datetime) else ef['created_at'],
        'first_name': ef['first_name'],
        'email': ef['email'],
        'email_opt_in': ef['email_opt_in'],
        'lang': ef['lang'],
        'monthly_expenses': ef['monthly_expenses'],
        'monthly_income': ef['monthly_income'],
        'current_savings': ef['current_savings'],
        'risk_tolerance_level': ef['risk_tolerance_level'],
        'dependents': ef['dependents'],
        'timeline': ef['timeline'],
        'recommended_months': ef['recommended_months'],
        'target_amount': ef['target_amount'],
        'savings_gap': ef['savings_gap'],
        'monthly_savings': ef['monthly_savings'],
        'percent_of_income': ef['percent_of_income'],
        'badges': badges
    }

# LearningProgress helper functions
def create_learning_progress(mongo, lp_data):
    """Create a learning progress record."""
    lp = {
        'id': int(uuid.uuid4().int & (1<<31)-1),
        'user_id': lp_data.get('user_id'),
        'session_id': lp_data['session_id'],
        'course_id': lp_data['course_id'],
        'lessons_completed': json.dumps(lp_data.get('lessons_completed', [])),
        'quiz_scores': json.dumps(lp_data.get('quiz_scores', {})),
        'current_lesson': lp_data.get('current_lesson')
    }
    mongo.db.learning_progress.insert_one(lp)
    return lp

def get_learning_progress(mongo, filters):
    """Retrieve learning progress records by filters."""
    return list(mongo.db.learning_progress.find(filters, {'_id': 0}))

def to_dict_learning_progress(lp):
    """Convert learning progress document to dict."""
    try:
        lessons_completed = json.loads(lp['lessons_completed']) if lp.get('lessons_completed') else []
        quiz_scores = json.loads(lp['quiz_scores']) if lp.get('quiz_scores') else {}
    except json.JSONDecodeError:
        current_app.logger.error(f"Invalid JSON in LearningProgress ID {lp['id']}")
        lessons_completed = []
        quiz_scores = {}
    return {
        'id': lp['id'],
        'user_id': lp['user_id'],
        'session_id': lp['session_id'],
        'course_id': lp['course_id'],
        'lessons_completed': lessons_completed,
        'quiz_scores': quiz_scores,
        'current_lesson': lp['current_lesson']
    }

# QuizResult helper functions
def create_quiz_result(mongo, qr_data):
    """Create a quiz result record."""
    qr = {
        'id': str(uuid.uuid4()),
        'user_id': qr_data.get('user_id'),
        'session_id': qr_data['session_id'],
        'created_at': qr_data.get('created_at', datetime.utcnow()),
        'first_name': qr_data.get('first_name'),
        'email': qr_data.get('email'),
        'send_email': qr_data.get('send_email', False),
        'personality': qr_data.get('personality'),
        'score': qr_data.get('score'),
        'badges': json.dumps(qr_data.get('badges', [])),
        'insights': json.dumps(qr_data.get('insights', [])),
        'tips': json.dumps(qr_data.get('tips', []))
    }
    mongo.db.quiz_results.insert_one(qr)
    return qr

def get_quiz_results(mongo, filters):
    """Retrieve quiz result records by filters."""
    return list(mongo.db.quiz_results.find(filters, {'_id': 0}))

def to_dict_quiz_result(qr):
    """Convert quiz result document to dict."""
    try:
        badges = json.loads(qr['badges']) if qr.get('badges') else []
        insights = json.loads(qr['insights']) if qr.get('insights') else []
        tips = json.loads(qr['tips']) if qr.get('tips') else []
    except json.JSONDecodeError:
        current_app.logger.error(f"Invalid JSON in QuizResult ID {qr['id']}")
        badges = []
        insights = []
        tips = []
    return {
        'id': qr['id'],
        'user_id': qr['user_id'],
        'session_id': qr['session_id'],
        'created_at': qr['created_at'].isoformat() + "Z" if isinstance(qr['created_at'], datetime) else qr['created_at'],
        'first_name': qr['first_name'],
        'email': qr['email'],
        'send_email': qr['send_email'],
        'personality': qr['personality'],
        'score': qr['score'],
        'badges': badges,
        'insights': insights,
        'tips': tips
    }

# Feedback helper functions
def create_feedback(mongo, feedback_data):
    """Create a feedback record."""
    feedback = {
        'id': int(uuid.uuid4().int & (1<<31)-1),
        'user_id': feedback_data.get('user_id'),
        'session_id': feedback_data['session_id'],
        'created_at': feedback_data.get('created_at', datetime.utcnow()),
        'tool_name': feedback_data['tool_name'],
        'rating': feedback_data['rating'],
        'comment': feedback_data.get('comment')
    }
    mongo.db.feedback.insert_one(feedback)
    return feedback

def get_feedback(mongo, filters):
    """Retrieve feedback records by filters."""
    return list(mongo.db.feedback.find(filters, {'_id': 0}))

def to_dict_feedback(feedback):
    """Convert feedback document to dict."""
    return {
        'id': feedback['id'],
        'user_id': feedback['user_id'],
        'session_id': feedback['session_id'],
        'created_at': feedback['created_at'].isoformat() + "Z" if isinstance(feedback['created_at'], datetime) else feedback['created_at'],
        'tool_name': feedback['tool_name'],
        'rating': feedback['rating'],
        'comment': feedback['comment']
    }

# ToolUsage helper functions
def create_tool_usage(mongo, tool_usage_data):
    """Create a tool usage record."""
    tool_usage = {
        'id': str(uuid.uuid4()),
        'tool_name': tool_usage_data['tool_name'],
        'user_id': tool_usage_data.get('user_id'),
        'session_id': tool_usage_data['session_id'],
        'action': tool_usage_data.get('action', 'unknown'),
        'created_at': tool_usage_data.get('created_at', datetime.utcnow())
    }
    mongo.db.tool_usage.insert_one(tool_usage)
    return tool_usage

def get_tool_usage(mongo, filters):
    """Retrieve tool usage records by filters."""
    return list(mongo.db.tool_usage.find(filters, {'_id': 0}))

def to_dict_tool_usage(tu):
    """Convert tool usage document to dict."""
    return {
        'id': tu['id'],
        'tool_name': tu['tool_name'],
        'user_id': tu['user_id'],
        'session_id': tu['session_id'],
        'action': tu['action'],
        'created_at': tu['created_at'].isoformat() + "Z" if isinstance(tu['created_at'], datetime) else tu['created_at']
    }

def log_tool_usage(mongo, tool_name, user_id=None, session_id=None, action=None, details=None):
    """
    Log tool usage to the MongoDB tool_usage collection.
    
    Args:
        mongo: PyMongo instance
        tool_name (str): Name of the tool (e.g., 'financial_health', 'budget')
        user_id (int): ID of the authenticated user (None if unauthenticated)
        session_id (str): Session ID for tracking unauthenticated users
        action (str): Action performed (e.g., 'step1_view', 'dashboard_submit')
        details (dict): Additional details for logging
    """
    try:
        tool_usage = {
            'id': str(uuid.uuid4()),
            'tool_name': tool_name,
            'user_id': user_id,
            'session_id': session_id or session.get('sid', 'unknown'),
            'action': action or 'unknown',
            'created_at': datetime.utcnow()
        }
        mongo.db.tool_usage.insert_one(tool_usage)
        current_app.logger.info(f"Logged tool usage: {tool_name} for session {session_id}", extra={'details': details})
    except Exception as e:
        current_app.logger.error(f"Failed to log tool usage: {str(e)}", extra={'tool_name': tool_name, 'session_id': session_id, 'details': details})
        raise
