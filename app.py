import os
import uuid
import datetime
from flask import Flask, render_template, request, session, redirect, url_for, flash, Blueprint
from translations import get_translations
from storage import save_user_data, load_user_data, save_session_data, load_session_data
from sendgrid_email import send_email
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key')
app.config['SESSION_DIR'] = os.environ.get('SESSION_DIR', 'data/sessions')

# Ensure session directory exists
os.makedirs(app.config['SESSION_DIR'], exist_ok=True)

# Blueprints for each tool
health_score_bp = Blueprint('health_score', __name__, template_folder='templates')
budget_bp = Blueprint('budget', __name__, template_folder='templates')
quiz_bp = Blueprint('quiz', __name__, template_folder='templates')
bill_bp = Blueprint('bill', __name__, template_folder='templates')
net_worth_bp = Blueprint('net_worth', __name__, template_folder='templates')
emergency_fund_bp = Blueprint('emergency_fund', __name__, template_folder='templates')

# Session required decorator
def session_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            session['user_id'] = str(uuid.uuid4())
        return f(*args, **kwargs)
    return decorated_function

# General Routes
@app.route('/')
def index():
    t = get_translations(session.get('language', 'en'))
    return render_template('index.html', t=t)

@app.route('/set_language/<lang>')
def set_language(lang):
    t = get_translations('en')
    if lang in ['en', 'ha']:
        session['language'] = lang
        flash(t['Language changed successfully'])
    else:
        flash(t['Invalid language selected'])
    return redirect(request.referrer or url_for('index'))

@app.route('/general_dashboard')
@session_required
def general_dashboard():
    t = get_translations(session.get('language', 'en'))
    data = load_user_data(session['user_id'])
    return render_template('general_dashboard.html', t=t, data=data)

# Financial Health Score Routes
@health_score_bp.route('/step1', methods=['GET', 'POST'])
@session_required
def health_score_step1():
    t = get_translations(session.get('language', 'en'))
    if request.method == 'POST':
        data = {
            'first_name': request.form.get('first_name'),
            'last_name': request.form.get('last_name', ''),
            'email': request.form.get('email'),
            'confirm_email': request.form.get('confirm_email'),
            'phone': request.form.get('phone', ''),
            'send_email': request.form.get('send_email') == 'on'
        }
        if not data['first_name']:
            flash(t['First Name Required'])
        elif data['email'] != data['confirm_email']:
            flash(t['Email addresses must match.'])
        else:
            save_session_data(session['user_id'], 'health_score_step1', data)
            return redirect(url_for('health_score.step2'))
    return render_template('health_score_step1.html', t=t)

@health_score_bp.route('/step2', methods=['GET', 'POST'])
@session_required
def health_score_step2():
    t = get_translations(session.get('language', 'en'))
    if request.method == 'POST':
        data = {
            'business_name': request.form.get('business_name'),
            'user_type': request.form.get('user_type')
        }
        if not data['business_name']:
            flash(t['Business Name Required'])
        else:
            save_session_data(session['user_id'], 'health_score_step2', data)
            return redirect(url_for('health_score.step3'))
    return render_template('health_score_step2.html', t=t)

@health_score_bp.route('/step3', methods=['GET', 'POST'])
@session_required
def health_score_step3():
    t = get_translations(session.get('language', 'en'))
    if request.method == 'POST':
        try:
            data = {
                'income': float(request.form.get('income', 0)),
                'expenses': float(request.form.get('expenses', 0)),
                'debt': float(request.form.get('debt', 0)),
                'interest_rate': float(request.form.get('interest_rate', 0))
            }
            if max(data.values()) > 10_000_000_000:
                flash('Input cannot exceed ₦10 billion.')
            else:
                save_session_data(session['user_id'], 'health_score_step3', data)
                return redirect(url_for('health_score.dashboard'))
        except ValueError:
            flash(t['Invalid Number'])
    return render_template('health_score_step3.html', t=t)

