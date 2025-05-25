from flask import Blueprint, render_template, session, request, redirect, url_for, flash
try:
    from app import trans  # Import trans from app.py instead
except ImportError:
    def trans(key, lang=None):
        return key  # Fallback to return the key as the translation

learning_hub_bp = Blueprint('learning_hub', __name__)

def trans(key):
    lang = session.get("lang", "en")
    return LEARNING_HUB_TRANSLATIONS.get(lang, {}).get(key, key)

courses_data = {
    "budgeting-101": {
        "id": "budgeting-101",
        "title_key": "learninghub_course_budgeting101_title",
        "desc_key": "learninghub_course_budgeting101_desc",
        "modules": [
            {
                "id": "module-1",
                "title_key": "learninghub_module_income_title",
                "lessons": [
                    {
                        "id": "budgeting-101-module-1-lesson-1",
                        "title_key": "learninghub_lesson_income_sources_title",
                        "content_key": "learninghub_lesson_income_sources_content",
                        "quiz_id": "quiz-1-1"
                    },
                    {
                        "id": "budgeting-101-module-1-lesson-2",
                        "title_key": "learninghub_lesson_net_income_title",
                        "content_key": "learninghub_lesson_net_income_content",
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
                "question_key": "learninghub_quiz_income_q1",
                "options_keys": [
                    "learninghub_quiz_income_opt_salary",
                    "learninghub_quiz_income_opt_business",
                    "learninghub_quiz_income_opt_investment",
                    "learninghub_quiz_income_opt_other"
                ],
                "answer_key": "learninghub_quiz_income_opt_salary"
            }
        ]
    }
}

def get_progress():
    return session.setdefault('learning_progress', {})

def save_progress():
    session.modified = True

def course_lookup(course_id):
    return courses_data.get(course_id)

def lesson_lookup(course, lesson_id):
    for module in course['modules']:
        for lesson in module['lessons']:
            if lesson['id'] == lesson_id:
                return lesson, module
    return None, None

@learning_hub_bp.route('/courses')
def courses():
    progress = get_progress()
    return render_template('courses.html', courses=courses_data, progress=progress, trans=trans)

@learning_hub_bp.route('/courses/<course_id>')
def course_overview(course_id):
    course = course_lookup(course_id)
    if not course:
        flash(trans("learninghub_course_not_found"), "danger")
        return redirect(url_for('learning_hub.courses'))
    progress = get_progress().get(course_id, {})
    return render_template('course_overview.html', course=course, progress=progress, trans=trans)

@learning_hub_bp.route('/courses/<course_id>/lesson/<lesson_id>', methods=['GET', 'POST'])
def lesson(course_id, lesson_id):
    course = course_lookup(course_id)
    if not course:
        flash(trans("learninghub_course_not_found"), "danger")
        return redirect(url_for('learning_hub.courses'))
    lesson, module = lesson_lookup(course, lesson_id)
    if not lesson:
        flash(trans("learninghub_lesson_not_found"), "danger")
        return redirect(url_for('learning_hub.course_overview', course_id=course_id))

    progress = get_progress()
    course_progress = progress.setdefault(course_id, {'lessons_completed': [], 'quiz_scores': {}, 'current_lesson': lesson_id})
    if request.method == 'POST':
        if lesson_id not in course_progress['lessons_completed']:
            course_progress['lessons_completed'].append(lesson_id)
            course_progress['current_lesson'] = lesson_id
            save_progress()
            flash(trans("learninghub_lesson_marked"), "success")
        # Next lesson navigation
        next_lesson_id = None
        found = False
        for m in course['modules']:
            for l in m['lessons']:
                if found:
                    next_lesson_id = l['id']
                    break
                if l['id'] == lesson_id:
                    found = True
            if next_lesson_id:
                break
        if next_lesson_id:
            return redirect(url_for('learning_hub.lesson', course_id=course_id, lesson_id=next_lesson_id))
        else:
            flash(trans("learninghub_lesson_done"), "success")
            return redirect(url_for('learning_hub.course_overview', course_id=course_id))
    return render_template('lesson.html', course=course, lesson=lesson, module=module, progress=course_progress, trans=trans)

@learning_hub_bp.route('/courses/<course_id>/quiz/<quiz_id>', methods=['GET', 'POST'])
def quiz(course_id, quiz_id):
    course = course_lookup(course_id)
    if not course:
        flash(trans("learninghub_course_not_found"), "danger")
        return redirect(url_for('learning_hub.courses'))
    quiz = quizzes_data.get(quiz_id)
    if not quiz:
        flash(trans("learninghub_quiz_not_found"), "danger")
        return redirect(url_for('learning_hub.course_overview', course_id=course_id))
    progress = get_progress()
    course_progress = progress.setdefault(course_id, {'lessons_completed': [], 'quiz_scores': {}, 'current_lesson': None})

    if request.method == 'POST':
        answers = request.form
        score = 0
        for i, q in enumerate(quiz['questions']):
            user_answer = answers.get(f'q{i}')
            if user_answer and user_answer == trans(q['answer_key']):
                score += 1
        course_progress['quiz_scores'][quiz_id] = score
        save_progress()
        flash(f"{trans('learninghub_quiz_completed')} {score}/{len(quiz['questions'])}", "success")
        return redirect(url_for('learning_hub.course_overview', course_id=course_id))
    return render_template('quiz.html', course=course, quiz=quiz, trans=trans)

@learning_hub_bp.route('/dashboard')
def dashboard():
    progress = get_progress()
    progress_summary = []
    for course_id, course in courses_data.items():
        cp = progress.get(course_id, {})
        lessons_total = sum(len(m['lessons']) for m in course['modules'])
        completed = len(cp.get('lessons_completed', []))
        percent = int((completed / lessons_total) * 100) if lessons_total > 0 else 0
        progress_summary.append({'course': course, 'completed': completed, 'total': lessons_total, 'percent': percent})
    return render_template('dashboard.html', progress_summary=progress_summary, trans=trans)
