from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from extensions import db
from models import User, ToolUsage, Feedback
from app import admin_required, trans
import logging
import csv
from io import StringIO
from sqlalchemy import func, exc

# Configure logging
logger = logging.getLogger('ficore_app.analytics')

# Define the admin blueprint
admin_bp = Blueprint('admin', __name__, template_folder='templates/admin', url_prefix='/admin')

# Valid tools for filtering
VALID_TOOLS = [
    'register', 'login', 'logout',
    'financial_health', 'budget', 'bill', 'net_worth',
    'emergency_fund', 'learning_hub', 'quiz'
]

@admin_bp.route('/')
@login_required
@admin_required
def overview():
    """Admin dashboard overview page with enhanced debugging logs."""
    lang = session.get('lang', 'en') if 'lang' in session else 'en'
    session_id = session.get('sid', 'no-session-id')
    logger.info("Entering overview for user: %s", current_user.username, extra={'session_id': session_id})
    
    try:
        logger.info("Starting database session with no_autoflush")
        with db.session.no_autoflush() as read_session:
            logger.info("Inside no_autoflush context")
            
            # User Stats
            logger.info("Querying total users")
            total_users = read_session.query(User).count()
            logger.info("Queried total_users: %d", total_users)
            
            last_day = datetime.utcnow() - timedelta(days=1)
            logger.info("Querying new users in last 24 hours, since: %s", last_day)
            new_users_last_24h = read_session.query(User).filter(User.created_at >= last_day).count()
            logger.info("Queried new_users_last_24h: %d", new_users_last_24h)
            
            # Referral Stats
            logger.info("Querying total referrals")
            total_referrals = read_session.query(User).filter(User.referred_by_id.isnot(None)).count()
            logger.info("Queried total_referrals: %d", total_referrals)
            
            logger.info("Querying new referrals in last 24 hours")
            new_referrals_last_24h = read_session.query(User).filter(
                User.referred_by_id.isnot(None),
                User.created_at >= last_day
            ).count()
            logger.info("Queried new_referrals_last_24h: %d", new_referrals_last_24h)
            
            logger.info("Calculating referral conversion rate")
            referral_conversion_rate = (total_referrals / total_users * 100) if total_users else 0.0
            logger.info("Referral conversion rate: %.2f%%", referral_conversion_rate)
            
            # Tool Usage Stats
            logger.info("Querying total tool usage")
            tool_usage_total = read_session.query(ToolUsage).count()
            logger.info("Queried tool_usage_total: %d", tool_usage_total)
            
            logger.info("Querying tool usage by tool")
            usage_by_tool = read_session.query(ToolUsage.tool_name, func.count(ToolUsage.id)).group_by(ToolUsage.tool_name).all()
            logger.info("Queried usage_by_tool: %s", usage_by_tool)
            top_tools = sorted(usage_by_tool, key=lambda x: x[1], reverse=True)[:3]
            logger.info("Top tools: %s", top_tools)
            
            # Action Breakdown for Top Tools
            logger.info("Querying action breakdown for top tools")
            action_breakdown = {}
            for tool, _ in top_tools:
                logger.info("Querying actions for tool: %s", tool)
                actions = read_session.query(ToolUsage.action, func.count(ToolUsage.id))\
                    .filter(ToolUsage.tool_name == tool)\
                    .group_by(ToolUsage.action)\
                    .limit(5).all()
                action_breakdown[tool] = actions
                logger.info("Actions for %s: %s", tool, actions)
            
            # Engagement Metrics
            logger.info("Querying multi-tool users")
            multi_tool_users = read_session.query(ToolUsage.user_id, func.count(func.distinct(ToolUsage.tool_name)))\
                .filter(ToolUsage.tool_name.in_(VALID_TOOLS[3:]))\
                .group_by(ToolUsage.user_id)\
                .having(func.count(func.distinct(ToolUsage.tool_name)) > 1)\
                .count()
            logger.info("Queried multi_tool_users: %d", multi_tool_users)
            
            logger.info("Querying total sessions")
            total_sessions = read_session.query(func.count(func.distinct(ToolUsage.session_id)))\
                .filter(ToolUsage.tool_name.in_(VALID_TOOLS[3:])).scalar()
            logger.info("Queried total_sessions: %d", total_sessions)
            
            multi_tool_ratio = (multi_tool_users / total_sessions * 100) if total_sessions else 0.0
            logger.info("Multi-tool ratio: %.2f%%", multi_tool_ratio)
            
            # Anonymous to registered conversion
            logger.info("Querying anonymous sessions")
            anon_sessions = read_session.query(ToolUsage.session_id)\
                .filter(ToolUsage.user_id.is_(None), ToolUsage.tool_name.in_(VALID_TOOLS[3:]))\
                .distinct().subquery()
            logger.info("Queried anonymous sessions")
            
            logger.info("Querying converted sessions")
            converted_sessions = read_session.query(ToolUsage.session_id)\
                .filter(ToolUsage.tool_name == 'register', ToolUsage.session_id.in_(anon_sessions))\
                .distinct().count()
            logger.info("Queried converted_sessions: %d", converted_sessions)
            
            anon_total = read_session.query(anon_sessions).count()
            logger.info("Queried anon_total: %d", anon_total)
            conversion_rate = (converted_sessions / anon_total * 100) if anon_total else 0.0
            logger.info("Conversion rate: %.2f%%", conversion_rate)
            
            # Feedback
            logger.info("Querying average feedback rating")
            avg_feedback = read_session.query(func.avg(Feedback.rating)).scalar() or 0.0
            logger.info("Queried avg_feedback: %.2f", avg_feedback)
            
            # Data for charts (last 30 days)
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=30)
            logger.info("Querying daily usage for charts, from %s to %s", start_date, end_date)
            daily_usage = read_session.query(
                func.date(ToolUsage.created_at).label('date'),
                ToolUsage.tool_name,
                func.count(ToolUsage.id).label('count')
            )\
            .filter(ToolUsage.created_at >= start_date, ToolUsage.created_at <= end_date)\
            .group_by('date', ToolUsage.tool_name)\
            .order_by('date')\
            .all()
            logger.info("Queried daily_usage: %s", daily_usage)
            
            logger.info("Querying daily referrals for charts")
            daily_referrals = read_session.query(
                func.date(User.created_at).label('date'),
                func.count(User.id).label('count')
            )\
            .filter(
                User.referred_by_id.isnot(None),
                User.created_at >= start_date,
                User.created_at <= end_date
            )\
            .group_by('date')\
            .order_by('date')\
            .all()
            logger.info("Queried daily_referrals: %s", daily_referrals)
            
            # Initialize chart data
            logger.info("Initializing chart data structure")
            chart_data = {
                'labels': [],
                'registrations': [],
                'logins': [],
                'referrals': [],
                'tool_usage': {tool: [] for tool in VALID_TOOLS[3:]}
            }
            
            logger.info("Populating chart data for dates")
            current_date = start_date
            while current_date <= end_date:
                chart_data['labels'].append(current_date.strftime('%Y-%m-%d'))
                chart_data['registrations'].append(0)
                chart_data['logins'].append(0)
                chart_data['referrals'].append(0)
                for tool in chart_data['tool_usage']:
                    chart_data['tool_usage'][tool].append(0)
                current_date += timedelta(days=1)
            
            logger.info("Processing daily usage data")
            for date, tool_name, count in daily_usage:
                idx = (datetime.strptime(date, '%Y-%m-%d') - start_date).days
                if 0 <= idx < len(chart_data['labels']):
                    if tool_name == 'register':
                        chart_data['registrations'][idx] = count
                    elif tool_name == 'login':
                        chart_data['logins'][idx] = count
                    elif tool_name in chart_data['tool_usage']:
                        chart_data['tool_usage'][tool_name][idx] = count
            logger.info("Processed daily usage data")
            
            logger.info("Processing daily referrals data")
            for date, count in daily_referrals:
                idx = (datetime.strptime(date, '%Y-%m-%d') - start_date).days
                if 0 <= idx < len(chart_data['labels']):
                    chart_data['referrals'][idx] = count
            logger.info("Processed daily referrals data")
            
            # Prepare metrics
            logger.info("Preparing metrics dictionary")
            metrics = {
                'total_users': total_users,
                'new_users_last_24h': new_users_last_24h,
                'total_referrals': total_referrals,
                'new_referrals_last_24h': new_referrals_last_24h,
                'referral_conversion_rate': round(referral_conversion_rate, 2),
                'tool_usage_total': tool_usage_total,
                'top_tools': top_tools,
                'action_breakdown': action_breakdown,
                'multi_tool_ratio': round(multi_tool_ratio, 2),
                'conversion_rate': round(conversion_rate, 2),
                'avg_feedback_rating': round(avg_feedback, 2)
            }
            logger.info("Prepared metrics: %s", metrics)
            logger.info("Prepared chart_data: %s", chart_data)
        
        logger.info("Exiting no_autoflush context")
        logger.info("Rendering template")
        return render_template(
            'admin_dashboard.html',
            lang=lang,
            metrics=metrics,
            chart_data=chart_data,
            valid_tools=VALID_TOOLS[3:],
            tool_name=None,
            start_date=None,
            end_date=None
        )
    except exc.SQLAlchemyError as e:
        logger.error("Database error in overview: %s", str(e), exc_info=True, extra={'session_id': session_id})
        flash(trans('admin_error', default='A database error occurred while loading the dashboard.', lang=lang), 'danger')
        return render_template(
            'admin_dashboard.html',
            lang=lang,
            metrics={},
            chart_data={},
            valid_tools=VALID_TOOLS[3:],
            tool_name=None,
            start_date=None,
            end_date=None
        ), 500
    except Exception as e:
        logger.error("Unexpected error in overview: %s", str(e), exc_info=True, extra={'session_id': session_id})
        flash(trans('admin_error', default='An error occurred while loading the dashboard.', lang=lang), 'danger')
        return render_template(
            'admin_dashboard.html',
            lang=lang,
            metrics={},
            chart_data={},
            valid_tools=VALID_TOOLS[3:],
            tool_name=None,
            start_date=None,
            end_date=None
        ), 500

