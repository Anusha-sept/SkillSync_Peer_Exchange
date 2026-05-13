from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from app import db
from app.models import User, Skill, Session

from app.utils.helpers import (
    profile_required,
    check_time_availability,
    check_booking_conflicts,
    CREDIT_RATES,
    get_user_busy_slots,
    get_common_availability
)

sessions_bp = Blueprint('sessions', __name__)


# ---------------- CREATE REQUEST ----------------
@sessions_bp.route('/create/<int:user_id>', methods=['GET', 'POST'])
@login_required
@profile_required
def create_request(user_id):

    if user_id == current_user.id:
        flash("You cannot request yourself", "danger")
        return redirect(url_for("main.matches"))

    provider = User.query.get_or_404(user_id)
    skills = Skill.query.all()

    if request.method == "POST":

        skill_id = request.form.get("skill_id")
        your_skill_id = request.form.get("your_skill_id")
        duration = request.form.get("duration")
        date = request.form.get("date")
        time = request.form.get("time")

        if not all([skill_id, your_skill_id, duration, date, time]):
            flash("Fill all fields", "danger")
            return redirect(request.url)

        duration_minutes = int(duration)

        try:
            scheduled_start = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        except:
            flash("Invalid date/time", "danger")
            return redirect(request.url)

        if scheduled_start <= datetime.utcnow():
            flash("Select future time", "danger")
            return redirect(request.url)

        scheduled_end = scheduled_start + timedelta(minutes=duration_minutes)

        can_book, msg = check_booking_conflicts(
            current_user.id, scheduled_start.date(), time, duration_minutes
        )
        if not can_book:
            flash(msg, "danger")
            return redirect(request.url)

        can_book, msg = check_booking_conflicts(
            provider.id, scheduled_start.date(), time, duration_minutes
        )
        if not can_book:
            flash(msg, "danger")
            return redirect(request.url)

        session = Session(
            requester_id=current_user.id,
            provider_id=provider.id,
            requester_skill_id=your_skill_id,
            provider_skill_id=skill_id,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            duration_minutes=duration_minutes,
            credits_amount=CREDIT_RATES[str(duration)]["credits"],
            status="pending"
        )

        db.session.add(session)
        db.session.commit()

        flash("Request sent!", "success")
        return redirect(url_for("sessions.my_sessions"))

    # ---------------- GET ----------------
    today = datetime.utcnow().date()

    user_busy = get_user_busy_slots(current_user.id, today)
    provider_busy = get_user_busy_slots(provider.id, today)
    common_slots = get_common_availability(current_user, provider)

    min_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    return render_template(
        "sessions/create.html",
        provider=provider,
        skills=skills,
        user_busy=user_busy,
        provider_busy=provider_busy,
        common_slots=common_slots,
        min_date=min_date
    )


# ---------------- OTHER ROUTES ----------------
@sessions_bp.route("/my")
@login_required
def my_sessions():

    sessions = Session.query.filter(
        (Session.requester_id == current_user.id) |
        (Session.provider_id == current_user.id)
    ).all()

    return render_template("sessions/my_sessions.html", sessions=sessions)