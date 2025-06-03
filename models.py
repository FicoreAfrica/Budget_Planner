from app import db
from datetime import datetime, date
import json

# User model for authentication
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

# Course model for Learning Hub static content
class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.String(50), primary_key=True)
    title_key = db.Column(db.String(100), nullable=False)
    title_en = db.Column(db.String(100), nullable=False)
    title_ha = db.Column(db.String(100), nullable=False)
    description_en = db.Column(db.Text, nullable=False)
    description_ha = db.Column(db.Text, nullable=False)
    is_premium = db.Column(db.Boolean, default=False, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'title_key': self.title_key,
            'title_en': self.title_en,
            'title_ha': self.title_ha,
            'description_en': self.description_en,
            'description_ha': self.description_ha,
            'is_premium': self.is_premium
        }

# Financial Health model
class FinancialHealth(db.Model):
    __tablename__ = 'financial_health'
    id = db.Column(db.String(36), primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    email = db.Column(db.String(120), nullable=True)
    first_name = db.Column(db.String(50), nullable=True)
    user_type = db.Column(db.String(20), nullable=True)
    income = db.Column(db.Float, nullable=True)
    expenses = db.Column(db.Float, nullable=True)
    debt = db.Column(db.Float, nullable=True)
    interest_rate = db.Column(db.Float, nullable=True)
    debt_to_income = db.Column(db.Float, nullable=True)
    savings_rate = db.Column(db.Float, nullable=True)
    interest_burden = db.Column(db.Float, nullable=True)
    score = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(50), nullable=True)
    status_key = db.Column(db.String(50), nullable=True)
    badges = db.Column(db.Text, nullable=True)  # Stored as JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    step = db.Column(db.Integer, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'email': self.email,
            'first_name': self.first_name,
            'user_type': self.user_type,
            'income': self.income,
            'expenses': self.expenses,
            'debt': self.debt,
            'interest_rate': self.interest_rate,
            'debt_to_income': self.debt_to_income,
            'savings_rate': self.savings_rate,
            'interest_burden': self.interest_burden,
            'score': self.score,
            'status': self.status,
            'status_key': self.status_key,
            'badges': json.loads(self.badges) if self.badges else [],
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'step': self.step
        }

