from flask import Blueprint, render_template, session, current_app, redirect, url_for, request, flash
from json_store import JsonStorage
import os
from datetime import datetime
import pandas as pd
try:
    from app import trans  # Import trans from app.py instead
except ImportError:
    def trans(key, lang=None):
        return key  # Fallback to return the key as the translation
        
courses_bp = Blueprint('courses', __name__, url_prefix='/courses')

COURSES_FILE = os.path.join('data', 'courses.json')
PROGRESS_FILE = os.path.join('data', 'user_progress.json')

SAMPLE_COURSES = [
    {
        'id': 'budgeting_101',
        'title_en': trans('course_budgeting_101_title_en'),
        'title_ha': trans('course_budgeting_101_title_ha'),
        'is_premium': False,
        'lessons': [
            {'title_en': trans('lesson_intro_budgeting_en'), 'title_ha': trans('lesson_intro_budgeting_ha'), 'content_en': trans('lesson_intro_budgeting_content_en'), 'content_ha': trans('lesson_intro_budgeting_content_ha')},
            {'title_en': trans('lesson_create_budget_en'), 'title_ha': trans('lesson_create_budget_ha'), 'content_en': trans('lesson_create_budget_content_en'), 'content_ha': trans('lesson_create_budget_content_ha')}
        ]
    },
    {
        'id': 'financial_quiz',
        'title_en': trans('course_financial_quiz_title_en'),
        'title_ha': trans('course_financial_quiz_title_ha'),
        'is_premium': False,
        'lessons': [
            {'title_en': trans('lesson_personal_info_en'), 'title_ha': trans('lesson_personal_info_ha'), 'content_en': trans('lesson_personal_info_content_en'), 'content_ha': trans('lesson_personal_info_content_ha')},
            {'title_en': trans('lesson_answer_questions_en'), 'title_ha': trans('lesson_answer_questions_ha'), 'content_en': trans('lesson_answer_questions_content_en'), 'content_ha': trans('lesson_answer_questions_content_ha')},
            {'title_en': trans('lesson_view_results_en'), 'title_ha': trans('lesson_view_results_ha'), 'content_en': trans('lesson_view_results_content_en'), 'content_ha': trans('lesson_view_results_content_ha')}
        ]
    }
]

def initialize_courses():
    courses_storage = current_app.config['STORAGE_MANAGERS']['courses']
    existing_courses = [record['data'] for record in courses_storage.read_all()]
    if not existing_courses:
        for course in SAMPLE_COURSES:
            courses_storage.append(course)
        current_app.logger.info("Initialized sample courses in courses.json")

@courses_bp.route('/')
def course_catalog():
    courses_storage = current_app.config['STORAGE_MANAGERS']['courses']
    initialize_courses()
    courses = courses_storage.read_all()
    lang = session.get('lang', 'en')
    user_progress = []
    if 'sid' in session:
        progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
        user_progress = progress_storage.filter_by_session(session['sid'])
    return render_template('courses.html', courses=courses, trans=trans, lang=lang, user_progress=user_progress)

