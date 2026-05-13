from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user
from datetime import datetime


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

def get_user_availability(user_id):
    return []


def get_common_availability(user1, user2):
    return []


def check_time_availability(*args, **kwargs):
    return True, "OK"


def check_booking_conflicts(*args, **kwargs):
    return True, "OK"


def get_user_busy_slots(user_id, date):
    return []