@health_score_bp.route('/dashboard')
@session_required
def health_score_dashboard():
    t = get_translations(session.get('language', 'en'))
    step1 = load_session_data(session['user_id'], 'health_score_step1') or {}
    step2 = load_session_data(session['user_id'], 'health_score_step2') or {}
    step3 = load_session_data(session['user_id'], 'health_score_step3') or {}
    
    if not all([step1, step2, step3]):
        flash(t['Incomplete Data'])
        return redirect(url_for('health_score.step1'))
    
    # Calculate score (simplified logic)
    cash_flow = step3.get('income', 0) - step3.get('expenses', 0)
    debt_to_income = step3.get('debt', 0) / step3.get('income', 1) if step3.get('income', 0) else 0
    score = min(100, max(0, int(cash_flow / 1000 - debt_to_income * 100)))
    
    data = {
        'score': score,
        'cash_flow': cash_flow,
        'debt_to_income': debt_to_income,
        'interest_burden': step3.get('interest_rate', 0)
    }
    save_user_data(session['user_id'], 'health_score', data)
    
    if step1.get('send_email'):
        send_email(
            step1['email'],
            t['Score Report Subject'].format(user_name=step1['first_name']),
            render_template('health_score_email.html', t=t, data=data)
        )
    
    return render_template('health_score_dashboard.html', t=t, data=data)

# Budget Planner Routes
@budget_bp.route('/step1', methods=['GET', 'POST'])
@session_required
def budget_step1():
    t = get_translations(session.get('language', 'en'))
    if request.method == 'POST':
        data = {
            'first_name': request.form.get('first_name'),
            'email': request.form.get('email'),
            'language': request.form.get('language'),
            'send_email': request.form.get('send_email') == 'on'
        }
        if not data['first_name']:
            flash(t['First Name Required'])
        elif not data['email']:
            flash(t['Invalid Email'])
        elif not data['language']:
            flash(t['Language required'])
        else:
            save_session_data(session['user_id'], 'budget_step1', data)
            return redirect(url_for('budget.step2'))
    return render_template('budget_step1.html', t=t)

@budget_bp.route('/step2', methods=['GET', 'POST'])
@session_required
def budget_step2():
    t = get_translations(session.get('language', 'en'))
    if request.method == 'POST':
        try:
            data = {
                'income': float(request.form.get('income', 0))
            }
            if data['income'] > 10_000_000_000:
                flash('Input cannot exceed ₦10 billion.')
            else:
                save_session_data(session['user_id'], 'budget_step2', data)
                return redirect(url_for('budget.step3'))
        except ValueError:
            flash(t['Invalid Number'])
    return render_template('budget_step2.html', t=t)

@budget_bp.route('/step3', methods=['GET', 'POST'])
@session_required
def budget_step3():
    t = get_translations(session.get('language', 'en'))
    if request.method == 'POST':
        try:
            data = {
                'housing': float(request.form.get('housing', 0)),
                'food': float(request.form.get('food', 0)),
                'transport': float(request.form.get('transport', 0)),
                'other': float(request.form.get('other', 0))
            }
            if max(data.values()) > 10_000_000_000:
                flash('Input cannot exceed ₦10 billion.')
            else:
                save_session_data(session['user_id'], 'budget_step3', data)
                return redirect(url_for('budget.step4'))
        except ValueError:
            flash(t['Invalid Number'])
    return render_template('budget_step3.html', t=t)

@budget_bp.route('/step4', methods=['GET', 'POST'])
@session_required
def budget_step4():
    t = get_translations(session.get('language', 'en'))
    if request.method == 'POST':
        try:
            data = {
                'savings_goal': float(request.form.get('savings_goal', 0))
            }
            if data['savings_goal'] > 10_000_000_000:
                flash('Input cannot exceed ₦10 billion.')
            else:
                save_session_data(session['user_id'], 'budget_step4', data)
                return redirect(url_for('budget.dashboard'))
        except ValueError:
            flash(t['Invalid Number'])
    return render_template('budget_step4.html', t=t)

@budget_bp.route('/dashboard')
@session_required
def budget_dashboard():
    t = get_translations(session.get('language', 'en'))
    step1 = load_session_data(session['user_id'], 'budget_step1') or {}
    step2 = load_session_data(session['user_id'], 'budget_step2') or {}
    step3 = load_session_data(session['user_id'], 'budget_step3') or {}
    step4 = load_session_data(session['user_id'], 'budget_step4') or {}
    
    if not all([step1, step2, step3]):
        flash(t['Incomplete Data'])
        return redirect(url_for('budget.step1'))
    
    total_expenses = sum([step3.get(k, 0) for k in ['housing', 'food', 'transport', 'other']])
    surplus_deficit = step2.get('income', 0) - total_expenses - step4.get('savings_goal', 0)
    
    data = {
        'income': step2.get('income', 0),
        'expenses': total_expenses,
        'savings_goal': step4.get('savings_goal', 0),
        'surplus_deficit': surplus_deficit
    }
    save_user_data(session['user_id'], 'budget', data)
    
    if step1.get('send_email'):
        send_email(
            step1['email'],
            t['Budget Report Subject'],
            render_template('budget_email.html', t=t, data=data)
        )
    
    return render_template('budget_dashboard.html', t=t, data=data)

