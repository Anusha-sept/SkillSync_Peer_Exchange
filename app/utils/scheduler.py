import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from app import db
from app.models import Session, User
from app.utils.email import send_session_reminder_email, send_session_completed_email, send_review_reminder_email
from app.utils.email import create_notification

logger = logging.getLogger(__name__)


def check_pending_sessions():
    try:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        pending_sessions = Session.query.filter(
            Session.status == 'pending',
            Session.created_at < cutoff
        ).all()
        
        for session in pending_sessions:
            session.status = 'expired'
            logger.info(f"Session {session.id} expired due to no response")
        
        if pending_sessions:
            db.session.commit()
    except Exception as e:
        logger.error(f"Error in check_pending_sessions: {e}")


def check_upcoming_sessions_for_reminder():
    now = datetime.utcnow()
    five_min_later = now + timedelta(minutes=5)
    
    sessions = Session.query.filter(
        Session.status == 'accepted',
        Session.scheduled_start >= now,
        Session.scheduled_start <= five_min_later
    ).all()
    
    for session in sessions:
        if not hasattr(session, '_reminder_sent'):
            requester = session.requester
            provider = session.provider
            
            send_session_reminder_email(session, requester)
            send_session_reminder_email(session, provider)
            
            create_notification(
                requester,
                "Session Starting Soon",
                f"Your session with {provider.first_name} starts in 5 minutes!",
                'session_reminder',
                f'/sessions/room/{session.id}'
            )
            create_notification(
                provider,
                "Session Starting Soon",
                f"Your session with {requester.first_name} starts in 5 minutes!",
                'session_reminder',
                f'/sessions/room/{session.id}'
            )
            
            session._reminder_sent = True
            db.session.commit()
            logger.info(f"Reminders sent for session {session.id}")


def check_completed_sessions():
    now = datetime.utcnow()
    
    sessions = Session.query.filter(
        Session.status == 'accepted',
        Session.scheduled_end < now
    ).all()
    
    for session in sessions:
        session.status = 'completed'
        session.completed_at = datetime.utcnow()
        
        requester = session.requester
        provider = session.provider
        
        requester.credits += session.credits_amount
        provider.credits += session.credits_amount
        
        requester.total_credits_earned += session.credits_amount
        provider.total_credits_earned += session.credits_amount
        
        send_session_completed_email(session)
        
        create_notification(
            requester,
            "Session Completed!",
            f"Your session with {provider.first_name} is complete. You earned {session.credits_amount} credits!",
            'session_complete',
            f'/sessions/review/{session.id}'
        )
        create_notification(
            provider,
            "Session Completed!",
            f"Your session with {requester.first_name} is complete. You earned {session.credits_amount} credits!",
            'session_complete',
            f'/sessions/review/{session.id}'
        )
        
        logger.info(f"Session {session.id} completed, credits transferred")
    
    if sessions:
        db.session.commit()


def send_review_reminders():
    completed_cutoff = datetime.utcnow() - timedelta(days=1)
    
    sessions = Session.query.filter(
        Session.status == 'completed',
        Session.completed_at >= completed_cutoff
    ).all()
    
    for session in sessions:
        requester_reviewed = any(r.reviewer_id == session.requester_id for r in session.reviews)
        provider_reviewed = any(r.reviewer_id == session.provider_id for r in session.reviews)
        
        if not requester_reviewed:
            send_review_reminder_email(session, session.requester)
        if not provider_reviewed:
            send_review_reminder_email(session, session.provider)
    
    logger.info("Review reminders sent")


def init_scheduler(app):
    scheduler = BackgroundScheduler()
    
    scheduler.add_job(
        check_pending_sessions,
        'interval',
        hours=1,
        id='check_pending_sessions'
    )
    
    scheduler.add_job(
        check_upcoming_sessions_for_reminder,
        'interval',
        minutes=1,
        id='check_upcoming_sessions'
    )
    
    scheduler.add_job(
        check_completed_sessions,
        'interval',
        minutes=1,
        id='check_completed_sessions'
    )
    
    scheduler.add_job(
        send_review_reminders,
        'interval',
        hours=24,
        id='send_review_reminders'
    )
    
    scheduler.start()
    logger.info("Scheduler started")
    
    return scheduler