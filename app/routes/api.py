from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app import db, csrf
from app.models import User, Skill, Session, Notification
from datetime import datetime, timedelta

api_bp = Blueprint('api', __name__)


@api_bp.route('/skills', methods=['GET'])
def get_skills():
    skills = Skill.query.all()
    return jsonify([{'id': s.id, 'name': s.name, 'category': s.category} for s in skills])


@api_bp.route('/search-users')
@login_required
def search_users():
    query = request.args.get('q', '')
    
    users = User.query.filter(
        User.username.ilike(f'%{query}%'),
        User.id != current_user.id,
        User.is_active == True
    ).limit(10).all()
    
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'name': u.full_name,
        'avatar': u.avatar,
        'skills': [s.name for s in u.offered_skills[:3]]
    } for u in users])


@api_bp.route('/notifications/count')
@login_required
def notifications_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})


@api_bp.route('/notifications/mark-read/<int:notification_id>')
@login_required
def mark_notification_read_api(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id == current_user.id:
        notification.is_read = True
        db.session.commit()
    return jsonify({'success': True})


@api_bp.route('/check-session-status/<int:session_id>')
@login_required
def check_session_status(session_id):
    session = Session.query.get_or_404(session_id)
    
    if session.requester_id != current_user.id and session.provider_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    now = datetime.utcnow()
    five_min_before = session.scheduled_start - timedelta(minutes=5)
    
    can_join = now >= five_min_before and now <= session.scheduled_end
    
    return jsonify({
        'status': session.status,
        'can_join': can_join,
        'start_time': session.scheduled_start.isoformat(),
        'end_time': session.scheduled_end.isoformat()
    })


@api_bp.route('/update-online-status', methods=['POST'])
@login_required
@csrf.exempt
def update_online_status():
    current_user.is_online = request.json.get('is_online', True)
    db.session.commit()
    return jsonify({'success': True})


@api_bp.route('/validate-credits')
@login_required
def validate_credits_api():
    amount = request.args.get('amount', type=int)
    if current_user.credits >= amount:
        return jsonify({'valid': True})
    return jsonify({'valid': False, 'available': current_user.credits})


@api_bp.route('/session/<int:session_id>/reviews')
@login_required
def get_session_reviews(session_id):
    session = Session.query.get_or_404(session_id)
    reviews = session.reviews.all()
    
    return jsonify([{
        'id': r.id,
        'reviewer': r.reviewer.full_name,
        'rating': r.rating,
        'comment': r.comment,
        'created_at': r.created_at.isoformat()
    } for r in reviews])


@api_bp.route('/user/<int:user_id>/stats')
@login_required
def get_user_stats(user_id):
    user = User.query.get_or_404(user_id)
    
    completed_sessions = Session.query.filter(
        ((Session.requester_id == user.id) | (Session.provider_id == user.id)),
        Session.status == 'completed'
    ).count()
    
    return jsonify({
        'total_sessions': completed_sessions,
        'average_rating': user.average_rating,
        'total_credits_earned': user.total_credits_earned,
        'achievement': user.achievement_title,
        'member_since': user.created_at.isoformat()
    })
