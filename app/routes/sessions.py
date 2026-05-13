from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from app import db
from app.models import User, Skill, Session

from app.utils.agora import create_meeting_channel, get_session_duration_minutes
from app.utils.email import send_exchange_request_email, send_request_confirmation_email, create_notification
from app.utils.helpers import (
    profile_required,
    check_booking_conflicts,
    get_user_busy_slots,
    get_common_availability
)

sessions_bp = Blueprint("sessions", __name__)


# =====================================================
# CREATE REQUEST
# =====================================================
@sessions_bp.route("/create/<int:user_id>", methods=["GET", "POST"])
@login_required
@profile_required
def create_request(user_id):

    if user_id == current_user.id:
        flash("Cannot book yourself", "danger")
        return redirect(url_for("main.matches"))

    provider = User.query.get_or_404(user_id)

    common_slots = get_common_availability(current_user, provider)

    today = datetime.utcnow().date()

    user_busy = get_user_busy_slots(current_user.id, today)
    provider_busy = get_user_busy_slots(provider.id, today)

    min_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    if request.method == "POST":

        skill_id = request.form.get("skill_id")
        your_skill_id = request.form.get("your_skill_id")
        date = request.form.get("date")
        time = request.form.get("time")
        duration = request.form.get("duration")

        if not all([skill_id, your_skill_id, date, time, duration]):
            flash("Fill all fields", "danger")
            return redirect(request.url)

        duration_minutes = get_session_duration_minutes(duration)

        start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        ok, msg = check_booking_conflicts(current_user.id, date, time, duration_minutes)
        if not ok:
            flash(msg, "danger")
            return redirect(request.url)

        ok, msg = check_booking_conflicts(provider.id, date, time, duration_minutes)
        if not ok:
            flash(msg, "danger")
            return redirect(request.url)

        session = Session(
            requester_id=current_user.id,
            provider_id=provider.id,
            requester_skill_id=your_skill_id,
            provider_skill_id=skill_id,
            scheduled_start=start_dt,
            scheduled_end=end_dt,
            duration_minutes=duration_minutes,
            credits_amount=50,
            status="pending",
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
            "New Session Request",
            f"{current_user.first_name} sent a request",
            "exchange_request",
            "/sessions/requests"
        )

        flash("Request sent successfully!", "success")
        return redirect(url_for("sessions.my_sessions"))

    return render_template(
        "sessions/create.html",
        provider=provider,
        common_slots=common_slots,
        user_busy=user_busy,
        provider_busy=provider_busy,
        min_date=min_date
    )


# =====================================================
# MY SESSIONS (FIX FOR YOUR DASHBOARD ERROR)
# =====================================================
@sessions_bp.route("/my")
@login_required
def my_sessions():

    upcoming = Session.query.filter(
        (Session.requester_id == current_user.id) |
        (Session.provider_id == current_user.id),
        Session.status == "accepted"
    ).all()

    pending = Session.query.filter(
        (Session.requester_id == current_user.id) |
        (Session.provider_id == current_user.id),
        Session.status == "pending"
    ).all()

    completed = Session.query.filter(
        (Session.requester_id == current_user.id) |
        (Session.provider_id == current_user.id),
        Session.status == "completed"
    ).all()

    return render_template(
        "sessions/my_sessions.html",
        upcoming=upcoming,
        pending=pending,
        completed=completed
    )