# Personality Quiz Routes
@quiz_bp.route('/step1', methods=['GET', 'POST'])
@session_required
def quiz_step1():
    t = get_translations(session.get('language', 'en'))
    questions = [
        'track_expenses', 'spend_non_essentials', 'save_regularly',
        'plan_expenses', 'impulse_purchases'
    ]
    if request.method == 'POST':
        data = {q: request.form.get(q) for q in questions}
        save_session_data(session['user_id'], 'quiz_step1', data)
        return redirect(url_for('quiz.step2'))
    return render_template('quiz_step1.html', t=t, questions=questions)

@quiz_bp.route('/step2', methods=['GET', 'POST'])
@session_required
def quiz_step2():
    t = get_translations(session.get('language', 'en'))
    questions = [
        'use_budgeting_tools', 'invest_money', 'emergency_fund',
        'set_financial_goals', 'seek_financial_advice'
    ]
    if request.method == 'POST':
        data = {q: request.form.get(q) for q in questions}
        save_session_data(session['user_id'], 'quiz_step2', data)
        return redirect(url_for('quiz.step3'))
    return render_template('quiz_step2.html', t=t, questions=questions)

@quiz_bp.route('/step3', methods=['GET', 'POST'])
@session_required
def quiz_step3():
    t = get_translations(session.get('language', 'en'))
    if request.method == 'POST':
        data = {
            'email': request.form.get('email'),
            'send_email': request.form.get('send_email') == 'on'
        }
        save_session_data(session['user_id'], 'quiz_step3', data)
        return redirect(url_for('quiz.results'))
    return render_template('quiz_step3.html', t=t)

@quiz_bp.route('/results')
@session_required
def quiz_results():
    t = get_translations(session.get('language', 'en'))
    step1 = load_session_data(session['user_id'], 'quiz_step1') or {}
    step2 = load_session_data(session['user_id'], 'quiz_step2') or {}
    step3 = load_session_data(session['user_id'], 'quiz_step3') or {}
    
    if not all([step1, step2]):
        flash(t['Incomplete Data'])
        return redirect(url_for('quiz.step1'))
    
    # Simplified scoring logic
    score = sum(1 for v in list(step1.values()) + list(step2.values()) if v in ['yes', 'always'])
    personality = 'Planner' if score >= 8 else 'Saver' if score >= 6 else 'Minimalist' if score >= 4 else 'Spender' if score >= 2 else 'Avoider'
    
    data = {'personality': personality, 'score': score}
    save_user_data(session['user_id'], 'quiz', data)
    
    if step3.get('send_email'):
        send_email(
            step3['email'],
            t['Quiz Report Subject'],
            render_template('quiz_email.html', t=t, data=data)
        )
    
    return render_template('quiz_results.html', t=t, data=data)

# Bill Planner Routes
@bill_bp.route('/form', methods=['GET', 'POST'])
@session_required
def bill_form():
    t = get_translations(session.get('language', 'en'))
    if request.method == 'POST':
        try:
            data = {
                'description': request.form.get('description'),
                'amount': float(request.form.get('amount', 0)),
                'due_date': request.form.get('due_date'),
                'category': request.form.get('category'),
                'frequency': request.form.get('frequency'),
                'reminder': request.form.get('reminder'),
                'status': 'Unpaid'
            }
            if data['amount'] > 10_000_000_000:
                flash('Input cannot exceed ₦10 billion.')
            else:
                due_date = datetime.datetime.strptime(data['due_date'], '%Y-%m-%d')
                if due_date.date() < datetime.date.today():
                    flash(t['Due date must be today or in the future'])
                else:
                    bills = load_user_data(session['user_id']).get('bills', [])
                    bills.append(data)
                    save_user_data(session['user_id'], 'bills', bills)
                    if data['reminder']:
                        send_email(
                            session.get('email', 'user@example.com'),
                            t['Bill Reminder'],
                            render_template('bill_reminder.html', t=t, bill=data)
                        )
                    return redirect(url_for('bill.dashboard'))
        except ValueError:
            flash(t['Invalid Number'])
    return render_template('bill_form.html', t=t)

