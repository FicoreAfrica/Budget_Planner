from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from translations import trans
from extensions import db
from models import User, log_tool_usage
import logging
import uuid
from datetime import datetime

# Configure logging
logger = logging.getLogger('ficore_app')

# Define the auth blueprint
auth_bp = Blueprint('auth', __name__, template_folder='templates', url_prefix='/auth')

# Forms
class SignupForm(FlaskForm):
    username = StringField(validators=[DataRequired(), Length(min=3, max=80)], render_kw={
        'placeholder': trans('core_auth_username_placeholder', default='e.g., chukwuma123'),
        'title': trans('core_auth_username_tooltip', default='Choose a unique username')
    })
    email = StringField(validators=[DataRequired(), Email()], render_kw={
        'placeholder': trans('core_email_placeholder', default='e.g., user@example.com'),
        'title': trans('core_email_tooltip', default='Enter your email address')
    })
    password = PasswordField(validators=[DataRequired(), Length(min=8)], render_kw={
        'placeholder': trans('core_auth_password_placeholder', default='Enter a secure password'),
        'title': trans('core_auth_password_tooltip', default='At least 8 characters')
    })
    confirm_password = PasswordField(validators=[DataRequired(), EqualTo('password')], render_kw={
        'placeholder': trans('core_auth_confirm_password_placeholder', default='Confirm your password'),
        'title': trans('core_auth_confirm_password_tooltip', default='Re-enter your password')
    })
    submit = SubmitField()

    def __init__(self, lang='en', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.username.label.text = trans('core_auth_username', default='Username', lang=lang)
        self.email.label.text = trans('core_email', default='Email', lang=lang)
        self.password.label.text = trans('core_auth_password', default='Password', lang=lang)
        self.confirm_password.label.text = trans('core_auth_confirm_password', default='Confirm Password', lang=lang)
        self.submit.label.text = trans('core_auth_signup', default='Sign Up', lang=lang)

    def validate_username(self, username):
        if User.query.filter_by(username=username.data).first():
            raise ValidationError(trans('core_auth_username_taken', default='Username is already taken.'))

    def validate_email(self, email):
        if User.query.filter_by(email=email.data).first():
            raise ValidationError(trans('core_auth_email_taken', default='Email is already registered.'))

class SigninForm(FlaskForm):
    email = StringField(validators=[DataRequired(), Email()], render_kw={
        'placeholder': trans('core_email_placeholder', default='e.g., user@example.com'),
        'title': trans('core_email_tooltip', default='Enter your email address')
    })
    password = PasswordField(validators=[DataRequired()], render_kw={
        'placeholder': trans('core_auth_password_placeholder', default='Enter your password'),
        'title': trans('core_auth_password_tooltip', default='Enter your password')
    })
    submit = SubmitField()

    def __init__(self, lang='en', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.email.label.text = trans('core_email', default='Email', lang=lang)
        self.password.label.text = trans('core_auth_password', default='Password', lang=lang)
        self.submit.label.text = trans('core_auth_signin', default='Sign In', lang=lang)

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(validators=[DataRequired()], render_kw={
        'placeholder': trans('core_auth_current_password_placeholder', default='Enter your current password'),
        'title': trans('core_auth_current_password_tooltip', default='Enter your current password')
    })
    new_password = PasswordField(validators=[DataRequired(), Length(min=8)], render_kw={
        'placeholder': trans('core_auth_new_password_placeholder', default='Enter a new secure password'),
        'title': trans('core_auth_new_password_tooltip', default='At least 8 characters')
    })
    confirm_new_password = PasswordField(validators=[DataRequired(), EqualTo('new_password')], render_kw={
        'placeholder': trans('core_auth_confirm_new_password_placeholder', default='Confirm your new password'),
        'title': trans('core_auth_confirm_new_password_tooltip', default='Re-enter your new password')
    })
    submit = SubmitField()

    def __init__(self, lang='en', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_password.label.text = trans('core_auth_current_password', default='Current Password', lang=lang)
        self.new_password.label.text = trans('core_auth_new_password', default='New Password', lang=lang)
        self.confirm_new_password.label.text = trans('core_auth_confirm_new_password', default='Confirm New Password', lang=lang)
        self.submit.label.text = trans('core_auth_change_password', default='Change Password', lang=lang)

    def validate_current_password(self, current_password):
        if not check_password_hash(current_user.password_hash, current_password.data):
            raise ValidationError(trans('core_auth_invalid_current_password', default='Current password is incorrect.'))

# Routes
@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    lang = session.get('lang', 'en')
    form = SignupForm(lang=lang, formdata=request.form if request.method == 'POST' else None)
    referral_code = request.args.get('ref')
    referrer = None
    session_id = session.get('sid')  # Use existing session_id
    
    # Log signup page view
    log_tool_usage('register', None, session_id, 'view_page')

    if referral_code and referral_code.strip():
        try:
            # Validate referral_code as a UUID
            uuid.UUID(referral_code)
            referrer = User.query.filter_by(referral_code=referral_code).first()
            if not referrer:
                logger.warning(f"Invalid referral code: {referral_code}", extra={'session_id': session_id})
                flash(trans('core_auth_invalid_referral', default='Invalid referral code.', lang=lang), 'warning')
            else:
                # Check referral limit (e.g., max 100 referrals per user)
                if len(referrer.referrals) >= 100:
                    logger.warning(f"Referral limit reached for referrer with code: {referral_code}", extra={'session_id': session_id})
                    flash(trans('core_auth_referral_limit_reached', default='This user has reached their referral limit.', lang=lang), 'warning')
                    referrer = None
        except ValueError:
            logger.warning(f"Invalid referral code format: {referral_code}", extra={'session_id': session_id})
            flash(trans('core_auth_invalid_referral_format', default='Invalid referral code format.', lang=lang), 'warning')
    
    try:
        if request.method == 'POST':
            if form.validate_on_submit():
                user = User(
                    username=form.username.data,
                    email=form.email.data,
                    password_hash=generate_password_hash(form.password.data),
                    is_admin=False,  # Default to False for all users
                    referred_by_id=referrer.id if referrer else None,
                    created_at=datetime.utcnow(),
                    lang=lang
                )
                db.session.add(user)
                db.session.commit()
                logger.info(f"User signed up: {user.username} with referral code: {referral_code or 'none'}", extra={'session_id': session_id})
                log_tool_usage('register', user.id, session_id, 'submit_success')
                flash(trans('core_auth_signup_success', default='Account created successfully! Please sign in.', lang=lang), 'success')
                return redirect(url_for('auth.signin'))
            else:
                logger.error(f"Signup form validation failed: {form.errors}", extra={'session_id': session_id, 'username': form.username.data, 'email': form.email.data})
                log_tool_usage('register', None, session_id, 'submit_error', details=f"Validation errors: {form.errors}")
                flash(trans('core_auth_form_errors', default='Please correct the errors in the form.', lang=lang), 'danger')
        
        return render_template('signup.html', form=form, lang=lang, referral_code=referral_code, referrer=referrer)
    except Exception as e:
        logger.error(f"Error in signup: {str(e)}", extra={'session_id': session_id, 'username': form.username.data if form.username.data else 'unknown', 'email': form.email.data if form.email.data else 'unknown'})
        log_tool_usage('register', None, session_id, 'error', details=f"Exception: {str(e)}")
        flash(trans('core_auth_error', default='An error occurred. Please try again.', lang=lang), 'danger')
        return render_template('signup.html', form=form, lang=lang, referral_code=referral_code, referrer=referrer), 500

@auth_bp.route('/signin', methods=['GET', 'POST'])
def signin():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    lang = session.get('lang', 'en')
    form = SigninForm(lang=lang, formdata=request.form if request.method == 'POST' else None)
    session_id = session.get('sid')  # Use existing session_id
    
    # Log signin page view
    log_tool_usage('login', None, session_id, 'view_page')

    try:
        with db.session.begin():
            if request.method == 'POST' and form.validate_on_submit():
                user = User.query.filter_by(email=form.email.data).first()
                if user and check_password_hash(user.password_hash, form.password.data):
                    login_user(user)
                    logger.info(f"User signed in: {user.username}", extra={'session_id': session_id})
                    log_tool_usage('login', user.id, session_id, 'submit_success')
                    flash(trans('core_auth_signin_success', default='Signed in successfully!', lang=lang), 'success')
                    return redirect(url_for('index'))
                else:
                    logger.warning(f"Invalid signin attempt for email: {form.email.data}", extra={'session_id': session_id})
                    log_tool_usage('login', None, session_id, 'submit_error')
                    flash(trans('core_auth_invalid_credentials', default='Invalid email or password.', lang=lang), 'danger')
            elif form.errors:
                logger.error(f"Signin form validation failed: {form.errors}", extra={'session_id': session_id})
                log_tool_usage('login', None, session_id, 'submit_error')
                flash(trans('core_auth_form_errors', default='Please correct the errors in the form.', lang=lang), 'danger')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in signin: {str(e)}", extra={'session_id': session_id})
        log_tool_usage('login', None, session_id, 'error')
        flash(trans('core_auth_error', default='An error occurred. Please try again.', lang=lang), 'danger')
        return render_template('signin.html', form=form, lang=lang), 500
    
    return render_template('signin.html', form=form, lang=lang)

@auth_bp.route('/logout')
@login_required
def logout():
    lang = session.get('lang', 'en')
    username = current_user.username
    user_id = current_user.id
    session_id = session.get('sid')  # Use existing session_id
    
    # Log logout action
    log_tool_usage('logout', user_id, session_id, 'submit')
    
    logout_user()
    logger.info(f"User logged out: {username}", extra={'session_id': session_id})
    flash(trans('core_core_auth_logout_success', default='Logged out successfully!', lang=lang), 'success')
    return redirect(url_for('index'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    lang = session.get('lang', 'en')
    password_form = ChangePasswordForm(lang=lang, formdata=request.form if request.method == 'POST' else None)
    session_id = session.get('sid')  # Use existing session_id
    
    try:
        if request.method == 'POST' and password_form.validate_on_submit():
            current_user.password_hash = generate_password_hash(password_form.new_password.data)
            db.session.commit()
            logger.info(f"User changed password: {current_user.username}", extra={'session_id': session_id})
            flash(trans('core_password_changed_success', default='Password changed successfully!', lang=lang), 'success')
            return redirect(url_for('auth.profile'))
        elif password_form.errors:
            logger.error(f"Change password form validation failed: {password_form.errors}", extra={'session_id': session_id})
            flash(trans('core_form_errors', default='Please correct the errors in the form.', lang=lang), 'danger')
        
        referral_link = url_for('auth.signup', ref=current_user.referral_code, _external=True)
        referral_count = len(current_user.referrals)
        referred_users = current_user.referrals
        return render_template('profile.html', lang=lang, referral_link=referral_link, referral_count=referral_count, referred_users=referred_users, password_form=password_form)
    except Exception as e:
        logger.error(f"Error in profile: {str(e)}", extra={'session_id': session_id})
        flash(trans('core_error', default='An error occurred. Please try again.', lang=lang), 'danger')
        return render_template('profile.html', lang=lang, referral_link=referral_link, referral_count=referral_count, referred_users=referred_users, password_form=password_form), 500

@auth_bp.route('/debug/auth')
def debug_auth():
    session_id = session.get('sid')  # Use existing session_id
    try:
        return jsonify({
            'is_authenticated': current_user.is_authenticated,
            'is_admin': current_user.is_admin if current_user.is_authenticated else False,
            'email': current_user.email if current_user.is_authenticated else None,
            'username': current_user.username if current_user.is_authenticated else None,
            'session_id': session_id
        })
    except Exception as e:
        logger.error(f"Error in debug_auth: {str(e)}", extra={'session_id': session_id})
        return jsonify({'error': str(e)}), 500
