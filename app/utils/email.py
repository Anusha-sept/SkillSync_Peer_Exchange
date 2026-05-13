import os
import logging
from flask_mail import Message
from app import mail, db
from app.models import User, Session, Notification
from threading import Thread

logger = logging.getLogger(__name__)


def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
            logger.info(f"Email sent: {msg.subject}")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")


def send_email(subject, recipients, html_body, text_body=None):
    from flask import current_app

    if not isinstance(recipients, list):
        recipients = [recipients]

    msg = Message(subject, recipients=recipients, html=html_body, body=text_body)

    # Keep local development from crashing on SMTP/SSL issues.
    if current_app.config.get('DEBUG'):
        try:
            mail.send(msg)
            logger.info(f"Email sent in debug mode: {msg.subject}")
        except Exception as e:
            logger.warning(f"Email skipped in debug mode: {e}")
        return

    Thread(
        target=send_async_email,
        args=(current_app._get_current_object(), msg),
        daemon=True,
    ).start()


def send_welcome_email(user):
    subject = "Welcome to SkillSync Nexus! 🚀"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 20px; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; text-align: center; }}
            .header h1 {{ color: white; margin: 0; font-size: 32px; }}
            .content {{ padding: 40px; }}
            .button {{ display: inline-block; padding: 15px 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; border-radius: 50px; font-weight: bold; margin-top: 20px; }}
            .credits {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 20px; border-radius: 15px; text-align: center; margin: 20px 0; font-size: 24px; font-weight: bold; }}
            .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎓 SkillSync Nexus</h1>
            </div>
            <div class="content">
                <h2>Welcome, {user.first_name}!</h2>
                <p>We're thrilled to have you join SkillSync Nexus - the future of peer-to-peer skill exchange!</p>
                <div class="credits">🎁 You've received <strong>50 FREE CREDITS</strong> to start learning!</div>
                <p>Here's what you can do:</p>
                <ul>
                    <li>🎯 <strong>Offer your skills</strong> - Share what you're great at</li>
                    <li>📚 <strong>Learn new skills</strong> - Find perfect exchange partners</li>
                    <li>🎥 <strong>Video sessions</strong> - Connect via HD video calls</li>
                    <li>🏆 <strong>Earn achievements</strong> - Build your reputation</li>
                </ul>
                <a href="https://skillsync-nexus.onrender.com" class="button">Start Your Journey</a>
            </div>
            <div class="footer">
                <p>© 2024 SkillSync Nexus. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    send_email(subject, user.email, html)


