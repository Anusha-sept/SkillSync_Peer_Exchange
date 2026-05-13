from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user


def profile_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and not current_user.profile_completed:
            flash('Please complete your profile, add skills, and set availability to access this feature.', 'warning')
            return redirect(url_for('profile.edit'))
        return f(*args, **kwargs)
    return decorated_function


def get_user_availability(user):
    """Get user's availability as a dict for scheduling"""
    availability = {}
    for av in user.availability:
        availability[av.day_of_week] = {
            'start': av.start_time.strftime('%H:%M') if av.start_time else None,
            'end': av.end_time.strftime('%H:%M') if av.end_time else None
        }
    return availability


def check_time_availability(user, date, start_time, duration_minutes):
    """Check if user is available at the given time"""
    from datetime import time, datetime, timedelta
    
    day_of_week = date.weekday()
    user_avail = user.availability.filter_by(day_of_week=day_of_week).first()
    
    if not user_avail:
        return False, "User not available on this day"
    
    try:
        start = datetime.strptime(start_time, '%H:%M').time()
    except:
        return False, "Invalid time format"
    
    end_time = (datetime.combine(date, start) + timedelta(minutes=duration_minutes)).time()
    
    if start < user_avail.start_time or end_time > user_avail.end_time:
        return False, "Time outside available hours"
    
    return True, "Available"


def check_booking_conflicts(user_id, date, start_time, duration_minutes):
    """Check if user has any conflicting sessions"""
    from datetime import datetime, timedelta
    from app.models import Session
    
    try:
        session_start = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
    except:
        return False, "Invalid date/time"
    
    session_end = session_start + timedelta(minutes=duration_minutes)
    
    conflicting = Session.query.filter(
        ((Session.requester_id == user_id) | (Session.provider_id == user_id)),
        Session.status.in_(['pending', 'accepted']),
        Session.scheduled_start < session_end,
        Session.scheduled_end > session_start
    ).first()
    
    if conflicting:
        return False, "You have a conflicting session at this time"
    
    return True, "No conflicts"


CREDIT_RATES = {
    '30': {'minutes': 30, 'credits': 25},
    '1h': {'minutes': 60, 'credits': 50},
    '2h': {'minutes': 120, 'credits': 100}
}