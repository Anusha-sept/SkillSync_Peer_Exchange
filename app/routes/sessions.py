from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import User, Skill, Session, Review
from datetime import datetime, timedelta
from app.utils.agora import get_agora_token, create_meeting_channel, can_join_session, get_session_duration_minutes, calculate_credits
from app.utils.email import send_exchange_request_email, send_request_confirmation_email, send_session_accepted_email, send_session_rejected_email, create_notification
from app.utils.helpers import profile_required, check_time_availability, check_booking_conflicts, CREDIT_RATES

sessions_bp = Blueprint('sessions', __name__)


@sessions_bp.route('/create/<int:user_id>', methods=['GET', 'POST'])
@login_required
@profile_required
def create_request(user_id):
    if user_id == current_user.id:
        flash('You cannot request a session with yourself.', 'danger')
        return redirect(url_for('main.matches'))
    
    provider = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        skill_id = request.form.get('skill_id')
        your_skill_id = request.form.get('your_skill_id')
        duration = request.form.get('duration')
        date = request.form.get('date')
        time = request.form.get('time')
        
        if not all([skill_id, your_skill_id, duration, date, time]):
            flash('Please fill in all fields.', 'danger')
            return redirect(url_for('sessions.create_request', user_id=user_id))
        
        skill = Skill.query.get(skill_id)
        your_skill = Skill.query.get(your_skill_id)
        
        try:
            scheduled_start = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        except ValueError:
            flash('Invalid date or time format.', 'danger')
            return redirect(url_for('sessions.create_request', user_id=user_id))
        
        if scheduled_start <= datetime.utcnow():
            flash('Please select a future date and time.', 'danger')
            return redirect(url_for('sessions.create_request', user_id=user_id))
        
        duration_minutes = get_session_duration_minutes(duration)
        credits = calculate_credits(duration_minutes)
        scheduled_end = scheduled_start + timedelta(minutes=duration_minutes)
        
        if current_user.credits < credits:
            flash(f'You need {credits} credits but you only have {current_user.credits}. Please top up first.', 'danger')
            return redirect(url_for('wallet.deposit'))
        
        existing_request = Session.query.filter(
            Session.requester_id == current_user.id,
            Session.provider_id == user_id,
            Session.status == 'pending'
        ).first()
        
        if existing_request:
            flash('You already have a pending request with this user.', 'warning')
            return redirect(url_for('main.matches'))
        
        can_book, message = check_booking_conflicts(current_user.id, scheduled_start.date(), time, duration_minutes)
        if not can_book:
            flash(message, 'danger')
            return redirect(url_for('sessions.create_request', user_id=user_id))
        
        can_book_provider, message = check_booking_conflicts(provider.id, scheduled_start.date(), time, duration_minutes)
        if not can_book_provider:
            flash(f'Provider {message}', 'warning')
            return redirect(url_for('sessions.create_request', user_id=user_id))
        
        can_book, message = check_time_availability(current_user, scheduled_start.date(), time, duration_minutes)
        if not can_book:
            flash(f'Your availability: {message}', 'danger')
            return redirect(url_for('sessions.create_request', user_id=user_id))
        
        can_book, message = check_time_availability(provider, scheduled_start.date(), time, duration_minutes)
        if not can_book:
            flash(f'Provider {message}', 'warning')
            return redirect(url_for('sessions.create_request', user_id=user_id))
        
        session = Session(
            requester_id=current_user.id,
            provider_id=user_id,
            requester_skill_id=your_skill_id,
            provider_skill_id=skill_id,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            duration_minutes=duration_minutes,
            credits_amount=credits,
            agora_channel=create_meeting_channel(0)
        )
        
        db.session.add(session)
        db.session.commit()
        
        session.agora_channel = create_meeting_channel(session.id)
        db.session.commit()
        
        current_user.credits -= credits
        
        send_exchange_request_email(session)
        send_request_confirmation_email(session)
        
        create_notification(
            provider,
            "New Exchange Request! 📩",
            f"{current_user.first_name} wants to exchange skills with you!",
            'exchange_request',
            f'/sessions/requests'
        )
        
        flash('Exchange request sent! The user will be notified.', 'success')
        return redirect(url_for('sessions.my_sessions'))
    
    available_skills = Skill.query.all()
    min_date = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')
    return render_template(
        'sessions/create.html',
        provider=provider,
        skills=available_skills,
        min_date=min_date,
    )


@sessions_bp.route('/requests')
@login_required
def requests():
    incoming = Session.query.filter_by(
        provider_id=current_user.id,
        status='pending'
    ).order_by(Session.created_at.desc()).all()
    
    outgoing = Session.query.filter_by(
        requester_id=current_user.id,
        status='pending'
    ).order_by(Session.created_at.desc()).all()
    
    return render_template('sessions/requests.html', incoming=incoming, outgoing=outgoing)


