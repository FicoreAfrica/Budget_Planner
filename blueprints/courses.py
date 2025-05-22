from flask import Blueprint, render_template, session, current_app, redirect, url_for
from json_store import JsonStorage
import os
from datetime import datetime

courses_bp = Blueprint('courses', __name__, url_prefix='/courses')

# Initialize JsonStorage for courses and user progress
COURSES_FILE = os.path.join('data', 'courses.json')
PROGRESS_FILE = os.path.join('data', 'user_progress.json')
courses_storage = JsonStorage(COURSES_FILE, logger_instance=current_app.logger)
progress_storage = JsonStorage(PROGRESS_FILE, logger_instance=current_app.logger)

@courses_bp.route('/')
def course_catalog():
    """Display the course catalog."""
    courses = courses_storage.read_all()
    lang = session.get('lang', 'en')
    # Get user progress if session ID exists
    user_progress = []
    if 'sid' in session:
        user_progress = progress_storage.filter_by_session(session['sid'])
    return render_template('courses.html', courses=courses, lang=lang, user_progress=user_progress)

@courses_bp.route('/<course_id>')
def course_page(course_id):
    """Display an individual course page and update progress."""
    courses = courses_storage.read_all()
    course = next((c for c in courses if c['id'] == course_id), None)
    if not course:
        return render_template('404.html'), 404

    # Update progress if user has a session
    if 'sid' in session:
        progress = progress_storage.filter_by_session(session['sid'])
        course_progress = next((p for p in progress if p['course_id'] == course_id), None)
        if not course_progress:
            # Initialize progress for this course
            progress_data = {
                'course_id': course_id,
                'completed_lessons': [],
                'progress_percentage': 0,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            progress_storage.append(progress_data, session_id=session['sid'])
            current_app.logger.info(f"Initialized progress for course {course_id} for session {session['sid']}")
        # Note: Lesson completion logic can be added later with a POST route

    lang = session.get('lang', 'en')
    return render_template('course_lesson.html', course=course, lang=lang)