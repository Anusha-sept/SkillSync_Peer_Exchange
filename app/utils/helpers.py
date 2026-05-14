from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user
from datetime import datetime
from app import db


# =====================================================
# PROFILE REQUIRED DECORATOR
# =====================================================
def profile_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))

        # adjust based on your DB field
        if hasattr(current_user, "profile_completed"):
            if not current_user.profile_completed:
                flash("Please complete your profile first", "warning")
                return redirect(url_for("profile.edit"))

        return f(*args, **kwargs)
    return decorated_function


# =====================================================
# PLACEHOLDER (TEMP SAFE FUNCTIONS)
# =====================================================

DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

def get_user_availability(user_id):
    from app.models import Availability
    from datetime import time
    availabilities = Availability.query.filter_by(user_id=user_id).all()
    result = []
    for a in availabilities:
        start = a.start_time if isinstance(a.start_time, time) else a.start_time
        end = a.end_time if isinstance(a.end_time, time) else a.end_time
        result.append({
            'day': DAY_NAMES[a.day_of_week],
            'day_of_week': a.day_of_week,
            'start': start.strftime('%H:%M'),
            'end': end.strftime('%H:%M'),
            'start_str': start.strftime('%H:%M'),
            'end_str': end.strftime('%H:%M')
        })
    return result


def get_common_availability(user1, user2):
    from datetime import time
    user1_avail = get_user_availability(user1.id)
    user2_avail = get_user_availability(user2.id)
    
    common = []
    for slot1 in user1_avail:
        for slot2 in user2_avail:
            if slot1['day_of_week'] == slot2['day_of_week']:
                start1 = time(int(slot1['start'].split(':')[0]), int(slot1['start'].split(':')[1]))
                end1 = time(int(slot1['end'].split(':')[0]), int(slot1['end'].split(':')[1]))
                start2 = time(int(slot2['start'].split(':')[0]), int(slot2['start'].split(':')[1]))
                end2 = time(int(slot2['end'].split(':')[0]), int(slot2['end'].split(':')[1]))
                start = max(start1, start2)
                end = min(end1, end2)
                if start < end:
                    common.append({
                        'day': slot1['day'],
                        'day_of_week': slot1['day_of_week'],
                        'start': start.strftime('%H:%M'),
                        'end': end.strftime('%H:%M'),
                        'start_str': start.strftime('%H:%M'),
                        'end_str': end.strftime('%H:%M')
                    })
    return common


def check_time_availability(*args, **kwargs):
    return True, "OK"


def check_booking_conflicts(user_id, date, time, duration):
    from app.models import Session
    from datetime import datetime, timedelta
    try:
        time_obj = datetime.strptime(time, '%H:%M').time()
        start_dt = datetime.combine(date, time_obj)
        end_dt = start_dt + timedelta(minutes=duration)
        
        conflicts = Session.query.filter(
            ((Session.requester_id == user_id) | (Session.provider_id == user_id)),
            Session.status.in_(['pending', 'accepted']),
            Session.scheduled_start < end_dt,
            Session.scheduled_end > start_dt
        ).first()
        
        if conflicts:
            return False, "You have a conflicting session at this time"
        return True, "OK"
    except Exception as e:
        return True, "OK"


def get_user_busy_slots(user_id, date):
    from app.models import Session
    from datetime import datetime, timedelta
    
    sessions = Session.query.filter(
        ((Session.requester_id == user_id) | (Session.provider_id == user_id)),
        Session.status.in_(['pending', 'accepted']),
        db.func.date(Session.scheduled_start) == date
    ).all()
    
    busy = []
    for s in sessions:
        busy.append((s.scheduled_start.time(), s.scheduled_end.time()))
    return busy