@admin_bp.route('/tool_usage', methods=['GET', 'POST'])
@login_required
@admin_required
def tool_usage():
    """Detailed tool usage analytics with filters."""
    lang = session.get('lang', 'en') if 'lang' in session else 'en'
    try:
        tool_name = request.args.get('tool_name')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        action = request.args.get('action')

        # Use read-only session for data retrieval
        with db.session.no_autoflush() as read_session:
            query = read_session.query(ToolUsage)
            if tool_name and tool_name in VALID_TOOLS[3:]:
                query = query.filter_by(tool_name=tool_name)
            if action:
                query = query.filter_by(action=action)
            if start_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                query = query.filter(ToolUsage.created_at >= start_date)
            else:
                start_date = None
            if end_date_str:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(ToolUsage.created_at < end_date)
            else:
                end_date = None

            usage_logs = query.order_by(ToolUsage.created_at.desc()).limit(100).all()

            # Available actions for the selected tool
            available_actions = read_session.query(ToolUsage.action)\
                .filter(ToolUsage.tool_name == tool_name if tool_name else True)\
                .distinct().all()
            available_actions = [a[0] for a in available_actions]

            # Chart data
            chart_data = {
                'labels': [],
                'usage_counts': {},
                'total_counts': []
            }
            if start_date and end_date:
                current_date = start_date
                while current_date < end_date:
                    date_str = current_date.strftime('%Y-%m-%d')
                    chart_data['labels'].append(date_str)
                    daily_query = query.filter(func.date(ToolUsage.created_at) == current_date.date())
                    total_count = daily_query.count()
                    chart_data['total_counts'].append(total_count)
                    if tool_name:
                        action_counts = read_session.query(ToolUsage.action, func.count(ToolUsage.id))\
                            .filter(
                                ToolUsage.tool_name == tool_name,
                                func.date(ToolUsage.created_at) == current_date.date()
                            )\
                            .group_by(ToolUsage.action).all()
                        for act, count in action_counts:
                            if act not in chart_data['usage_counts']:
                                chart_data['usage_counts'][act] = [0] * len(chart_data['labels'])
                            chart_data['usage_counts'].setdefault(act, [0] * len(chart_data['labels']))
                            chart_data['usage_counts'][act][-1] = count
                    current_date += timedelta(days=1)
            else:
                # Default to last 30 days
                end_date = datetime.utcnow()
                start_date = end_date - timedelta(days=30)
                daily_usage = read_session.query(
                    func.date(ToolUsage.created_at).label('date'),
                    ToolUsage.action,
                    func.count(ToolUsage.id).label('count')
                )\
                .filter(
                    ToolUsage.created_at >= start_date,
                    ToolUsage.created_at <= end_date,
                    ToolUsage.tool_name == (tool_name if tool_name else ToolUsage.tool_name)
                )\
                .group_by('date', ToolUsage.action)\
                .order_by('date')\
                .all()
                current_date = start_date
                idx = 0
                for date, action, count in daily_usage:
                    while current_date < datetime.strptime(date, '%Y-%m-%d'):
                        chart_data['labels'].append(current_date.strftime('%Y-%m-%d'))
                        chart_data['total_counts'].append(0)
                        for act in chart_data['usage_counts']:
                            if idx >= len(chart_data['usage_counts'].get(act, [])):
                                chart_data['usage_counts'].setdefault(act, [0] * (idx + 1))[-1] = 0
                        current_date += timedelta(days=1)
                        idx += 1
                    if current_date.strftime('%Y-%m-%d') == date:
                        chart_data['labels'].append(date)
                        if idx >= len(chart_data['total_counts']):
                            chart_data['total_counts'].append(0)
                        if action not in chart_data['usage_counts']:
                            chart_data['usage_counts'][action] = [0] * (idx + 1)
                        chart_data['usage_counts'][action][idx] = count
                        chart_data['total_counts'][idx] += count
                        current_date += timedelta(days=1)
                        idx += 1
                while current_date <= end_date:
                    chart_data['labels'].append(current_date.strftime('%Y-%m-%d'))
                    chart_data['total_counts'].append(0)
                    for act in chart_data['usage_counts']:
                        if idx >= len(chart_data['usage_counts'].get(act, [])):
                            chart_data['usage_counts'].setdefault(act, [0] * (idx + 1))[-1] = 0
                    current_date += timedelta(days=1)

        logger.info(
            f"Tool usage analytics accessed by {current_user.username}, tool={tool_name}, action={action}, start={start_date_str}, end={end_date_str}",
            extra={'session_id': session.get('sid', 'no-session-id')}
        )
        return render_template(
            'admin_dashboard.html',
            lang=lang,
            metrics=usage_logs,
            chart_data=chart_data,
            valid_tools=VALID_TOOLS[3:],
            tool_name=tool_name,
            start_date=start_date_str,
            end_date=end_date_str,
            action=action,
            available_actions=available_actions
        )
    except exc.SQLAlchemyError as e:
        logger.error(f"Database error in tool usage analytics: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans('admin_error', default='A database error occurred while loading analytics.', lang=lang), 'error')
        return render_template(
            'admin_dashboard.html',
            lang=lang,
            metrics=[],
            chart_data={},
            valid_tools=VALID_TOOLS[3:],
            tool_name=None,
            start_date=None,
            end_date=None,
            action=None,
            available_actions=[]
        ), 500
    except Exception as e:
        logger.error(f"Unexpected error in tool usage analytics: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans('admin_error', default='Error loading analytics.', lang=lang), 'error')
        return render_template(
            'admin_dashboard.html',
            lang=lang,
            metrics=[],
            chart_data={},
            valid_tools=VALID_TOOLS[3:],
            tool_name=None,
            start_date=None,
            end_date=None,
            action=None,
            available_actions=[]
        ), 500

@admin_bp.route('/export_csv', methods=['GET'])
@login_required
@admin_required
def export_csv():
    """Export filtered tool usage logs as CSV."""
    lang = session.get('lang', 'en') if 'lang' in session else 'en'
    try:
        tool_name = request.args.get('tool_name')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        action = request.args.get('action')

        # Use read-only session for data get
        with db.session.no_autoflush() as read_session:
            query = read_session.query(ToolUsage)
            if tool_name and tool_name in VALID_TOOLS[3:]:
                query = query.filter_by(tool_name=tool_name)
            if action:
                query = query.filter_by(action=action)
            if start_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                query = query.filter(ToolUsage.created_at >= start_date)
            if end_date_str:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(ToolUsage.created_at < end_date)

            usage_logs = query.all()

        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(['ID', 'User ID', 'Session ID', 'Tool Name', 'Action', 'Created At'])
        for log in usage_logs:
            cw.writerow([
                log.id,
                log.user_id or 'anonymous',
                log.session_id,
                log.tool_name,
                log.action,
                log.created_at.isoformat() if log.created_at else 'N/A'
            ])

        output = si.getvalue()
        si.close()

        logger.info(
            f"CSV export generated by {current_user.username}, tool={tool_name}, action={action}, start={start_date_str}, end={end_date_str}",
            extra={'session_id': session.get('sid', 'no-session-id')}
        )
        return Response(
            output,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=tool_usage_export.csv'}
        )
    except exc.SQLAlchemyError as e:
        logger.error(f"Database error in CSV export: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans('admin_export_error', default='A database error occurred while exporting CSV.', lang=lang), 'error')
        return redirect(url_for('admin.tool_usage'))
    except Exception as e:
        logger.error(f"Unexpected error in CSV export: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        flash(trans('admin_export_error', default='Error exporting CSV.', lang=lang), 'error')
        return redirect(url_for('admin.tool_usage'))
    finally:
        if 'si' in locals():
            si.close()
