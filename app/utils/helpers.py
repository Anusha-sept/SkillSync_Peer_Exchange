from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user


# =====================================================
# PROFILE REQUIRED DECORATOR
# =====================================================
def profile_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and not current_user.profile_completed:
            flash(
                'Please complete your profile, add skills, and set availability to access this feature.',
                'warning'
            )
            return redirect(url_for('profile.edit'))
        return f(*args, **kwargs)

    return decorated_function


# =====================================================
# USER AVAILABILITY
# =====================================================
def get_user_availability(user):
    availability = {}

    for av in user.availability:
        availability[av.day_of_week] = {
            'start': av.start_time.strftime('%H:%M') if av.start_time else None,
            'end': av.end_time.strftime('%H:%M') if av.end_time else None
        }

    return availability


# =====================================================
# TIME AVAILABILITY CHECK
# =====================================================
def check_time_availability(user, date, start_time, duration_minutes):
    from datetime import datetime, timedelta

    day_of_week = date.weekday()

    user_avail = next(
        (a for a in user.availability if a.day_of_week == day_of_week),
        None
    )

    if not user_avail:
        return False, "User not available on this day"

    try:
        start = datetime.strptime(start_time, '%H:%M').time()
    except ValueError:
        return False, "Invalid time format (HH:MM required)"

    end_time = (
        datetime.combine(date, start) + timedelta(minutes=duration_minutes)
    ).time()

    if user_avail.start_time and start < user_avail.start_time:
        return False, "Time outside available hours"

    if user_avail.end_time and end_time > user_avail.end_time:
        return False, "Time outside available hours"

    return True, "Available"


# =====================================================
# BOOKING CONFLICT CHECK
# =====================================================
def check_booking_conflicts(user_id, date, start_time, duration_minutes):
    from datetime import datetime, timedelta
    from app.models import Session

    try:
        session_start = datetime.strptime(
            f"{date} {start_time}",
            "%Y-%m-%d %H:%M"
        )
    except ValueError:
        return False, "Invalid date/time format"

    session_end = session_start + timedelta(minutes=duration_minutes)

    conflicting = Session.query.filter(
        ((Session.requester_id == user_id) |
         (Session.provider_id == user_id)),
        Session.status.in_(['pending', 'accepted']),
        Session.scheduled_start < session_end,
        Session.scheduled_end > session_start
    ).first()

    if conflicting:
        return False, "You have a conflicting session at this time"

    return True, "No conflicts"


# =====================================================
# BUSY SLOTS
# =====================================================
def get_user_busy_slots(user_id, date):
    from app.models import Session

    sessions = Session.query.filter(
        ((Session.requester_id == user_id) |
         (Session.provider_id == user_id)),
        Session.status.in_(['pending', 'accepted'])
    ).all()

    busy_slots = []

    for s in sessions:
        if s.scheduled_start and s.scheduled_end:
            if s.scheduled_start.date() == date:
                busy_slots.append({
                    "start": s.scheduled_start.time(),
                    "end": s.scheduled_end.time()
                })

    return busy_slots


# =====================================================
# ⭐ NEW: COMMON AVAILABILITY (FIXED MISSING IMPORT ISSUE)
# =====================================================
def get_common_availability(user1, user2):
    """
    Returns overlapping availability slots between two users
    """

    common = []

    for a1 in user1.availability:
        for a2 in user2.availability:

            if a1.day_of_week != a2.day_of_week:
                continue

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
# CREDIT RATES
# =====================================================
CREDIT_RATES = {
    '30': {'minutes': 30, 'credits': 25},
    '1h': {'minutes': 60, 'credits': 50},
    '2h': {'minutes': 120, 'credits': 100}
}