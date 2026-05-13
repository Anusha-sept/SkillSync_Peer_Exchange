from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import User, Skill, Session, Review
from datetime import datetime, timedelta

from app.utils.agora import (
    get_agora_token,
    create_meeting_channel,
    can_join_session,
    get_session_duration_minutes,
    calculate_credits
)

from app.utils.email import (
    send_exchange_request_email,
    send_request_confirmation_email,
    send_session_accepted_email,
    send_session_rejected_email,
    create_notification
)

from app.utils.helpers import (
    profile_required,
    check_time_availability,
    check_booking_conflicts,
    CREDIT_RATES,
    get_user_busy_slots
)

sessions_bp = Blueprint('sessions', __name__)


# ---------------- CREATE REQUEST ----------------
@sessions_bp.route('/create/<int:user_id>', methods=['GET', 'POST'])
@login_required
@profile_required
def create_request(user_id):

    if user_id == current_user.id:
        flash('You cannot request a session with yourself.', 'danger')
        return redirect(url_for('main.matches'))

    provider = User.query.get_or_404(user_id)

    available_skills = Skill.query.all()

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
            scheduled_start = datetime.strptime(
                f"{date} {time}",
                "%Y-%m-%d %H:%M"
            )
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
            flash(
                f'You need {credits} credits but you only have {current_user.credits}.',
                'danger'
            )
            return redirect(url_for('wallet.index'))

        existing_request = Session.query.filter(
            Session.requester_id == current_user.id,
            Session.provider_id == user_id,
            Session.status == 'pending'
        ).first()

        if existing_request:
            flash('You already have a pending request with this user.', 'warning')
            return redirect(url_for('main.matches'))

        # Conflict checks
        can_book, message = check_booking_conflicts(
            current_user.id,
            scheduled_start.date(),
            time,
            duration_minutes
        )
        if not can_book:
            flash(message, 'danger')
            return redirect(url_for('sessions.create_request', user_id=user_id))

        can_book, message = check_booking_conflicts(
            provider.id,
            scheduled_start.date(),
            time,
            duration_minutes
        )
        if not can_book:
            flash(f'Provider {message}', 'warning')
            return redirect(url_for('sessions.create_request', user_id=user_id))

        can_book, message = check_time_availability(
            current_user,
            scheduled_start.date(),
            time,
            duration_minutes
        )
        if not can_book:
            flash(f'Your availability: {message}', 'danger')
            return redirect(url_for('sessions.create_request', user_id=user_id))

        can_book, message = check_time_availability(
            provider,
            scheduled_start.date(),
            time,
            duration_minutes
        )
        if not can_book:
            flash(f'Provider {message}', 'warning')
            return redirect(url_for('sessions.create_request', user_id=user_id))

        # Create session
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

        send_exchange_request_email(session)
        send_request_confirmation_email(session)

        create_notification(
            provider,
            "New Exchange Request! 📩",
            f"{current_user.first_name} wants to exchange skills with you!",
            'exchange_request',
            '/sessions/requests'
        )

        flash('Exchange request sent!', 'success')
        return redirect(url_for('sessions.my_sessions'))

    # ---------------- AVAILABILITY LOGIC (GET) ----------------
    today = datetime.utcnow().date()

    provider_busy = get_user_busy_slots(provider.id, today)
    user_busy = get_user_busy_slots(current_user.id, today)

    min_date = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')

    return render_template(
        'sessions/create.html',
        provider=provider,
        skills=available_skills,
        min_date=min_date,
        provider_busy=provider_busy,
        user_busy=user_busy
    )


# ---------------- OTHER ROUTES (UNCHANGED) ----------------
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


@sessions_bp.route('/my')
@login_required
def my_sessions():
    upcoming = Session.query.filter(
        ((Session.requester_id == current_user.id) |
         (Session.provider_id == current_user.id)),
        Session.status == 'accepted',
        Session.scheduled_start > datetime.utcnow()
    ).all()

    pending = Session.query.filter(
        ((Session.requester_id == current_user.id) |
         (Session.provider_id == current_user.id)),
        Session.status == 'pending'
    ).all()

    completed = Session.query.filter(
        ((Session.requester_id == current_user.id) |
         (Session.provider_id == current_user.id)),
        Session.status == 'completed'
    ).all()

    return render_template(
        'sessions/my_sessions.html',
        upcoming=upcoming,
        pending=pending,
        completed=completed
    )