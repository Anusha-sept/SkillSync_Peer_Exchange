from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from app import db
from app.models import User, Session

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
        flash("Cannot request yourself", "danger")
        return redirect(url_for("main.matches"))

    provider = User.query.get_or_404(user_id)

    common_slots = get_common_availability(current_user, provider)
    provider_busy = get_user_busy_slots(provider.id, datetime.utcnow().date())
    user_busy = get_user_busy_slots(current_user.id, datetime.utcnow().date())

    if request.method == "POST":

        skill_id = request.form.get("skill_id")
        your_skill_id = request.form.get("your_skill_id")
        duration = request.form.get("duration")
        date = request.form.get("date")
        time = request.form.get("time")

        if not all([skill_id, your_skill_id, duration, date, time]):
            flash("Fill all fields", "danger")
            return redirect(request.url)

        start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")

        duration_minutes = get_session_duration_minutes(duration)
        credits = calculate_credits(duration_minutes)
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        if current_user.credits < credits:
            flash("Not enough credits", "danger")
            return redirect(url_for("wallet.index"))

        ok, msg = check_booking_conflicts(
            current_user.id, start_dt.date(), time, duration_minutes
        )
        if not ok:
            flash(msg, "danger")
            return redirect(request.url)

        ok, msg = check_booking_conflicts(
            provider.id, start_dt.date(), time, duration_minutes
        )
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
            "New Request",
            f"{current_user.first_name} sent you a request",
            "exchange_request",
            "/sessions/requests"
        )

        flash("Request sent!", "success")
        return redirect(url_for("sessions.my_sessions"))

    min_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    return render_template(
        "sessions/create.html",
        provider=provider,
        min_date=min_date,
        provider_busy=provider_busy,
        user_busy=user_busy,
        common_slots=common_slots
    )


# =====================================================
# MY SESSIONS (FIX FOR YOUR ERROR)
# =====================================================
@sessions_bp.route("/my")
@login_required
def my_sessions():
    sessions = Session.query.filter(
        (Session.requester_id == current_user.id) |
        (Session.provider_id == current_user.id)
    ).order_by(Session.scheduled_start.desc()).all()

    return render_template("sessions/my_sessions.html", sessions=sessions)


# =====================================================
# REQUESTS
# =====================================================
@sessions_bp.route("/requests")
@login_required
def requests():
    pending = Session.query.filter(
        Session.provider_id == current_user.id,
        Session.status == 'pending'
    ).order_by(Session.created_at.desc()).all()
    return render_template("sessions/requests.html", sessions=pending)


# =====================================================
# ACCEPT REQUEST
# =====================================================
@sessions_bp.route("/accept/<int:session_id>")
@login_required
def accept_request(session_id):
    session = Session.query.get_or_404(session_id)
    if session.provider_id != current_user.id:
        flash("Unauthorized", "danger")
        return redirect(url_for("sessions.my_sessions"))
    if session.status != 'pending':
        flash("Request already processed", "warning")
        return redirect(url_for("sessions.requests"))
    session.status = 'accepted'
    db.session.commit()
    from app.utils.email import send_session_accepted_email, create_notification
    send_session_accepted_email(session)
    create_notification(session.requester, "Request Accepted", f"{current_user.first_name} accepted your request", "session_accepted", f"/sessions/room/{session.id}")
    flash("Request accepted!", "success")
    return redirect(url_for("sessions.requests"))


# =====================================================
# REJECT REQUEST
# =====================================================
@sessions_bp.route("/reject/<int:session_id>")
@login_required
def reject_request(session_id):
    session = Session.query.get_or_404(session_id)
    if session.provider_id != current_user.id:
        flash("Unauthorized", "danger")
        return redirect(url_for("sessions.my_sessions"))
    if session.status != 'pending':
        flash("Request already processed", "warning")
        return redirect(url_for("sessions.requests"))
    session.status = 'rejected'
    db.session.commit()
    from app.utils.email import send_session_rejected_email, create_notification
    send_session_rejected_email(session)
    create_notification(session.requester, "Request Declined", f"{current_user.first_name} declined your request", "session_rejected", "/sessions/my")
    flash("Request declined", "info")
    return redirect(url_for("sessions.requests"))