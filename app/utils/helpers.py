from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user
from datetime import datetime, timedelta


# =====================================================
# PROFILE REQUIRED
# =====================================================
def profile_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and not current_user.profile_completed:
            flash("Complete your profile first", "warning")
            return redirect(url_for("profile.edit"))
        return f(*args, **kwargs)
    return decorated_function


# =====================================================
# USER AVAILABILITY FORMATTER
# =====================================================
def get_user_availability(user):
    availability = {}

    for av in user.availability:
        availability[av.day_of_week] = {
            "start": av.start_time.strftime("%H:%M"),
            "end": av.end_time.strftime("%H:%M")
        }

    return availability


# =====================================================
# BUSY SLOTS (RETURN OBJECTS - FIX FOR TEMPLATE)
# =====================================================
def get_user_busy_slots(user_id, date):
    from app.models import Session

    sessions = Session.query.filter(
        (Session.requester_id == user_id) |
        (Session.provider_id == user_id),
        Session.status.in_(["pending", "accepted"])
    ).all()

    busy = []

    for s in sessions:
        if s.scheduled_start and s.scheduled_start.date() == date:
            busy.append(s)

    return busy


# =====================================================
# COMMON AVAILABILITY (FIXED)
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
# TIME CHECK
# =====================================================
def check_time_availability(user, date, start_time, duration_minutes):
    day = date.weekday()

    slot = next((a for a in user.availability if a.day_of_week == day), None)

    if not slot:
        return False, "No availability"

    try:
        start = datetime.strptime(start_time, "%H:%M").time()
    except:
        return False, "Invalid time"

    end = (datetime.combine(date, start) + timedelta(minutes=duration_minutes)).time()

    if start < slot.start_time or end > slot.end_time:
        return False, "Outside available hours"

    return True, "OK"


# =====================================================
# BOOKING CONFLICT
# =====================================================
def check_booking_conflicts(user_id, date, start_time, duration_minutes):
    from app.models import Session

    try:
        start_dt = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
    except:
        return False, "Invalid datetime"

    end_dt = start_dt + timedelta(minutes=duration_minutes)

    conflict = Session.query.filter(
        (Session.requester_id == user_id) |
        (Session.provider_id == user_id),
        Session.status.in_(["pending", "accepted"]),
        Session.scheduled_start < end_dt,
        Session.scheduled_end > start_dt
    ).first()

    if conflict:
        return False, "Conflicting session exists"

    return True, "OK"


# =====================================================
# CREDIT RATES
# =====================================================
CREDIT_RATES = {
    "30": 25,
    "60": 50,
    "120": 100
}