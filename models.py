from app import db
from datetime import datetime
import json

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

# Financial Health model
class FinancialHealth(db.Model):
    __tablename__ = 'financial_health'
    id = db.Column(db.String(36), primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    user_email = db.Column(db.String(120), nullable=True)
    first_name = db.Column(db.String(50))
    user_type = db.Column(db.String(20))
    income = db.Column(db.Float)
    expenses = db.Column(db.Float)
    debt = db.Column(db.Float)
    interest_rate = db.Column(db.Float)
    debt_to_income = db.Column(db.Float)
    savings_rate = db.Column(db.Float)
    interest_burden = db.Column(db.Float)
    score = db.Column(db.Float)
    status = db.Column(db.String(50))
    status_key = db.Column(db.String(50))
    badges = db.Column(db.Text)  # Stored as JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    step = db.Column(db.Integer)

# Budget model
class Budget(db.Model):
    __tablename__ = 'budget'
    id = db.Column(db.String(36), primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    user_email = db.Column(db.String(120), nullable=True)
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

# Bill model
class Bill(db.Model):
    __tablename__ = 'bills'
    id = db.Column(db.String(36), primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    user_email = db.Column(db.String(120), nullable=True)
    first_name = db.Column(db.String(50))
    bill_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    frequency = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    send_email = db.Column(db.Boolean, default=False)
    reminder_days = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_email': self.user_email,
            'first_name': self.first_name,
            'bill_name': self.bill_name,
            'amount': self.amount,
            'due_date': self.due_date.strftime('%Y-%m-%d'),
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
    user_email = db.Column(db.String(120), nullable=True)
    first_name = db.Column(db.String(50))
    cash_savings = db.Column(db.Float, nullable=False)
    investments = db.Column(db.Float, nullable=False)
    property = db.Column(db.Float, nullable=False)
    loans = db.Column(db.Float, nullable=False)
    total_assets = db.Column(db.Float, nullable=False)
    total_liabilities = db.Column(db.Float, nullable=False)
    net_worth = db.Column(db.Float, nullable=False)
    badges = db.Column(db.Text)  # Stored as JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Emergency Fund model
class EmergencyFund(db.Model):
    __tablename__ = 'emergency_fund'
    id = db.Column(db.String(36), primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    first_name = db.Column(db.String(50))
    email = db.Column(db.String(120))
    email_opt_in = db.Column(db.Boolean, default=False)
    lang = db.Column(db.String(10))
    monthly_expenses = db.Column(db.Float)
    monthly_income = db.Column(db.Float)
    current_savings = db.Column(db.Float)
    risk_tolerance_level = db.Column(db.String(20))
    dependents = db.Column(db.Integer)
    timeline = db.Column(db.Integer)
    recommended_months = db.Column(db.Integer)
    target_amount = db.Column(db.Float)
    savings_gap = db.Column(db.Float)
    monthly_savings = db.Column(db.Float)
    percent_of_income = db.Column(db.Float)
    badges = db.Column(db.Text)  # Stored as JSON string
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

# Learning Progress model
class LearningProgress(db.Model):
    __tablename__ = 'learning_progress'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), nullable=False)
    course_id = db.Column(db.String(50), nullable=False)
    lessons_completed = db.Column(db.Text, default='[]')  # JSON string
    quiz_scores = db.Column(db.Text, default='{}')        # JSON string
    current_lesson = db.Column(db.String(50))

    __table_args__ = (db.UniqueConstraint('session_id', 'course_id', name='uix_session_course'),)

    def to_dict(self):
        return {
            'lessons_completed': json.loads(self.lessons_completed),
            'quiz_scores': json.loads(self.quiz_scores),
            'current_lesson': self.current_lesson
        }

# Quiz Result model
class QuizResult(db.Model):
    __tablename__ = 'quiz_results'
    id = db.Column(db.String(36), primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    first_name = db.Column(db.String(50))
    personality = db.Column(db.String(50))
    score = db.Column(db.Integer)
    badges = db.Column(db.Text)  # Stored as JSON string
    insights = db.Column(db.Text)  # Stored as JSON string
    tips = db.Column(db.Text)  # Stored as JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
