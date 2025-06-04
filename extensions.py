from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin  # Add UserMixin import
from flask_session import Session
from flask_wtf.csrf import CSRFProtect
from datetime import datetime  # Ensure datetime is imported

db = SQLAlchemy()
login_manager = LoginManager()
session = Session()
csrf = CSRFProtect()

class User(db.Model, UserMixin):  # Add UserMixin
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    lang = db.Column(db.String(10), default='en')
