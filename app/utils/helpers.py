from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user
from datetime import datetime, timedelta

from app.models import Session


# =====================================================
# PROFILE CHECK
# =====================================================
def profile_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and not current_user.profile_completed:
            flash("Complete your profile first.", "warning")
            return redirect(url_for("profile.edit"))
        return f(*args, **kwargs)
    return decorated_function


# =====================================================
# USER AVAILABILITY FORMATTER
# =====================================================
def get_user_availability(user):
    return [
        {
            "day_of_week": a.day_of_week,
            "start": a.start_time.strftime("%H:%M"),
            "end": a.end_time.strftime("%H:%M")
        }
        for a in user.availability
    ]


# =====================================================
# CHECK TIME SLOT INSIDE AVAILABILITY
# =====================================================
def check_time_availability(user, date, start_time, duration_minutes):
    day = date.weekday()

    slot = next((a for a in user.availability if a.day_of_week == day), None)

    if not slot:
        return False, "Not available on this day"

    try:
        start = datetime.strptime(start_time, "%H:%M").time()
    except ValueError:
        return False, "Invalid time format"

    end = (datetime.combine(date, start) + timedelta(minutes=duration_minutes)).time()

    if start < slot.start_time or end > slot.end_time:
        return False, "Outside availability"

    return True, "OK"


# =====================================================
# BOOKING CONFLICT CHECK
# =====================================================
def check_booking_conflicts(user_id, date, start_time, duration_minutes):
    try:
        start_dt = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
    except ValueError:
        return False, "Invalid datetime"

    end_dt = start_dt + timedelta(minutes=duration_minutes)

    conflict = Session.query.filter(
        ((Session.requester_id == user_id) | (Session.provider_id == user_id)),
        Session.status.in_(["pending", "accepted"]),
        Session.scheduled_start < end_dt,
        Session.scheduled_end > start_dt
    ).first()

    if conflict:
        return False, "Conflicting session exists"

    return True, "OK"


# =====================================================
# BUSY SLOTS (FIXED - NO IMPORT ERROR)
# =====================================================
def get_user_busy_slots(user_id, date):
    sessions = Session.query.filter(
        ((Session.requester_id == user_id) | (Session.provider_id == user_id)),
        Session.status.in_(["pending", "accepted"])
    ).all()

    return [
        {
            "start": s.scheduled_start.time(),
            "end": s.scheduled_end.time()
        }
        for s in sessions
        if s.scheduled_start and s.scheduled_start.date() == date
    ]


# =====================================================
# COMMON SLOTS (THIS FIXES YOUR UI FEATURE)
# =====================================================
def get_common_availability(user1, user2):
    common = []

    for a1 in user1.availability:
        for a2 in user2.availability:

            if a1.day_of_week == a2.day_of_week:

                start = max(a1.start_time, a2.start_time)
                end = min(a1.end_time, a2.end_time)

                if start < end:
                    common.append({
                        "day_of_week": a1.day_of_week,
                        "start": start.strftime("%H:%M"),
                        "end": end.strftime("%H:%M")
                    })

    return common


# =====================================================
# CREDIT SYSTEM
# =====================================================
CREDIT_RATES = {
    "30": {"minutes": 30, "credits": 25},
    "60": {"minutes": 60, "credits": 50},
    "120": {"minutes": 120, "credits": 100}
}