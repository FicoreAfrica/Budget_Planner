from flask import Blueprint, render_template, session, request, redirect, url_for, flash
from translations import trans  # Import the global trans function
from json_store import JsonStorage  # Import JsonStorage
import logging
import os

# Set up logger with INFO level to reduce verbosity
logger = logging.getLogger('ficore_app')
logger.setLevel(logging.INFO)

learning_hub_bp = Blueprint('learning_hub', __name__)

# Initialize courses.json with default courses
courses_storage = JsonStorage('data/courses.json')
courses_data = {
    "budgeting_101": {
        "id": "budgeting_101",
        "title_en": "Budgeting 101",  # Direct English title for courses.json
        "title_ha": "Tsarin Kudi 101",
        "description_en": "Learn the basics of budgeting.",  # Added for courses.json
        "description_ha": "Koyon asalin tsarin kudi.",
        "title_key": "learning_hub_course_budgeting101_title",
        "desc_key": "learning_hub_course_budgeting101_desc",
        "modules": [
            {
                "id": "module-1",
                "title_key": "learning_hub_module_income_title",
                "lessons": [
                    {
                        "id": "budgeting_101-module-1-lesson-1",
                        "title_key": "learning_hub_lesson_income_sources_title",
                        "content_key": "learning_hub_lesson_income_sources_content",
                        "quiz_id": "quiz-1-1"
                    },
                    {
                        "id": "budgeting_101-module-1-lesson-2",
                        "title_key": "learning_hub_lesson_net_income_title",
                        "content_key": "learning_hub_lesson_net_income_content",
                        "quiz_id": None
                    }
                ]
            }
        ]
    },
    "financial_quiz": {
        "id": "financial_quiz",
        "title_en": "Financial Quiz",
        "title_ha": "Jarabawar Kudi",
        "description_en": "Test your financial knowledge.",
        "description_ha": "Gwada ilimin ku na kudi.",
        "title_key": "learning_hub_course_financial_quiz_title",
        "desc_key": "learning_hub_course_financial_quiz_desc",
        "modules": [
            {
                "id": "module-1",
                "title_key": "learning_hub_module_quiz_title",
                "lessons": [
                    {
                        "id": "financial_quiz-module-1-lesson-1",
                        "title_key": "learning_hub_lesson_quiz_intro_title",
                        "content_key": "learning_hub_lesson_quiz_intro_content",
                        "quiz_id": "quiz-financial-1"
                    }
                ]
            }
        ]
    },
    "savings_basics": {
        "id": "savings_basics",
        "title_en": "Savings Basics",
        "title_ha": "Asalin Tattara Kudi",
        "description_en": "Understand how to save effectively.",
        "description_ha": "Fahimci yadda ake tattara kudi yadda ya kamata.",
        "title_key": "learning_hub_course_savings_basics_title",
        "desc_key": "learning_hub_course_savings_basics_desc",
        "modules": [
            {
                "id": "module-1",
                "title_key": "learning_hub_module_savings_title",
                "lessons": [
                    {
                        "id": "savings_basics-module-1-lesson-1",
                        "title_key": "learning_hub_lesson_savings_strategies_title",
                        "content_key": "learning_hub_lesson_savings_strategies_content",
                        "quiz_id": None
                    }
                ]
            }
        ]
    }
}

quizzes_data = {
    "quiz-1-1": {
        "questions": [
            {
                "question_key": "learning_hub_quiz_income_q1",
                "options_keys": [
                    "learning_hub_quiz_income_opt_salary",
                    "learning_hub_quiz_income_opt_business",
                    "learning_hub_quiz_income_opt_investment",
                    "learning_hub_quiz_income_opt_other"
                ],
                "answer_key": "learning_hub_quiz_income_opt_salary"
            }
        ]
    },
    "quiz-financial-1": {
        "questions": [
            {
                "question_key": "learning_hub_quiz_financial_q1",
                "options_keys": [
                    "learning_hub_quiz_financial_opt_a",
                    "learning_hub_quiz_financial_opt_b",
                    "learning_hub_quiz_financial_opt_c",
                    "learning_hub_quiz_financial_opt_d"
                ],
                "answer_key": "learning_hub_quiz_financial_opt_a"
            }
        ]
    }
}

# Initialize courses.json if empty
def initialize_courses():
    """Initialize courses.json with default courses if empty."""
    try:
        courses = courses_storage.read_all()
        if not courses:
            logger.info("Courses storage is empty. Initializing with default courses.", extra={'session_id': 'no-request-context'})
            # Convert courses_data to list format for courses.json
            default_courses = [
                {
                    'id': course['id'],
                    'title_en': course['title_en'],
                    'title_ha': course['title_ha'],
                    'description_en': course['description_en'],
                    'description_ha': course['description_ha']
                } for course in courses_data.values()
            ]
            if not courses_storage.create(default_courses):
                logger.error("Failed to initialize courses.json with default courses", extra={'session_id': 'no-request-context'})
                raise RuntimeError("Course initialization failed")
            logger.info(f"Initialized courses.json with {len(default_courses)} default courses", extra={'session_id': 'no-request-context'})
    except Exception as e:
        logger.error(f"Error initializing courses: {str(e)}", extra={'session_id': 'no-request-context'})
        raise


