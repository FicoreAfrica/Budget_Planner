from flask import Blueprint, render_template, session
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from extensions import db
from models import User, ToolUsage
from app import trans
import logging

# Configure logging
logger = logging.getLogger('ficore_app.analytics')

# Define the admin blueprint
admin_bp = Blueprint('admin', __name__, template_folder='templates/admin', url_prefix='/admin')

@admin_bp.route('/')
@login_required
def dashboard():
    lang = session.get('lang', 'en')
    try:
        # Basic Stats
        total_users = User.query.count()
        last_day = datetime.utcnow() - timedelta(days=1)
        new_users_last_24h = User.query.filter(User.created_at >= last_day).count()
        tool_usage_total = ToolUsage.query.count()

        metrics = {
            'total_users': total_users,
            'new_users_last_24h': new_users_last_24h,
            'tool_usage_total': tool_usage_total
        }
        logger.info(f"Admin dashboard accessed by {current_user.username}", extra={'session_id': session.get('sid', 'no-session-id')})
        return render_template('admin_dashboard.html', lang=lang, metrics=metrics)
    except Exception as e:
        logger.error(f"Error in admin dashboard: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        return render_template('admin_dashboard.html', lang=lang, metrics={}), 500
