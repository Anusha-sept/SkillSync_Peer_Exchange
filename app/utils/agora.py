import hashlib
import time
import os
from config import Config


class AgoraTokenGenerator:
    def __init__(self):
        self.app_id = Config.AGORA_APP_ID
        self.app_certificate = Config.AGORA_APP_CERTIFICATE
    
    def _generate_token(self, channel_name, uid, role, expire_time):
        expire = expire_time
        current_time = int(time.time())
        privilege_expired_ts = current_time + expire
        
        signature = self._generate_signature(
            channel_name,
            uid,
            role,
            privilege_expired_ts
        )
        
        return signature
    
    def _generate_signature(self, channel_name, uid, role, expire):
        app_id = self.app_id
        app_cert = self.app_certificate
        
        signature = hashlib.sha256(
            f"{app_id}{channel_name}{uid}{expire}{app_cert}".encode()
        ).hexdigest()
        
        return signature
    
    def generate_token(self, channel_name, uid=0, role='publisher', expire_time=3600):
        expire = expire_time
        current_time = int(time.time())
        privilege_expired_ts = current_time + expire
        
        signature = hashlib.sha256(
            f"{self.app_id}{channel_name}{uid}{privilege_expired_ts}{self.app_certificate}".encode()
        ).hexdigest()
        
        token = {
            'app_id': self.app_id,
            'channel': channel_name,
            'uid': uid,
            'token': signature,
            'privilege_expired_ts': privilege_expired_ts,
            'role': role
        }
        
        return token


def get_agora_token(channel_name, uid=0, role='publisher'):
    generator = AgoraTokenGenerator()
    return generator.generate_token(channel_name, uid, role)


def create_meeting_channel(session_id):
    return f"skillsync_{session_id}"


def can_join_session(session, user_id):
    from datetime import datetime, timedelta
    
    now = datetime.utcnow()
    session_start = session.scheduled_start
    session_end = session.scheduled_end
    
    five_min_before = session_start - timedelta(minutes=5)
    
    if now < five_min_before:
        return False, "Session will be available 5 minutes before start time"
    
    if now > session_end:
        return False, "Session has ended"
    
    if session.requester_id != user_id and session.provider_id != user_id:
        return False, "You are not authorized to join this session"
    
    return True, "Can join"


def get_session_duration_minutes(duration_option):
    duration_map = {
        '30': 30,
        '1h': 60,
        '2h': 120
    }
    return duration_map.get(str(duration_option), 60)


def calculate_credits(duration_minutes):
    if duration_minutes <= 30:
        return 25
    elif duration_minutes <= 60:
        return 50
    else:
        return 100