@bill_bp.route('/dashboard')
@session_required
def bill_dashboard():
    t = get_translations(session.get('language', 'en'))
    bills = load_user_data(session['user_id']).get('bills', [])
    return render_template('bill_dashboard.html', t=t, bills=bills)

@bill_bp.route('/view_edit_bills')
@session_required
def view_edit_bills():
    t = get_translations(session.get('language', 'en'))
    bills = load_user_data(session['user_id']).get('bills', [])
    return render_template('view_edit_bills.html', t=t, bills=bills)

@bill_bp.route('/toggle_status/<int:index>')
@session_required
def toggle_status(index):
    t = get_translations(session.get('language', 'en'))
    bills = load_user_data(session['user_id']).get('bills', [])
    if 0 <= index < len(bills):
        bills[index]['status'] = 'Paid' if bills[index]['status'] == 'Unpaid' else 'Unpaid'
        save_user_data(session['user_id'], 'bills', bills)
    return redirect(url_for('bill.view_edit_bills'))

@bill_bp.route('/delete/<int:index>')
@session_required
def delete_bill(index):
    t = get_translations(session.get('language', 'en'))
    bills = load_user_data(session['user_id']).get('bills', [])
    if 0 <= index < len(bills):
        bills.pop(index)
        save_user_data(session['user_id'], 'bills', bills)
        flash(t['Bill Deleted'])
    return redirect(url_for('bill.view_edit_bills'))

# Net Worth Calculator Routes
@net_worth_bp.route('/step1', methods=['GET', 'POST'])
@session_required
def net_worth_step1():
    t = get_translations(session.get('language', 'en'))
    if request.method == 'POST':
        data = {
            'first_name': request.form.get('first_name'),
            'email': request.form.get('email'),
            'send_email': request.form.get('send_email') == 'on'
        }
        if not data['first_name']:
            flash(t['First Name Required'])
        elif not data['email']:
            flash(t['Invalid Email'])
        else:
            save_session_data(session['user_id'], 'net_worth_step1', data)
            return redirect(url_for('net_worth.step2'))
    return render_template('net_worth_step1.html', t=t)

@net_worth_bp.route('/step2', methods=['GET', 'POST'])
@session_required
def net_worth_step2():
    t = get_translations(session.get('language', 'en'))
    if request.method == 'POST':
        try:
            data = {
                'cash': float(request.form.get('cash', 0)),
                'investments': float(request.form.get('investments', 0)),
                'real_estate': float(request.form.get('real_estate', 0)),
                'vehicles': float(request.form.get('vehicles', 0)),
                'business': float(request.form.get('business', 0)),
                'other_assets': float(request.form.get('other_assets', 0)),
                'credit_card': float(request.form.get('credit_card', 0)),
                'loans': float(request.form.get('loans', 0)),
                'bills': float(request.form.get('bills', 0)),
                'other_debts': float(request.form.get('other_debts', 0))
            }
            if max(data.values()) > 10_000_000_000:
                flash('Input cannot exceed ₦10 billion.')
            else:
                save_session_data(session['user_id'], 'net_worth_step2', data)
                return redirect(url_for('net_worth.dashboard'))
        except ValueError:
            flash(t['Invalid Number'])
    return render_template('net_worth_step2.html', t=t)

@net_worth_bp.route('/dashboard')
@session_required
def net_worth_dashboard():
    t = get_translations(session.get('language', 'en'))
    step1 = load_session_data(session['user_id'], 'net_worth_step1') or {}
    step2 = load_session_data(session['user_id'], 'net_worth_step2') or {}
    
    if not all([step1, step2]):
        flash(t['Incomplete Data'])
        return redirect(url_for('net_worth.step1'))
    
    total_assets = sum([step2.get(k, 0) for k in ['cash', 'investments', 'real_estate', 'vehicles', 'business', 'other_assets']])
    total_liabilities = sum([step2.get(k, 0) for k in ['credit_card', 'loans', 'bills', 'other_debts']])
    net_worth = total_assets - total_liabilities
    
    data = {
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'net_worth': net_worth
    }
    save_user_data(session['user_id'], 'net_worth', data)
    
    if step1.get('send_email'):
        send_email(
            step1['email'],
            t['Net Worth Calculator'],
            render_template('net_worth_email.html', t=t, data=data)
        )
    
    return render_template('net_worth_dashboard.html', t=t, data=data)

