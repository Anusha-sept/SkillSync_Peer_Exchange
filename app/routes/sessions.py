from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import User, Skill, Session
from datetime import datetime, timedelta

from app.utils.agora import (
    create_meeting_channel,
    get_session_duration_minutes,
    calculate_credits
)

from app.utils.email import (
    send_exchange_request_email,
    send_request_confirmation_email,
    create_notification
)

from app.utils.helpers import (
    profile_required,
    check_time_availability,
    check_booking_conflicts,
    get_user_busy_slots,
    get_common_availability
)

sessions_bp = Blueprint('sessions', __name__)


# =========================================================
# CREATE SESSION REQUEST
# =========================================================
@sessions_bp.route('/create/<int:user_id>', methods=['GET', 'POST'])
@login_required
@profile_required
def create_request(user_id):

    if user_id == current_user.id:
        flash('You cannot request a session with yourself.', 'danger')
        return redirect(url_for('main.matches'))

    provider = User.query.get_or_404(user_id)
    skills = Skill.query.all()

    if request.method == 'POST':

        skill_id = request.form.get('skill_id')
        your_skill_id = request.form.get('your_skill_id')
        duration = request.form.get('duration')
        date = request.form.get('date')
        time = request.form.get('time')

        if not all([skill_id, your_skill_id, duration, date, time]):
            flash('Please fill all fields.', 'danger')
            return redirect(url_for('sessions.create_request', user_id=user_id))

        try:
            scheduled_start = datetime.strptime(
                f"{date} {time}",
                "%Y-%m-%d %H:%M"
            )
        except ValueError:
            flash('Invalid date/time format.', 'danger')
            return redirect(url_for('sessions.create_request', user_id=user_id))

        if scheduled_start <= datetime.utcnow():
            flash('Select a future time.', 'danger')
            return redirect(url_for('sessions.create_request', user_id=user_id))

        duration_minutes = get_session_duration_minutes(duration)
        credits = calculate_credits(duration_minutes)
        scheduled_end = scheduled_start + timedelta(minutes=duration_minutes)

        # ---------------- CREDIT CHECK ----------------
        if current_user.credits < credits:
            flash(f'Need {credits} credits, you have {current_user.credits}', 'danger')
            return redirect(url_for('wallet.index'))

        # ---------------- DUPLICATE REQUEST CHECK ----------------
        existing = Session.query.filter_by(
            requester_id=current_user.id,
            provider_id=user_id,
            status='pending'
        ).first()

        if existing:
            flash('Request already exists.', 'warning')
            return redirect(url_for('main.matches'))

        # ---------------- CONFLICT CHECKS ----------------
        ok, msg = check_booking_conflicts(
            current_user.id, scheduled_start.date(), time, duration_minutes
        )
        if not ok:
            flash(msg, 'danger')
            return redirect(url_for('sessions.create_request', user_id=user_id))

        ok, msg = check_booking_conflicts(
            provider.id, scheduled_start.date(), time, duration_minutes
        )
        if not ok:
            flash(f'Provider: {msg}', 'danger')
            return redirect(url_for('sessions.create_request', user_id=user_id))

        ok, msg = check_time_availability(
            current_user, scheduled_start.date(), time, duration_minutes
        )
        if not ok:
            flash(f'You: {msg}', 'danger')
            return redirect(url_for('sessions.create_request', user_id=user_id))

        ok, msg = check_time_availability(
            provider, scheduled_start.date(), time, duration_minutes
        )
        if not ok:
            flash(f'Provider: {msg}', 'danger')
            return redirect(url_for('sessions.create_request', user_id=user_id))

        # ---------------- CREATE SESSION ----------------
        session = Session(
            requester_id=current_user.id,
            provider_id=user_id,
            requester_skill_id=your_skill_id,
            provider_skill_id=skill_id,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            duration_minutes=duration_minutes,
            credits_amount=credits,
            agora_channel=""   # temp
        )

        db.session.add(session)
        db.session.commit()

        # Agora channel after ID exists
        session.agora_channel = create_meeting_channel(session.id)
        db.session.commit()

        # ---------------- NOTIFICATIONS ----------------
        send_exchange_request_email(session)
        send_request_confirmation_email(session)

        create_notification(
            provider,
            "New Exchange Request 📩",
            f"{current_user.first_name} sent you a session request",
            'exchange_request',
            '/sessions/requests'
        )

        flash('Session request sent!', 'success')
        return redirect(url_for('sessions.my_sessions'))

    # =====================================================
    # GET: AVAILABILITY VIEW
    # =====================================================
    today = datetime.utcnow().date()

    provider_busy = get_user_busy_slots(provider.id, today)
    user_busy = get_user_busy_slots(current_user.id, today)

    common_slots = get_common_availability(current_user, provider)

    min_date = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')

    return render_template(
        'sessions/create.html',
        provider=provider,
        skills=skills,
        provider_busy=provider_busy,
        user_busy=user_busy,
        common_slots=common_slots,
        min_date=min_date
    )


# =========================================================
# REQUESTS PAGE
# =========================================================
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

    return render_template(
        'sessions/requests.html',
        incoming=incoming,
        outgoing=outgoing
    )


# =========================================================
# MY SESSIONS
# =========================================================
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


# =========================================================
# API: COMPARE AVAILABILITY (OPTIONAL UI FEATURE)
# =========================================================
@sessions_bp.route('/api/availability/<int:user1>/<int:user2>')
@login_required
def compare_availability(user1, user2):

    u1 = User.query.get_or_404(user1)
    u2 = User.query.get_or_404(user2)

    return jsonify({
        "user1": u1.full_name,
        "user2": u2.full_name,
        "common_slots": get_common_availability(u1, u2)
    })