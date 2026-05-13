from datetime import datetime, timedelta


# =====================================================
# SAFE STUBS (PREVENT RENDER CRASH)
# =====================================================

def get_user_busy_slots(user_id, date):
    return []


def get_common_availability(user1, user2):
    return []


def check_time_availability(*args, **kwargs):
    return True, "OK"


def check_booking_conflicts(user_id, date, time, duration):
    return True, "OK"