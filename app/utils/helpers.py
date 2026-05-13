from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user


# ---------------------------
# PROFILE REQUIRED
# ---------------------------
def profile_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and not current_user.profile_completed:
            flash(
                'Please complete your profile, add skills, and set availability.',
                'warning'
            )
            return redirect(url_for('profile.edit'))
        return f(*args, **kwargs)
    return decorated_function


# ---------------------------
# USER BUSY SLOTS
# ---------------------------
def get_user_busy_slots(user_id, date):
    from app.models import Session

    sessions = Session.query.filter(
        (Session.requester_id == user_id) |
        (Session.provider_id == user_id),
        Session.status.in_(['pending', 'accepted'])
    ).all()

    busy = []

    for s in sessions:
        if s.scheduled_start and s.scheduled_start.date() == date:
            busy.append((s.scheduled_start.time(), s.scheduled_end.time()))

    return busy


# ---------------------------
# COMMON AVAILABILITY (MAIN FIX)
# ---------------------------
def get_common_availability(user1, user2):
    common = []

    for a1 in user1.availability:
        for a2 in user2.availability:

            if a1.day_of_week != a2.day_of_week:
                continue

            start = max(a1.start_time, a2.start_time)
            end = min(a1.end_time, a2.end_time)

            if start < end:
                common.append({
                    "day": a1.day_of_week,
                    "start": start,
                    "end": end
                })

    return common


# ---------------------------
# TIME CHECK
# ---------------------------
def check_time_availability(user, date, start_time, duration_minutes):
    from datetime import datetime, timedelta

    day_of_week = date.weekday()

    slot = next(
        (a for a in user.availability if a.day_of_week == day_of_week),
        None
    )

    if not slot:
        return False, "User not available on this day"

    try:
        start = datetime.strptime(start_time, "%H:%M").time()
    except ValueError:
        return False, "Invalid time format"

    end = (datetime.combine(date, start) +
           timedelta(minutes=duration_minutes)).time()

    if start < slot.start_time or end > slot.end_time:
        return False, "Outside availability"

    return True, "Available"


# ---------------------------
# BOOKING CONFLICTS
# ---------------------------
def check_booking_conflicts(user_id, date, start_time, duration_minutes):
    from datetime import datetime, timedelta
    from app.models import Session

    try:
        session_start = datetime.strptime(
            f"{date} {start_time}",
            "%Y-%m-%d %H:%M"
        )
    except ValueError:
        return False, "Invalid date/time"

    session_end = session_start + timedelta(minutes=duration_minutes)

    conflict = Session.query.filter(
        (Session.requester_id == user_id) |
        (Session.provider_id == user_id),
        Session.status.in_(['pending', 'accepted']),
        Session.scheduled_start < session_end,
        Session.scheduled_end > session_start
    ).first()

    if conflict:
        return False, "Conflicting session exists"

    return True, "No conflict"


# ---------------------------
# CREDIT RATES
# ---------------------------
CREDIT_RATES = {
    "30": {"minutes": 30, "credits": 25},
    "60": {"minutes": 60, "credits": 50},
    "120": {"minutes": 120, "credits": 100}
}