# Emergency Fund Calculator Routes
@emergency_fund_bp.route('/step1', methods=['GET', 'POST'])
@session_required
def emergency_fund_step1():
    t = get_translations(session.get('language', 'en'))
    if request.method == 'POST':
        data = {
            'first_name': request.form.get('first_name'),
            'email': request.form.get('email'),
            'send_email': request.form.get('send_email') == 'on'
        }
        if not data['first_name']:
            flash(t['First Name Required'])
        elif not data['email']:
            flash(t['Invalid Email'])
        else:
            save_session_data(session['user_id'], 'emergency_fund_step1', data)
            return redirect(url_for('emergency_fund.step2'))
    return render_template('emergency_fund_step1.html', t=t)

@emergency_fund_bp.route('/step2', methods=['GET', 'POST'])
@session_required
def emergency_fund_step2():
    t = get_translations(session.get('language', 'en'))
    if request.method == 'POST':
        try:
            data = {
                'monthly_expenses': float(request.form.get('monthly_expenses', 0)),
                'monthly_income': float(request.form.get('monthly_income', 0)),
                'current_savings': float(request.form.get('current_savings', 0)),
                'risk_level': request.form.get('risk_level'),
                'dependents': int(request.form.get('dependents', 0)),
                'timeline': request.form.get('timeline')
            }
            if max([data['monthly_expenses'], data['monthly_income'], data['current_savings']]) > 10_000_000_000:
                flash('Input cannot exceed ₦10 billion.')
            else:
                save_session_data(session['user_id'], 'emergency_fund_step2', data)
                return redirect(url_for('emergency_fund.dashboard'))
        except ValueError:
            flash(t['Invalid Number'])
    return render_template('emergency_fund_step2.html', t=t)

@emergency_fund_bp.route('/dashboard')
@session_required
def emergency_fund_dashboard():
    t = get_translations(session.get('language', 'en'))
    step1 = load_session_data(session['user_id'], 'emergency_fund_step1') or {}
    step2 = load_session_data(session['user_id'], 'emergency_fund_step2') or {}
    
    if not all([step1, step2]):
        flash(t['Incomplete Data'])
        return redirect(url_for('emergency_fund.step1'))
    
    months = {'6 Months': 6, '12 Months': 12, '18 Months': 18}
    risk_factor = {'Low': 3, 'Medium': 6, 'High': 9}
    target_fund = step2['monthly_expenses'] * risk_factor[step2['risk_level']] * (1 + step2['dependents'] * 0.1)
    savings_gap = max(0, target_fund - step2['current_savings'])
    monthly_savings = savings_gap / months[step2['timeline']] if savings_gap > 0 else 0
    
    data = {
        'target_fund': target_fund,
        'savings_gap': savings_gap,
        'monthly_savings': monthly_savings
    }
    save_user_data(session['user_id'], 'emergency_fund', data)
    
    if step1.get('send_email'):
        send_email(
            step1['email'],
            t['Emergency Fund Calculator'],
            render_template('emergency_fund_email.html', t=t, data=data)
        )
    
    return render_template('emergency_fund_dashboard.html', t=t, data=data)

# Error Handlers
@app.errorhandler(404)
def page_not_found(e):
    t = get_translations(session.get('language', 'en'))
    return render_template('404.html', t=t), 404

@app.errorhandler(500)
def internal_server_error(e):
    t = get_translations(session.get('language', 'en'))
    return render_template('500.html', t=t), 500

# Register Blueprints
app.register_blueprint(health_score_bp, url_prefix='/health_score')
app.register_blueprint(budget_bp, url_prefix='/budget')
app.register_blueprint(quiz_bp, url_prefix='/quiz')
app.register_blueprint(bill_bp, url_prefix='/bill')
app.register_blueprint(net_worth_bp, url_prefix='/net_worth')
app.register_blueprint(emergency_fund_bp, url_prefix='/emergency_fund')

if __name__ == '__main__':
    app.run(debug=True)