@sessions_bp.route('/accept/<int:session_id>')
@login_required
def accept_request(session_id):
    session = Session.query.get_or_404(session_id)
    
    if session.provider_id != current_user.id:
        flash('You are not authorized to accept this request.', 'danger')
        return redirect(url_for('sessions.requests'))
    
    if session.status != 'pending':
        flash('This request has already been processed.', 'warning')
        return redirect(url_for('sessions.requests'))
    
    session.status = 'accepted'
    
    send_session_accepted_email(session)
    
    create_notification(
        session.requester,
        "Request Accepted! 🎉",
        f"{current_user.first_name} accepted your exchange request!",
        'session_accepted',
        f'/sessions/my'
    )
    
    db.session.commit()
    flash('Request accepted! Both users have been notified.', 'success')
    return redirect(url_for('sessions.requests'))


@sessions_bp.route('/reject/<int:session_id>')
@login_required
def reject_request(session_id):
    session = Session.query.get_or_404(session_id)
    
    if session.provider_id != current_user.id:
        flash('You are not authorized to reject this request.', 'danger')
        return redirect(url_for('sessions.requests'))
    
    if session.status != 'pending':
        flash('This request has already been processed.', 'warning')
        return redirect(url_for('sessions.requests'))
    
    session.status = 'rejected'
    
    send_session_rejected_email(session)
    
    create_notification(
        session.requester,
        "Request Declined 😔",
        f"{current_user.first_name} declined your exchange request.",
        'session_rejected',
        '/sessions/my'
    )
    
    session.requester.credits += session.credits_amount
    
    db.session.commit()
    flash('Request rejected.', 'info')
    return redirect(url_for('sessions.requests'))


@sessions_bp.route('/my')
@login_required
def my_sessions():
    upcoming = Session.query.filter(
        ((Session.requester_id == current_user.id) | (Session.provider_id == current_user.id)),
        Session.status == 'accepted',
        Session.scheduled_start > datetime.utcnow()
    ).order_by(Session.scheduled_start).all()
    
    pending = Session.query.filter(
        ((Session.requester_id == current_user.id) | (Session.provider_id == current_user.id)),
        Session.status == 'pending'
    ).order_by(Session.created_at.desc()).all()
    
    completed = Session.query.filter(
        ((Session.requester_id == current_user.id) | (Session.provider_id == current_user.id)),
        Session.status == 'completed'
    ).order_by(Session.scheduled_start.desc()).all()
    
    return render_template('sessions/my_sessions.html',
                         upcoming=upcoming,
                         pending=pending,
                         completed=completed)


@sessions_bp.route('/room/<int:session_id>')
@login_required
def room(session_id):
    session = Session.query.get_or_404(session_id)
    
    if session.requester_id != current_user.id and session.provider_id != current_user.id:
        flash('You are not authorized to join this session.', 'danger')
        return redirect(url_for('sessions.my_sessions'))
    
    if session.status not in ['accepted', 'completed']:
        flash('This session is not available for video calling.', 'warning')
        return redirect(url_for('sessions.my_sessions'))
    
    can_join, message = can_join_session(session, current_user.id)
    
    if not can_join:
        flash(message, 'warning')
        return redirect(url_for('sessions.my_sessions'))
    
    other_user = session.provider if session.requester_id == current_user.id else session.requester
    
    token_data = get_agora_token(session.agora_channel, current_user.id)
    
    return render_template('sessions/room.html',
                         session=session,
                         other_user=other_user,
                         agora_app_id=token_data['app_id'],
                         agora_token=token_data['token'],
                         channel=token_data['channel'],
                         uid=token_data['uid'])


@sessions_bp.route('/review/<int:session_id>', methods=['GET', 'POST'])
@login_required
def review(session_id):
    session = Session.query.get_or_404(session_id)
    
    if session.status != 'completed':
        flash('This session is not available for review.', 'warning')
        return redirect(url_for('sessions.my_sessions'))
    
    if session.requester_id != current_user.id and session.provider_id != current_user.id:
        flash('You are not authorized to review this session.', 'danger')
        return redirect(url_for('sessions.my_sessions'))
    
    existing_review = Review.query.filter_by(
        session_id=session.id,
        reviewer_id=current_user.id
    ).first()
    
    if existing_review:
        flash('You have already reviewed this session.', 'warning')
        return redirect(url_for('sessions.my_sessions'))
    
    if request.method == 'POST':
        rating = int(request.form.get('rating'))
        comment = request.form.get('comment')
        
        reviewed_id = session.provider_id if session.requester_id == current_user.id else session.requester_id
        
        review = Review(
            session_id=session.id,
            reviewer_id=current_user.id,
            reviewed_id=reviewed_id,
            rating=rating,
            comment=comment
        )
        
        db.session.add(review)
        db.session.commit()
        
        flash('Review submitted! Thanks for your feedback.', 'success')
        return redirect(url_for('sessions.my_sessions'))
    
    other_user = session.provider if session.requester_id == current_user.id else session.requester
    return render_template('sessions/review.html', session=session, other_user=other_user)


@sessions_bp.route('/history')
@login_required
def history():
    sessions = Session.query.filter(
        ((Session.requester_id == current_user.id) | (Session.provider_id == current_user.id)),
        Session.status.in_(['completed', 'rejected', 'expired'])
    ).order_by(Session.scheduled_start.desc()).all()
    
    return render_template('sessions/history.html', sessions=sessions)
