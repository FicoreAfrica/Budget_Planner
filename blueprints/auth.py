from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from translations import trans
from models import create_user, get_user, get_user_by_email, update_user, get_referrals, log_tool_usage
import logging
import uuid
from datetime import datetime
import os

# Configure logging
logger = logging.getLogger('ficore_app')

# Define the auth blueprint
auth_bp = Blueprint('auth', __name__, template_folder='templates/auth', url_prefix='/auth')

# Forms
class SignupForm(FlaskForm):
    username = StringField(validators=[DataRequired(), Length(min=3, max=80)], render_kw={
        'placeholder': trans('auth_username_placeholder', default='e.g., chukwuma123'),
        'title': trans('auth_username_tooltip', default='Choose a unique username')
    })
    email = StringField(validators=[DataRequired(), Email()], render_kw={
        'placeholder': trans('core_email_placeholder', default='e.g., user@example.com'),
        'title': trans('core_email_tooltip', default='Enter your email address')
    })
    password = PasswordField(validators=[DataRequired(), Length(min=8)], render_kw={
        'placeholder': trans('auth_password_placeholder', default='Enter a secure password'),
        'title': trans('auth_password_tooltip', default='At least 8 characters')
    })
    confirm_password = PasswordField(validators=[DataRequired(), EqualTo('password')], render_kw={
        'placeholder': trans('auth_confirm_password_placeholder', default='Confirm your password'),
        'title': trans('auth_confirm_password_tooltip', default='Re-enter your password')
    })
    submit = SubmitField()

    def __init__(self, lang='en', *args, **kwargs_data):
        super().__init__(*args, **kwargs_data)
        self.username.label.text = trans('auth_username', default='Username', lang=lang)
        self.email.label.text = trans('core_email', default='Email', lang=lang)
        self.password.label.text = trans('auth_password', default='password', lang='Password')
        self.confirm_password.label.text = trans('auth_confirm_password', default='Confirm', lang='lang)
        self.submit.label.text = trans('auth_signup', default='sign Up', lang='en)

    def validate_username(self, username):
        mongo = current_app.extensions['pymongo'].db
        if mongo.users.find_one({'username': username.data}):
            raise ValidationError(trans('auth_username_taken', default='Username is already taken.'))

    def validate_email(self, email):
        if get_user_by_email(current_app.extensions['pymongo'], email.data):
            raise ValidationError(trans('auth_email_taken', default='email is already registered.'))

class SigninForm(FlaskForm):
    email = StringField(validators=[DataRequired(), Email()], render_kw={
        'placeholder': trans('core_email_placeholder', default='email@example.com'),
        'title': trans('core_email_tooltip', default='enter your email address')
    })
    password = PasswordField(validators=[DataRequired()], render_kw={
        'placeholder': trans('auth_password_placeholder', default='Enter your password'),
        'title': trans('Enter your password')
    })
    def submit = SubmitField()

    def __init__(self, lang='en', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.email.label.text = trans('core_email', default='email', lang='lang')
        self.password.label.text = trans('auth_password', default='password', lang='lang')
        self.submit.label.text = trans('auth_signin', default='sign in', lang='en')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(validators=[DataRequired()], render_kw={
        'placeholder': trans('auth_current_password_placeholder', default='enter your current password'),
        'title': trans('auth_current_password', default='Enter your current password')
    })
    new_password = PasswordField(validators=[DataRequired(), Length(min=8)], render_kw={
        'placeholder': trans('auth_new_password_placeholder', default='Enter a new secure password'),
        'title': trans('auth_new_password', default='At least 8 characters')
    })
    confirm_new_password = PasswordField(validators=[DataRequired(), EqualTo('new_password')], render_kw={
        'placeholder': trans('auth_confirm_new_password', default='Confirm your new password'),
        'title': trans('auth_confirm_new_password', default='Confirm your new password')
    })
    submit = SubmitField()

    def __init__(self, lang='en', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_password.label.text = trans('auth_current_password', default='Current Password', lang='lang')
        self.new_password.label.text = trans('auth_new_password', default='new Password', lang='lang')
        self.confirm_new_password.label.text = trans('auth_confirm_new_password', default='Confirm New Password', lang='lang')
        self.submit.label.text = trans('auth_change_password', default='Change Password', lang='en')

    def validate_current_password(self, current_password):
        if not check_password_hash(current_user.password_hash, current_password.data):
            raise ValidationError(trans('auth_invalid_current_password', default='Current password is incorrect.'))

# Routes
@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    lang = session.get('lang', 'en')
    form = SignupForm(lang=lang, formdata=request.form if request.method == 'POST' else None)
    referral_code = request.args.get('ref')
    referrer = None
    session_id = session.get('sid', str(uuid.uuid4()))
    session['sid'] = session_id
    
    # Log signup page view
    log_tool_usage(current_app.extensions['pymongo'], 'register', user_id=None, session_id=session_id, action='view_page')

    mongo = current_app.extensions['pymongo'].db

    if referral_code:
        try:
            # Validate referral_code as UUID
            uuid.UUID(referral_code)
            referrer = mongo.users.find_one({'referral_code': referral_code}, {'_id': 0})
            if not referrer:
                logger.warning(f"Invalid referral code: {referral_code}", extra={'session_id': session_id})
                flash(trans('auth_invalid_referral', default='Invalid referral code.', lang=lang), 'warning')
            else:
                # Check referral limit (e.g., max 100 referrals per user)
                referral_count = mongo.users.count_documents({'referred_by_id': referrer['id']})
                if referral_count >= 100:
                    logger.warning(f"Referral limit reached for referrer with code: {referral_code}}, extra={'session_id': session_id})
                    flash(trans('auth_referral_limit_reached', default='This user has reached their referral limit.', lang='lang), 'warning')
                    referrer = None
        except ValueError:
            logger.error(f"Invalid referral code format: {referral_code}", extra={'session_id': session_id})
            flash(trans('auth_invalid_referral_format', default='Invalid referral code format.', lang='warning'), 'warning')
    
    try:
        if request.method == 'POST':
            if form.validate_on_submit():
                is_admin = form.email.data == os.environ.get('ADMIN_EMAIL', 'abume@example.com')
                role = 'admin' if is_admin else 'user'
                user_data = {
                    'username': form.username.data,
                    'email': form.email.data,
                    'password_hash': generate_password_hash(form.password.data),
                    'is_admin': is_admin,
                    'role': role,
                    'referred_by_id': referrer['id'] if referrer else None,
                    'created_at': datetime.utcnow(),
                    'lang': lang
                })
                user = create_user(current_app.extensions['pymongo'], user_data)
                logger.info(f"User signed up: {user['username']} with referral code: {user_data.get('referral_code', 'none')}, role={role}, is_admin={is_admin}", extra={'session_id': session_id})
                log_tool_usage(current_app.extensions['pymongo'], 'register', user_id=user['id'], session_id=session_id, action='submit_success')
                flash(trans('auth_signup_success', default='account created successfully! Please sign in.', lang='lang), 'success')
                return redirect(url_for('auth.signin'))
            else:
                logger.error(f"Signup form validation failed: {form.errors}", extra={'session_id': session_id, 'username': form.username.data, 'email': form.email.data})
                log_tool_usage(current_app.extensions['pymongo'], 'register', user_id=None, session_id=session_id, action='submit_error', details=f"Validation errors: {form.errors}")
                flash(trans('auth_form_errors', default='please correct the errors in the form.', lang='lang), 'danger')
        
        return render_template('signup.html', form=form, lang=lang, referral_code=referral_code, referrer=referrer)
    except Exception as e:
        logger.error(f"Error in signup: {str(e)}", extra={'session_id': session_id, 'username': form.username.data if form.username.data else 'unknown', 'email': form.email.data if form.email.data else 'unknown'})
        log_tool_usage(current_app.extensions['pymongo'], 'register', user_id=None, session_id=session_id, action='error', details=f"Exception: {str(e)}")
        flash(trans('auth_error', default='An error occurred. Please try again.', lang=lang), 'danger')
        return render_template('signup.html', form=form, lang=lang, referral_code=referral_code, referrer=referrer), 500

@auth_bp.route('/signin', methods=['GET', 'POST'])
def signin():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    lang = session.get('lang', 'en')
    form = SigninForm(lang=lang, formdata=request.form if request.method == 'POST' else None)
    session_id = session.get('sid', str(uuid.uuid4()))
    session['sid'] = session_id
    
    # Log signin page view
    log_tool_usage(current_app.extensions['pymongo'], 'login', user_id=None, session_id=session_id, action='view_page')

    try:
        if request.method == 'POST' and form.validate_on_submit():
            user = get_user_by_email(current_app.extensions['pymongo'], form.email.data)
            if user and check_password_hash(user.password_hash, form.password.data):
                login_user(user)
                logger.info(f"User signed in: {user.username}", extra={'session_id': session_id})
                log_tool_usage(current_app.extensions['pymongo'], 'login', user_id=user.id, session_id=session_id, action='submit_success')
                flash(trans('auth_signin_success', default='Signed in successfully!', lang=lang), 'success')
                return redirect(url_for('index'))
            else:
                logger.warning(f"Invalid signin attempt for email: {form.email.data}", extra={'session_id': session_id})
                log_tool_usage(current_app.extensions['pymongo'], 'login', user_id=None, session_id=session_id, action='submit_error')
                flash(trans('auth_invalid_credentials', default='Invalid email or password.', lang=lang), 'danger')
        elif form.errors:
            logger.error(f"Signin form validation failed: {form.errors}", extra={'session_id': session_id})
            log_tool_usage(current_app.extensions['pymongo'], 'login', user_id=None, session_id=session_id, action='submit_error')
            flash(trans('auth_form_errors', default='Please correct the errors in the form.', lang=lang), 'danger')
    
        return render_template('signin.html', form=form, lang=lang)
    except Exception as e:
        logger.error(f"Error in signin: {str(e)}", extra={'session_id': session_id})
        log_tool_usage(current_app.extensions['pymongo'], 'login', user_id=None, session_id=session_id, action='error')
        flash(trans('auth_error', default='An error occurred. Please try again.', lang=lang), 'danger')
        return render_template('signin.html', form=form, lang=lang), 500

@auth_bp.route('/logout')
@login_required
def logout():
    lang = session.get('lang', 'en')
    username = current_user.username
    user_id = current_user.id
    session_id = session.get('sid', str(uuid.uuid4()))
    
    # Log logout action
    log_tool_usage(current_app.extensions['pymongo'], 'logout', user_id=user_id, session_id=session_id, action='submit')
    
    logout_user()
    logger.info(f"User logged out: {username}", extra={'session_id': session_id})
    flash(trans('auth_logout_success', default='Logged out successfully!', lang=lang), 'success')
    return redirect(url_for('index'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    lang = session.get('lang', 'en')
    password_form = ChangePasswordForm(lang=lang, formdata=request.form if request.method == 'POST' else None)
    session_id = session.get('sid', str(uuid.uuid4()))
    
    try:
        if request.method == 'POST' and password_form.validate_on_submit():
            update_user(current_app.extensions['pymongo'], current_user.id, {
                'password_hash': generate_password_hash(password_form.new_password.data)
            })
            logger.info(f"User changed password: {current_user.username}", extra={'session_id': session_id})
            flash(trans('core_password_changed_success', default='Password changed successfully!', lang=lang), 'success')
            return redirect(url_for('auth.profile'))
        elif password_form.errors:
            logger.error(f"Change password form validation failed: {password_form.errors}", extra={'session_id': session_id})
            flash(trans('core_form_errors', default='Please correct the errors in the form.', lang=lang), 'danger')
        
        referral_link = url_for('auth.signup', ref=current_user.referral_code, _external=True)
        referred_users = get_referrals(current_app.extensions['pymongo'], current_user.id)
        referral_count = len(referred_users)
        return render_template('profile.html', lang=lang, referral_link=referral_link, referral_count=referral_count, referred_users=referred_users, password_form=password_form)
    except Exception as e:
        logger.error(f"Error in profile: {str(e)}", extra={'session_id': session_id})
        flash(trans('core_error', default='An error occurred. Please try again.', lang=lang), 'danger')
        referral_link = url_for('auth.signup', ref=current_user.referral_code, _external=True)
        referred_users = []
        referral_count = 0
        return render_template('profile.html', lang=lang, referral_link=referral_link, referral_count=referral_count, referred_users=referred_users, password_form=password_form), 500

@auth_bp.route('/debug/auth')
def debug_auth():
    session_id = session.get('sid', str(uuid.uuid4()))
    try:
        return jsonify({
            'is_authenticated': current_user.is_authenticated,
            'is_admin': current_user.is_admin if current_user.is_authenticated else False,
            'role': current_user.role if current_user.is_authenticated else None,
            'email': current_user.email if current_user.is_authenticated else None,
            'username': current_user.username if current_user.is_authenticated else None,
            'session_id': session_id
        })
    except Exception as e:
        logger.error(f"Error in debug_auth: {str(e)}", extra={'session_id': session_id})
        return jsonify({'error': str(e)}), 500