@courses_bp.route('/<course_id>')
def course_page(course_id):
    courses_storage = current_app.config['STORAGE_MANAGERS']['courses']
    progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
    courses = courses_storage.read_all()
    course = next((c for c in courses if c['id'] == course_id), None)
    lang = session.get('lang', 'en')
    if not course:
        flash(trans("course_not_found", lang=lang), "danger")
        return render_template('404.html', trans=trans, lang=lang), 404

    if course_id == 'financial_quiz':
        return redirect(url_for('quiz.step1', course_id=course_id))

    if 'sid' in session:
        progress = progress_storage.filter_by_session(session['sid'])
        course_progress = next((p['data'] for p in progress if p['data']['course_id'] == course_id), None)
        if not course_progress:
            progress_data = {
                'course_id': course_id,
                'completed_lessons': [],
                'progress_percentage': 0,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            progress_storage.append(progress_data, session_id=session['sid'])
            current_app.logger.info(f"Initialized progress for course {course_id} for session {session['sid']}")
            sync_progress_to_sheets(session['sid'])

    return render_template('course_lesson.html', course=course, trans=trans, lang=lang)

@courses_bp.route('/complete_lesson/<course_id>/<int:lesson_index>', methods=['POST'])
def complete_lesson(course_id, lesson_index):
    if 'sid' not in session:
        flash(trans('login_to_track_progress', lang=session.get('lang', 'en')), 'danger')
        return redirect(url_for('index'))

    progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
    courses_storage = current_app.config['STORAGE_MANAGERS']['courses']
    courses = courses_storage.read_all()
    course = next((c for c in courses if c['id'] == course_id), None)
    lang = session.get('lang', 'en')
    if not course or lesson_index >= len(course['lessons']):
        flash(trans("course_not_found", lang=lang), "danger")
        return render_template('404.html', trans=trans, lang=lang), 404
    
    progress = progress_storage.filter_by_session(session['sid'])
    course_progress = next((p for p in progress if p['data']['course_id'] == course_id), None)
    if not course_progress:
        progress_data = {
            'course_id': course_id,
            'completed_lessons': [lesson_index],
            'progress_percentage': (1 / len(course['lessons'])) * 100,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        progress_storage.append(progress_data, session_id=session['sid'])
    else:
        completed_lessons = course_progress['data']['completed_lessons']
        if lesson_index not in completed_lessons:
            completed_lessons.append(lesson_index)
            course_progress['data']['completed_lessons'] = completed_lessons
            course_progress['data']['progress_percentage'] = (len(completed_lessons) / len(course['lessons'])) * 100
            course_progress['data']['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            progress_storage.update_by_id(course_progress['id'], course_progress['data'])

    current_app.logger.info(f"Lesson {lesson_index} completed for course {course_id} by session {session['sid']}")
    sync_progress_to_sheets(session['sid'])
    flash(trans('lesson_completed_success', lang=lang), 'success')
    return redirect(url_for('courses.course_page', course_id=course_id))

@courses_bp.route('/complete_quiz/<course_id>', methods=['POST'])
def complete_quiz(course_id):
    if 'sid' not in session:
        flash(trans('login_to_track_progress', lang=session.get('lang', 'en')), 'danger')
        return redirect(url_for('index'))

    lang = session.get('lang', 'en')
    if course_id != 'financial_quiz':
        flash(trans('invalid_course_id', lang=lang), 'danger')
        return redirect(url_for('courses.course_catalog'))

    progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
    progress = progress_storage.filter_by_session(session['sid'])
    course_progress = next((p for p in progress if p['data']['course_id'] == course_id), None)
    if not course_progress:
        progress_data = {
            'course_id': course_id,
            'completed_lessons': [0, 1, 2],  # All quiz lessons
            'progress_percentage': 100,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        progress_storage.append(progress_data, session_id=session['sid'])
    else:
        course_progress['data']['completed_lessons'] = [0, 1, 2]
        course_progress['data']['progress_percentage'] = 100
        course_progress['data']['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        progress_storage.update_by_id(course_progress['id'], course_progress['data'])

    current_app.logger.info(f"Quiz course {course_id} completed by session {session['sid']}")
    sync_progress_to_sheets(session['sid'])
    flash(trans('quiz_completed_success', lang=lang), 'success')
    return redirect(url_for('courses.course_catalog'))

def sync_progress_to_sheets(session_id):
    gspread_client = current_app.config['GSPREAD_CLIENT']
    progress_storage = current_app.config['STORAGE_MANAGERS']['user_progress']
    if not gspread_client:
        current_app.logger.error("Cannot sync to Google Sheets: gspread client not initialized")
        return

    try:
        progress_records = progress_storage.filter_by_session(session_id)
        data = [{
            'session_id': record['session_id'],
            'course_id': record['data']['course_id'],
            'completed_lessons': len(record['data']['completed_lessons']),
            'progress_percentage': record['data']['progress_percentage'],
            'last_updated': record['data']['last_updated']
        } for record in progress_records]

        df = pd.DataFrame(data)
        if df.empty:
            current_app.logger.info(f"No progress data to sync for session {session_id}")
            return

        spreadsheet = gspread_client.open('FicoreProgress')
        try:
            worksheet = spreadsheet.worksheet('UserProgress')
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title='UserProgress', rows=100, cols=5)
            worksheet.append_row(['session_id', 'course_id', 'completed_lessons', 'progress_percentage', 'last_updated'])

        worksheet.clear()
        worksheet.append_row(['session_id', 'course_id', 'completed_lessons', 'progress_percentage', 'last_updated'])
        for _, row in df.iterrows():
            worksheet.append_row([
                row['session_id'],
                row['course_id'],
                row['completed_lessons'],
                row['progress_percentage'],
                row['last_updated']
            ])
        current_app.logger.info(f"Synced progress for session {session_id} to Google Sheets")
    except Exception as e:
        current_app.logger.error(f"Failed to sync progress to Google Sheets: {str(e)}", exc_info=True)