def get_progress():
    try:
        return session.setdefault('learning_progress', {})
    except Exception as e:
        logger.error(f"Error accessing session['learning_progress']: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})
        return {}

def save_progress():
    try:
        session.modified = True
    except Exception as e:
        logger.error(f"Error saving session: {str(e)}", extra={'session_id': session.get('sid', 'no-session-id')})

def course_lookup(course_id):
    return courses_data.get(course_id)

def lesson_lookup(course, lesson_id):
    if not course or 'modules' not in course:
        return None, None
    for module in course['modules']:
        for lesson in module.get('lessons', []):
            if lesson.get('id') == lesson_id:
                return lesson, module
    return None, None

@learning_hub_bp.route('/courses')
def courses():
    progress = get_progress()
    return render_template('learning_hub_courses.html', courses=courses_data, progress=progress)

@learning_hub_bp.route('/courses/<course_id>')
def course_overview(course_id):
    course = course_lookup(course_id)
    if not course:
        flash(trans("learning_hub_course_not_found", default="Course not found"), "danger")
        return redirect(url_for('learning_hub.courses'))
    progress = get_progress().get(course_id, {})
    return render_template('learning_hub_course_overview.html', course=course, progress=progress)

@learning_hub_bp.route('/courses/<course_id>/lesson/<lesson_id>', methods=['GET', 'POST'])
def lesson(course_id, lesson_id):
    course = course_lookup(course_id)
    if not course:
        flash(trans("learning_hub_course_not_found", default="Course not found"), "danger")
        return redirect(url_for('learning_hub.courses'))
    lesson, module = lesson_lookup(course, lesson_id)
    if not lesson:
        flash(trans("learning_hub_lesson_not_found", default="Lesson not found"), "danger")
        return redirect(url_for('learning_hub.course_overview', course_id=course_id))

    progress = get_progress()
    course_progress = progress.setdefault(course_id, {'lessons_completed': [], 'quiz_scores': {}, 'current_lesson': lesson_id})
    if request.method == 'POST':
        if lesson_id not in course_progress['lessons_completed']:
            course_progress['lessons_completed'].append(lesson_id)
            course_progress['current_lesson'] = lesson_id
            save_progress()
            flash(trans("learning_hub_lesson_marked", default="Lesson marked as completed"), "success")
        # Next lesson navigation
        next_lesson_id = None
        found = False
        for m in course['modules']:
            for l in m['lessons']:
                if found and l.get('id'):
                    next_lesson_id = l['id']
                    break
                if l['id'] == lesson_id:
                    found = True
            if next_lesson_id:
                break
        if next_lesson_id:
            return redirect(url_for('learning_hub.lesson', course_id=course_id, lesson_id=next_lesson_id))
        else:
            flash(trans("learning_hub_lesson_done", default="Course completed"), "success")
            return redirect(url_for('learning_hub.course_overview', course_id=course_id))
    return render_template('learning_hub_lesson.html', course=course, lesson=lesson, module=module, progress=course_progress)

@learning_hub_bp.route('/courses/<course_id>/quiz/<quiz_id>', methods=['GET', 'POST'])
def quiz(course_id, quiz_id):
    course = course_lookup(course_id)
    if not course:
        flash(trans("learning_hub_course_not_found", default="Course not found"), "danger")
        return redirect(url_for('learning_hub.courses'))
    quiz = quizzes_data.get(quiz_id)
    if not quiz:
        flash(trans("learning_hub_quiz_not_found", default="Quiz not found"), "danger")
        return redirect(url_for('learning_hub.course_overview', course_id=course_id))
    progress = get_progress()
    course_progress = progress.setdefault(course_id, {'lessons_completed': [], 'quiz_scores': {}, 'current_lesson': None})

    if request.method == 'POST':
        answers = request.form.to_dict()
        score = 0
        for i, q in enumerate(quiz['questions']):
            user_answer = answers.get(f'q{i}')
            if user_answer and user_answer == trans(q['answer_key'], default=q['answer_key']):
                score += 1
        course_progress['quiz_scores'][quiz_id] = score
        save_progress()
        flash(f"{trans('learning_hub_quiz_completed', default='Quiz completed! Score:')} {score}/{len(quiz['questions'])}", "success")
        return redirect(url_for('learning_hub.course_overview', course_id=course_id))
    return render_template('learning_hub_quiz.html', course=course, quiz=quiz)

@learning_hub_bp.route('/dashboard')
def dashboard():
    progress = get_progress()
    progress_summary = []
    for course_id, course in courses_data.items():
        cp = progress.get(course_id, {})
        lessons_total = sum(len(m.get('lessons', [])) for m in course['modules'])
        completed = len(cp.get('lessons_completed', []))
        percent = int((completed / lessons_total) * 100) if lessons_total > 0 else 0
        progress_summary.append({'course': course, 'completed': completed, 'total': lessons_total, 'percent': percent})
    return render_template('learning_hub_dashboard.html', progress_summary=progress_summary)
