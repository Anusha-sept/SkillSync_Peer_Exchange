from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user
from datetime import datetime, timedelta

from app import db
from app.models import Session


# =====================================================
# PROFILE REQUIRED
# =====================================================
def profile_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and not current_user.profile_completed:
            flash(
                "Please complete your profile, add skills, and set availability.",
                "warning"
            )
            return redirect(url_for("profile.edit"))
        return f(*args, **kwargs)

    return decorated_function


# =====================================================
# GET USER AVAILABILITY (FIXED)
# =====================================================
def get_user_availability(user):
    availability = []

    for av in user.availability:
        availability.append({
            "day_of_week": av.day_of_week,
            "start": av.start_time.strftime("%H:%M") if av.start_time else None,
            "end": av.end_time.strftime("%H:%M") if av.end_time else None
        })

    return availability


# =====================================================
# CHECK TIME AVAILABILITY
# =====================================================
def check_time_availability(user, date, start_time, duration_minutes):
    day_of_week = date.weekday()

    user_avail = next(
        (a for a in user.availability if a.day_of_week == day_of_week),
        None
    )

    if not user_avail:
        return False, "User not available on this day"

    try:
        start = datetime.strptime(start_time, "%H:%M").time()
    except ValueError:
        return False, "Invalid time format"

    end_time = (
        datetime.combine(date, start) + timedelta(minutes=duration_minutes)
    ).time()

    if user_avail.start_time and start < user_avail.start_time:
        return False, "Outside available hours"

    if user_avail.end_time and end_time > user_avail.end_time:
        return False, "Outside available hours"

    return True, "Available"


# =====================================================
# BOOKING CONFLICT CHECK
# =====================================================
def check_booking_conflicts(user_id, date, start_time, duration_minutes):
    try:
        session_start = datetime.strptime(
            f"{date} {start_time}",
            "%Y-%m-%d %H:%M"
        )
    except ValueError:
        return False, "Invalid date/time"

    session_end = session_start + timedelta(minutes=duration_minutes)

    conflict = Session.query.filter(
        ((Session.requester_id == user_id) |
         (Session.provider_id == user_id)),
        Session.status.in_(["pending", "accepted"]),
        Session.scheduled_start < session_end,
        Session.scheduled_end > session_start
    ).first()

    if conflict:
        return False, "Conflicting session exists"

    return True, "No conflicts"


# =====================================================
# BUSY SLOTS (THIS FIXES YOUR IMPORT ERROR)
# =====================================================
def get_user_busy_slots(user_id, date):
    sessions = Session.query.filter(
        ((Session.requester_id == user_id) |
         (Session.provider_id == user_id)),
        Session.status.in_(["pending", "accepted"])
    ).all()

    busy = []

    for s in sessions:
        if s.scheduled_start and s.scheduled_start.date() == date:
            busy.append({
                "start": s.scheduled_start.time(),
                "end": s.scheduled_end.time()
            })

    return busy


# =====================================================
# CREDIT SYSTEM
# =====================================================
CREDIT_RATES = {
    "30": {"minutes": 30, "credits": 25},
    "60": {"minutes": 60, "credits": 50},
    "120": {"minutes": 120, "credits": 100}
}