def send_exchange_request_email(session):
    requester = session.requester
    provider = session.provider
    subject = f"📩 New Skill Exchange Request from {requester.first_name}"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 20px; overflow: hidden; box-shadow: 0 10px 40px rgba(0,0,0,0.1); }}
            .header {{ background: #667eea; padding: 30px; text-align: center; }}
            .content {{ padding: 30px; }}
            .details {{ background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0; }}
            .button {{ display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 25px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="color: white; margin: 0;">📩 Exchange Request</h2>
            </div>
            <div class="content">
                <p>Hi {provider.first_name},</p>
                <p><strong>{requester.first_name} {requester.last_name}</strong> wants to exchange skills with you!</p>
                <div class="details">
                    <p><strong>📅 Session:</strong> {session.scheduled_start.strftime('%B %d, %Y at %H:%M')}</p>
                    <p><strong>⏱️ Duration:</strong> {session.duration_minutes} minutes</p>
                    <p><strong>🎯 They'll learn:</strong> {session.provider_skill.name}</p>
                    <p><strong>📚 You'll learn:</strong> {session.requester_skill.name}</p>
                </div>
                <p>Log in to accept or decline this request.</p>
            </div>
        </div>
    </body>
    </html>
    """
    send_email(subject, provider.email, html)


def send_request_confirmation_email(session):
    requester = session.requester
    subject = "✅ Your Skill Exchange Request Sent!"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 20px; overflow: hidden; }}
            .header {{ background: #10b981; padding: 30px; text-align: center; }}
            .content {{ padding: 30px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="color: white; margin: 0;">✅ Request Sent!</h2>
            </div>
            <div class="content">
                <p>Hi {requester.first_name},</p>
                <p>Your skill exchange request has been sent to <strong>{session.provider.first_name} {session.provider.last_name}</strong>.</p>
                <p>We'll notify you when they respond!</p>
            </div>
        </div>
    </body>
    </html>
    """
    send_email(subject, requester.email, html)


def send_session_accepted_email(session):
    requester = session.requester
    provider = session.provider
    meet_link = f"/sessions/room/{session.id}"
    
    html_requester = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 20px; overflow: hidden; }}
            .header {{ background: #10b981; padding: 30px; text-align: center; }}
            .content {{ padding: 30px; }}
            .join-button {{ display: inline-block; padding: 15px 40px; background: #10b981; color: white; text-decoration: none; border-radius: 50px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="color: white; margin: 0;">🎉 Session Accepted!</h2>
            </div>
            <div class="content">
                <p>Great news! <strong>{provider.first_name}</strong> accepted your exchange request.</p>
                <p><strong>📅 Date:</strong> {session.scheduled_start.strftime('%B %d, %Y')}</p>
                <p><strong>⏰ Time:</strong> {session.scheduled_start.strftime('%H:%M')} - {session.scheduled_end.strftime('%H:%M')}</p>
                <p>Join 5 minutes before the scheduled time.</p>
                <a href="https://skillsync-nexus.onrender.com{meet_link}" class="join-button">Join Session</a>
            </div>
        </div>
    </body>
    </html>
    """
    send_email(f"🎉 Your Session with {provider.first_name} is Confirmed!", requester.email, html_requester)
    
    html_provider = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 20px; overflow: hidden; }}
            .header {{ background: #10b981; padding: 30px; text-align: center; }}
            .content {{ padding: 30px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="color: white; margin: 0;">🎉 Session Confirmed!</h2>
            </div>
            <div class="content">
                <p>You're all set! Your session with <strong>{requester.first_name}</strong> is confirmed.</p>
                <p><strong>📅 Date:</strong> {session.scheduled_start.strftime('%B %d, %Y')}</p>
                <p><strong>⏰ Time:</strong> {session.scheduled_start.strftime('%H:%M')} - {session.scheduled_end.strftime('%H:%M')}</p>
            </div>
        </div>
    </body>
    </html>
    """
    send_email(f"🎉 Your Session with {requester.first_name} is Confirmed!", provider.email, html_provider)


def send_session_rejected_email(session):
    requester = session.requester
    provider = session.provider
    subject = "😔 Session Request Declined"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 20px; overflow: hidden; }}
            .header {{ background: #ef4444; padding: 30px; text-align: center; }}
            .content {{ padding: 30px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="color: white; margin: 0;">Session Declined</h2>
            </div>
            <div class="content">
                <p>Hi {requester.first_name},</p>
                <p>Unfortunately, <strong>{provider.first_name}</strong> declined your exchange request.</p>
                <p>Don't worry! There are many other skilled learners waiting to connect with you.</p>
                <p>Keep exploring to find your perfect match!</p>
            </div>
        </div>
    </body>
    </html>
    """
    send_email(subject, requester.email, html)


def send_session_reminder_email(session, user):
    other_user = session.provider if user.id == session.requester_id else session.requester
    subject = "⏰ Session Reminder - Starting Soon!"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 20px; overflow: hidden; }}
            .header {{ background: #f59e0b; padding: 30px; text-align: center; }}
            .content {{ padding: 30px; }}
            .button {{ display: inline-block; padding: 15px 40px; background: #f59e0b; color: white; text-decoration: none; border-radius: 50px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="color: white; margin: 0;">⏰ 5-Minute Warning!</h2>
            </div>
            <div class="content">
                <p>Hi {user.first_name},</p>
                <p>Your session with <strong>{other_user.first_name}</strong> starts in 5 minutes!</p>
                <p><strong>📅 Date:</strong> {session.scheduled_start.strftime('%B %d, %Y')}</p>
                <p><strong>⏰ Time:</strong> {session.scheduled_start.strftime('%H:%M')}</p>
                <a href="https://skillsync-nexus.onrender.com/sessions/room/{session.id}" class="button">Join Now</a>
            </div>
        </div>
    </body>
    </html>
    """
    send_email(subject, user.email, html)


def send_session_completed_email(session):
    requester = session.requester
    provider = session.provider
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 20px; overflow: hidden; }}
            .header {{ background: #8b5cf6; padding: 30px; text-align: center; }}
            .content {{ padding: 30px; }}
            .button {{ display: inline-block; padding: 12px 30px; background: #8b5cf6; color: white; text-decoration: none; border-radius: 25px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="color: white; margin: 0;">🎉 Session Completed!</h2>
            </div>
            <div class="content">
                <p>Great job! Your skill exchange session is complete.</p>
                <p>Please take a moment to rate your experience and leave feedback.</p>
                <a href="https://skillsync-nexus.onrender.com/sessions/review/{session.id}" class="button">Leave Review</a>
            </div>
        </div>
    </body>
    </html>
    """
    send_email("🎉 Your Session is Complete!", requester.email, html)
    send_email("🎉 Your Session is Complete!", provider.email, html)


def send_review_reminder_email(session, user):
    other_user = session.provider if user.id == session.requester_id else session.requester
    subject = "⭐ How was your session?"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 20px; overflow: hidden; }}
            .header {{ background: #ec4899; padding: 30px; text-align: center; }}
            .content {{ padding: 30px; }}
            .button {{ display: inline-block; padding: 12px 30px; background: #ec4899; color: white; text-decoration: none; border-radius: 25px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="color: white; margin: 0;">⭐ Rate Your Experience</h2>
            </div>
            <div class="content">
                <p>Hi {user.first_name},</p>
                <p>How was your session with <strong>{other_user.first_name}</strong>?</p>
                <p>Your feedback helps build our community!</p>
                <a href="https://skillsync-nexus.onrender.com/sessions/review/{session.id}" class="button">Leave Review</a>
            </div>
        </div>
    </body>
    </html>
    """
    send_email(subject, user.email, html)


def send_certificate_email(user, certificate):
    subject = "🏆 Congratulations on Your Achievement!"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 20px; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }}
            .header {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 40px; text-align: center; }}
            .content {{ padding: 40px; text-align: center; }}
            .certificate {{ border: 3px solid #f5576c; padding: 30px; border-radius: 15px; margin: 20px 0; }}
            .button {{ display: inline-block; padding: 15px 40px; background: #f5576c; color: white; text-decoration: none; border-radius: 50px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="color: white; margin: 0;">🏆 Certificate Earned!</h1>
            </div>
            <div class="content">
                <p>Congratulations, <strong>{user.first_name}</strong>!</p>
                <div class="certificate">
                    <h3>{certificate.title}</h3>
                    <p>Total Credits: {certificate.credits_at_achievement}</p>
                    <p>Certificate Code: {certificate.certificate_code}</p>
                    <p>Issued: {certificate.issued_at.strftime('%B %d, %Y')}</p>
                </div>
                <a href="https://skillsync-nexus.onrender.com/profile/certificates" class="button">View Certificate</a>
            </div>
        </div>
    </body>
    </html>
    """
    send_email(subject, user.email, html)


def create_notification(user, title, message, notification_type, link=None):
    notification = Notification(
        user_id=user.id,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link
    )
    db.session.add(notification)
    db.session.commit()
    return notification