# Budget model
class Budget(db.Model):
    __tablename__ = 'budget'
    id = db.Column(db.String(36), primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    email = db.Column(db.String(120), nullable=True)
    income = db.Column(db.Float, nullable=False, default=0.0)
    fixed_expenses = db.Column(db.Float, nullable=False, default=0.0)
    variable_expenses = db.Column(db.Float, nullable=False, default=0.0)
    savings_goal = db.Column(db.Float, nullable=False, default=0.0)
    surplus_deficit = db.Column(db.Float, nullable=False, default=0.0)
    housing = db.Column(db.Float, nullable=False, default=0.0)
    food = db.Column(db.Float, nullable=False, default=0.0)
    transport = db.Column(db.Float, nullable=False, default=0.0)
    dependents = db.Column(db.Float, nullable=False, default=0.0)
    miscellaneous = db.Column(db.Float, nullable=False, default=0.0)
    others = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'email': self.email,
            'income': self.income,
            'fixed_expenses': self.fixed_expenses,
            'variable_expenses': self.variable_expenses,
            'savings_goal': self.savings_goal,
            'surplus_deficit': self.surplus_deficit,
            'housing': self.housing,
            'food': self.food,
            'transport': self.transport,
            'dependents': self.dependents,
            'miscellaneous': self.miscellaneous,
            'others': self.others,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

# Bill model
class Bill(db.Model):
    __tablename__ = 'bills'
    id = db.Column(db.String(36), primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    email = db.Column(db.String(120), nullable=True)
    first_name = db.Column(db.String(50), nullable=True)
    bill_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    frequency = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    send_email = db.Column(db.Boolean, default=False, nullable=False)
    reminder_days = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'email': self.email,
            'first_name': self.first_name,
            'bill_name': self.bill_name,
            'amount': self.amount,
            'due_date': self.due_date.strftime('%Y-%m-%d') if self.due_date else None,
            'frequency': self.frequency,
            'category': self.category,
            'status': self.status,
            'send_email': self.send_email,
            'reminder_days': self.reminder_days,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

# Net Worth model
class NetWorth(db.Model):
    __tablename__ = 'net_worth'
    id = db.Column(db.String(36), primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    email = db.Column(db.String(120), nullable=True)
    first_name = db.Column(db.String(50), nullable=True)
    cash_savings = db.Column(db.Float, nullable=False, default=0.0)
    investments = db.Column(db.Float, nullable=False, default=0.0)
    property = db.Column(db.Float, nullable=False, default=0.0)
    loans = db.Column(db.Float, nullable=False, default=0.0)
    total_assets = db.Column(db.Float, nullable=False, default=0.0)
    total_liabilities = db.Column(db.Float, nullable=False, default=0.0)
    net_worth = db.Column(db.Float, nullable=False, default=0.0)
    badges = db.Column(db.Text, nullable=True)  # Stored as JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    send_email = db.Column(db.Boolean, default=False, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'email': self.email,
            'first_name': self.first_name,
            'cash_savings': self.cash_savings,
            'investments': self.investments,
            'property': self.property,
            'loans': self.loans,
            'total_assets': self.total_assets,
            'total_liabilities': self.total_liabilities,
            'net_worth': self.net_worth,
            'badges': json.loads(self.badges) if self.badges else [],
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'send_email': self.send_email
        }

# Emergency Fund model
class EmergencyFund(db.Model):
    __tablename__ = 'emergency_fund'
    id = db.Column(db.String(36), primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    first_name = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    email_opt_in = db.Column(db.Boolean, default=False, nullable=False)
    lang = db.Column(db.String(10), nullable=True)
    monthly_expenses = db.Column(db.Float, nullable=True)
    monthly_income = db.Column(db.Float, nullable=True)
    current_savings = db.Column(db.Float, nullable=True)
    risk_tolerance_level = db.Column(db.String(20), nullable=True)
    dependents = db.Column(db.Integer, nullable=True)
    timeline = db.Column(db.Integer, nullable=True)
    recommended_months = db.Column(db.Integer, nullable=True)
    target_amount = db.Column(db.Float, nullable=True)
    savings_gap = db.Column(db.Float, nullable=True)
    monthly_savings = db.Column(db.Float, nullable=True)
    percent_of_income = db.Column(db.Float, nullable=True)
    badges = db.Column(db.Text, nullable=True)  # Stored as JSON string
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'first_name': self.first_name,
            'email': self.email,
            'email_opt_in': self.email_opt_in,
            'lang': self.lang,
            'monthly_expenses': self.monthly_expenses,
            'monthly_income': self.monthly_income,
            'current_savings': self.current_savings,
            'risk_tolerance_level': self.risk_tolerance_level,
            'dependents': self.dependents,
            'timeline': self.timeline,
            'recommended_months': self.recommended_months,
            'target_amount': self.target_amount,
            'savings_gap': self.savings_gap,
            'monthly_savings': self.monthly_savings,
            'percent_of_income': self.percent_of_income,
            'badges': json.loads(self.badges) if self.badges else [],
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

# Learning Progress model
class LearningProgress(db.Model):
    __tablename__ = 'learning_progress'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    course_id = db.Column(db.String(50), nullable=False)
    lessons_completed = db.Column(db.Text, default='[]', nullable=False)  # JSON string
    quiz_scores = db.Column(db.Text, default='{}', nullable=False)  # JSON string
    current_lesson = db.Column(db.String(50), nullable=True)

    __table_args__ = (db.UniqueConstraint('session_id', 'course_id', name='uix_session_course'),)

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'course_id': self.course_id,
            'lessons_completed': json.loads(self.lessons_completed),
            'quiz_scores': json.loads(self.quiz_scores),
            'current_lesson': self.current_lesson
        }

# Quiz Result model
class QuizResult(db.Model):
    __tablename__ = 'quiz_results'
    id = db.Column(db.String(36), primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    email = db.Column(db.String(120), nullable=True)
    first_name = db.Column(db.String(50), nullable=True)
    personality = db.Column(db.String(50), nullable=True)
    score = db.Column(db.Integer, nullable=True)
    badges = db.Column(db.Text, nullable=True)  # Stored as JSON string
    insights = db.Column(db.Text, nullable=True)  # Stored as JSON string
    tips = db.Column(db.Text, nullable=True)  # Stored as JSON string
    send_email = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'email': self.email,
            'first_name': self.first_name,
            'personality': self.personality,
            'score': self.score,
            'badges': json.loads(self.badges) if self.badges else [],
            'insights': json.loads(self.insights) if self.insights else [],
            'tips': json.loads(self.tips) if self.tips else [],
            'send_email': self.send_email,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
