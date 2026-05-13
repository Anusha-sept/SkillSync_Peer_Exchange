from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models import User, Skill, Session, Notification, Certificate, AdminLog

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    stats = {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'total_sessions': Session.query.count(),
        'completed_sessions': Session.query.filter_by(status='completed').count(),
        'total_credits': db.session.query(db.func.sum(User.credits)).scalar() or 0,
        'total_credits_earned': db.session.query(db.func.sum(User.total_credits_earned)).scalar() or 0,
        'total_skills': Skill.query.count(),
        'pending_sessions': Session.query.filter_by(status='pending').count()
    }
    
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_sessions = Session.query.order_by(Session.created_at.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html', stats=stats, recent_users=recent_users, recent_sessions=recent_sessions)


@admin_bp.route('/users')
@login_required
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    users = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('admin/users.html', users=users)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.first_name = request.form.get('first_name')
        user.last_name = request.form.get('last_name')
        user.email = request.form.get('email')
        user.username = request.form.get('username')
        user.credits = int(request.form.get('credits', 0))
        user.is_active = 'is_active' in request.form
        user.is_admin = 'is_admin' in request.form
        
        db.session.commit()
        
        log = AdminLog(admin_id=current_user.id, action=f'Updated user {user.username}', details=f'Changed credits to {user.credits}')
        db.session.add(log)
        db.session.commit()
        
        flash(f'User {user.username} updated successfully!', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('admin/edit_user.html', user=user)


@admin_bp.route('/users/<int:user_id>/delete')
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('You cannot delete your own account!', 'danger')
        return redirect(url_for('admin.users'))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    log = AdminLog(admin_id=current_user.id, action=f'Deleted user {username}', details='User account deleted')
    db.session.add(log)
    db.session.commit()
    
    flash(f'User {username} has been deleted.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/sessions')
@login_required
@admin_required
def sessions():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    status = request.args.get('status')
    
    query = Session.query
    if status:
        query = query.filter_by(status=status)
    
    sessions = query.order_by(Session.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('admin/sessions.html', sessions=sessions, current_status=status)


@admin_bp.route('/sessions/<int:session_id>')
@login_required
@admin_required
def view_session(session_id):
    session = Session.query.get_or_404(session_id)
    return render_template('admin/view_session.html', session=session)


@admin_bp.route('/skills', methods=['GET', 'POST'])
@login_required
@admin_required
def skills():
    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category')
        description = request.form.get('description')
        
        existing = Skill.query.filter_by(name=name).first()
        if existing:
            flash('Skill already exists!', 'warning')
            return redirect(url_for('admin.skills'))
        
        skill = Skill(name=name, category=category, description=description)
        db.session.add(skill)
        db.session.commit()
        
        flash(f'Skill "{name}" created!', 'success')
        return redirect(url_for('admin.skills'))
    
    skills = Skill.query.order_by(Skill.name).all()
    categories = db.session.query(Skill.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    return render_template('admin/skills.html', skills=skills, categories=categories)


@admin_bp.route('/skills/<int:skill_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_skill(skill_id):
    skill = Skill.query.get_or_404(skill_id)
    
    skill.name = request.form.get('name')
    skill.category = request.form.get('category')
    skill.description = request.form.get('description')
    
    db.session.commit()
    flash(f'Skill "{skill.name}" updated!', 'success')
    return redirect(url_for('admin.skills'))


@admin_bp.route('/skills/<int:skill_id>/delete')
@login_required
@admin_required
def delete_skill(skill_id):
    skill = Skill.query.get_or_404(skill_id)
    name = skill.name
    db.session.delete(skill)
    db.session.commit()
    
    flash(f'Skill "{name}" deleted!', 'success')
    return redirect(url_for('admin.skills'))


@admin_bp.route('/certificates')
@login_required
@admin_required
def certificates():
    certificates = Certificate.query.order_by(Certificate.issued_at.desc()).all()
    return render_template('admin/certificates.html', certificates=certificates)


@admin_bp.route('/logs')
@login_required
@admin_required
def logs():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    logs = AdminLog.query.order_by(AdminLog.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('admin/logs.html', logs=logs)


@admin_bp.route('/analytics')
@login_required
@admin_required
def analytics():
    from datetime import datetime, timedelta
    
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)
    
    sessions_last_30_days = Session.query.filter(Session.created_at >= thirty_days_ago).count()
    sessions_last_7_days = Session.query.filter(Session.created_at >= seven_days_ago).count()
    
    new_users_last_30 = User.query.filter(User.created_at >= thirty_days_ago).count()
    new_users_last_7 = User.query.filter(User.created_at >= seven_days_ago).count()
    
    avg_rating = db.session.query(db.func.avg(User.id)).scalar()
    users_with_ratings = User.query.filter(User.id.in_(
        db.session.query(db.func.distinct(db.func.nullif(db.column('reviewed_id'), None)))
    )).count()
    
    status_breakdown = db.session.query(
        Session.status,
        db.func.count(Session.id)
    ).group_by(Session.status).all()
    
    return render_template('admin/analytics.html',
                         sessions_last_30=sessions_last_30_days,
                         sessions_last_7=sessions_last_7_days,
                         new_users_last_30=new_users_last_30,
                         new_users_last_7=new_users_last_7,
                         status_breakdown=status_breakdown)