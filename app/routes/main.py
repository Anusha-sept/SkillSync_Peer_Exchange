from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import User, Skill, Session, Notification, WalletTransaction, Certificate
from datetime import datetime, timedelta
from app.utils.helpers import profile_required

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('main/index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    upcoming_sessions = Session.query.filter(
        ((Session.requester_id == current_user.id) | (Session.provider_id == current_user.id)),
        Session.status == 'accepted',
        Session.scheduled_start > datetime.utcnow()
    ).order_by(Session.scheduled_start).limit(3).all()
    
    pending_requests = Session.query.filter(
        Session.provider_id == current_user.id,
        Session.status == 'pending'
    ).order_by(Session.created_at.desc()).limit(5).all()
    
    recent_notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    recent_transactions = WalletTransaction.query.filter_by(
        user_id=current_user.id
    ).order_by(WalletTransaction.created_at.desc()).limit(5).all()
    
    stats = {
        'total_sessions': Session.query.filter(
            ((Session.requester_id == current_user.id) | (Session.provider_id == current_user.id)),
            Session.status == 'completed'
        ).count(),
        'total_credits_earned': current_user.total_credits_earned,
        'average_rating': current_user.average_rating,
        'certificates_count': current_user.certificates.count()
    }
    
    return render_template('main/dashboard.html',
                         upcoming_sessions=upcoming_sessions,
                         pending_requests=pending_requests,
                         recent_notifications=recent_notifications,
                         recent_transactions=recent_transactions,
                         stats=stats)


@main_bp.route('/explore')
@login_required
@profile_required
def explore():
    users = User.query.filter(
        User.id != current_user.id,
        User.is_active == True,
        User.profile_completed == True
    ).join(User.availability).all()
    
    skills = Skill.query.all()
    
    return render_template('main/explore.html', users=users, skills=skills)


@main_bp.route('/matches')
@login_required
@profile_required
def matches():
    users = User.query.filter(
        User.id != current_user.id,
        User.is_active == True,
        User.profile_completed == True
    ).join(User.availability).all()
    
    matches = []
    for user in users:
        match_score = calculate_match_score(current_user, user)
        if match_score > 30:
            matches.append({
                'user': user,
                'score': match_score,
                'common_skills': get_common_skills(current_user, user),
                'matching_skills': get_matching_wanted_skills(current_user, user)
            })
    
    matches.sort(key=lambda x: x['score'], reverse=True)
    
    return render_template('main/matches.html', matches=matches)


def calculate_match_score(user, other):
    score = 0
    
    user_offered = set(s.id for s in user.offered_skills)
    user_wanted = set(s.id for s in user.wanted_skills)
    other_offered = set(s.id for s in other.offered_skills)
    other_wanted = set(s.id for s in other.wanted_skills)
    
    if user_offered & other_wanted:
        score += 40
    if other_offered & user_wanted:
        score += 40
    
    experience_scores = {'beginner': 1, 'intermediate': 2, 'advanced': 3, 'expert': 4}
    user_exp = experience_scores.get(user.experience_level, 1)
    other_exp = experience_scores.get(other.experience_level, 1)
    score += (user_exp + other_exp) * 2
    
    if other.average_rating > 0:
        score += min(other.average_rating * 5, 20)
    
    return score


def get_common_skills(user, other):
    user_offered = set(s.id for s in user.offered_skills)
    other_offered = set(s.id for s in other.offered_skills)
    common = user_offered & other_offered
    return Skill.query.filter(Skill.id.in_(common)).all()


def get_matching_wanted_skills(user, other):
    user_wanted = set(s.id for s in user.wanted_skills)
    other_offered = set(s.id for s in other.offered_skills)
    matching = user_wanted & other_offered
    return Skill.query.filter(Skill.id.in_(matching)).all()


@main_bp.route('/notifications')
@login_required
def notifications():
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).all()
    
    return render_template('main/notifications.html', notifications=notifications)


@main_bp.route('/notifications/mark-read/<int:notification_id>')
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id == current_user.id:
        notification.is_read = True
        db.session.commit()
    
    if notification.link:
        return redirect(notification.link)
    return redirect(url_for('main.notifications'))


@main_bp.route('/notifications/mark-all-read')
@login_required
def mark_all_notifications_read():
    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).update({'is_read': True})
    db.session.commit()
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('main.notifications'))


@main_bp.route('/leaderboard')
@login_required
def leaderboard():
    top_users = User.query.order_by(
        User.total_credits_earned.desc()
    ).limit(20).all()
    
    return render_template('main/leaderboard.html', top_users=top_users)