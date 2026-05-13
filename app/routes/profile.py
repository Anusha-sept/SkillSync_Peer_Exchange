from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from app import db, config
from app.models import User, Skill, Availability, Certificate, UserSkillPreference

profile_bp = Blueprint('profile', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Credit rates constant
CREDIT_OPTIONS = [
    {'value': '30', 'label': '30 min', 'credits': 25},
    {'value': '60', 'label': '1 hour', 'credits': 50},
    {'value': '120', 'label': '2 hours', 'credits': 100},
]


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@profile_bp.route('/<username>')
def view(username):
    user = User.query.filter_by(username=username).first_or_404()
    
    sessions_as_requester = user.sessions_as_requester.filter_by(status='completed').count()
    sessions_as_provider = user.sessions_as_provider.filter_by(status='completed').count()
    total_sessions = sessions_as_requester + sessions_as_provider
    
    return render_template('profile/view.html', profile_user=user, total_sessions=total_sessions)


@profile_bp.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    try:
        if request.method == 'POST':
            # Save basic profile info
            current_user.first_name = request.form.get('first_name', '').strip()
            current_user.last_name = request.form.get('last_name', '').strip()
            current_user.bio = request.form.get('bio', '').strip()
            current_user.experience_level = request.form.get('experience_level', 'beginner')
            current_user.timezone = request.form.get('timezone', current_user.timezone or 'UTC')
            
            # Validate required fields
            if not current_user.first_name or not current_user.last_name:
                flash('Please enter your first and last name.', 'danger')
                return redirect(url_for('profile.edit'))
            
            # Handle avatar upload
            if 'avatar' in request.files:
                file = request.files['avatar']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"{current_user.id}_{file.filename}")
                    upload_folder = config.Config.UPLOAD_FOLDER
                    os.makedirs(upload_folder, exist_ok=True)
                    file.save(os.path.join(upload_folder, filename))
                    current_user.avatar = filename
            
            # Get offered and wanted skills
            offered_skills = request.form.getlist('offered_skills')
            wanted_skills = request.form.getlist('wanted_skills')
            
            if not offered_skills:
                flash('Please select at least one skill you can teach.', 'warning')
                return redirect(url_for('profile.edit'))
            
            # Update offered skills
            current_user.offered_skills = []
            for skill_id in offered_skills:
                skill = Skill.query.get(int(skill_id))
                if skill:
                    current_user.offered_skills.append(skill)
                    
                    # Save/update skill preference with duration and credits
                    duration = request.form.get(f'duration_{skill_id}', '60')
                    credits = request.form.get(f'credits_{skill_id}', '50')
                    
                    preference = UserSkillPreference.query.filter_by(
                        user_id=current_user.id,
                        skill_id=int(skill_id)
                    ).first()
                    
                    if preference:
                        preference.duration_minutes = int(duration)
                        preference.credits = int(credits)
                    else:
                        preference = UserSkillPreference(
                            user_id=current_user.id,
                            skill_id=int(skill_id),
                            duration_minutes=int(duration),
                            credits=int(credits)
                        )
                        db.session.add(preference)
            
            # Update wanted skills
            current_user.wanted_skills = []
            for skill_id in wanted_skills:
                skill = Skill.query.get(int(skill_id))
                if skill:
                    current_user.wanted_skills.append(skill)
            
            # Mark profile as complete
            current_user.profile_completed = True
            
            db.session.commit()
            
            flash('Profile saved! Now set your availability to start exchanging skills.', 'success')
            return redirect(url_for('profile.availability'))
        
        # Get all skills
        skills = Skill.query.all()
        
        # Get user's current skill preferences
        user_preferences = {}
        for pref in current_user.skill_preferences:
            user_preferences[pref.skill_id] = {
                'duration': pref.duration_minutes,
                'credits': pref.credits
            }
        
        # Get user's current offered and wanted skill IDs
        offered_ids = [s.id for s in current_user.offered_skills]
        wanted_ids = [s.id for s in current_user.wanted_skills]
        
        # Get user's availability
        user_availability = {}
        for av in current_user.availability:
            user_availability[av.day_of_week] = {
                'start': av.start_time.strftime('%H:%M') if av.start_time else '',
                'end': av.end_time.strftime('%H:%M') if av.end_time else ''
            }
        
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        return render_template('profile/edit.html', 
                             skills=skills,
                             credit_options=CREDIT_OPTIONS,
                             user_preferences=user_preferences,
                             offered_ids=offered_ids,
                             wanted_ids=wanted_ids,
                             availability=user_availability,
                             days=days)
                             
    except Exception as e:
        print(f"Error in profile edit: {e}")
        db.session.rollback()
        flash(f'Error saving profile: {str(e)}', 'danger')
        return redirect(url_for('main.dashboard'))


@profile_bp.route('/availability', methods=['GET', 'POST'])
@login_required
def availability():
    try:
        if request.method == 'POST':
            # Save availability
            Availability.query.filter_by(user_id=current_user.id).delete()
            current_user.timezone = request.form.get('timezone', current_user.timezone or 'UTC')
            
            available_days = 0
            for day in range(7):
                is_available = request.form.get(f'available_{day}')
                start_time = request.form.get(f'start_{day}')
                end_time = request.form.get(f'end_{day}')
                
                if is_available and start_time and end_time:
                    parsed_start = datetime.strptime(start_time, '%H:%M').time()
                    parsed_end = datetime.strptime(end_time, '%H:%M').time()
                    if parsed_end <= parsed_start:
                        flash(f'End time must be after start time for day {day + 1}.', 'warning')
                        return redirect(url_for('profile.availability'))
                    availability = Availability(
                        user_id=current_user.id,
                        day_of_week=day,
                        start_time=parsed_start,
                        end_time=parsed_end
                    )
                    db.session.add(availability)
                    available_days += 1
            
            db.session.commit()
            
            if available_days == 0:
                flash('Please set at least one available day.', 'warning')
                return redirect(url_for('profile.availability'))
            
            flash('🎉 Profile complete! You can now find exchange partners and book sessions!', 'success')
            return redirect(url_for('main.dashboard'))
        
        user_availability = {}
        for av in current_user.availability:
            user_availability[av.day_of_week] = {
                'start': av.start_time.strftime('%H:%M') if av.start_time else '',
                'end': av.end_time.strftime('%H:%M') if av.end_time else ''
            }
        
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        return render_template('profile/availability.html', 
                             days=days, 
                             availability=user_availability,
                             selected_timezone=current_user.timezone or 'UTC')
    except Exception as e:
        print(f"Error in availability: {e}")
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('profile.edit'))


@profile_bp.route('/certificates')
@login_required
def certificates():
    certificates = current_user.certificates.order_by('issued_at desc').all()
    return render_template('profile/certificates.html', certificates=certificates)


@profile_bp.route('/certificate/<int:cert_id>')
@login_required
def view_certificate(cert_id):
    certificate = Certificate.query.get_or_404(cert_id)
    if certificate.user_id != current_user.id:
        flash('You are not authorized to view this certificate.', 'danger')
        return redirect(url_for('profile.certificates'))
    
    return render_template('profile/certificate_view.html', certificate=certificate)


@profile_bp.route('/skills/manage', methods=['GET', 'POST'])
@login_required
def manage_skills():
    if request.method == 'POST':
        skill_name = request.form.get('skill_name')
        category = request.form.get('category')
        
        existing_skill = Skill.query.filter_by(name=skill_name).first()
        if existing_skill:
            flash('Skill already exists!', 'warning')
            return redirect(url_for('profile.manage_skills'))
        
        skill = Skill(name=skill_name, category=category)
        db.session.add(skill)
        db.session.commit()
        
        flash(f'Skill "{skill_name}" created!', 'success')
        return redirect(url_for('profile.manage_skills'))
    
    skills = Skill.query.all()
    return render_template('profile/skills_manage.html', skills=skills)
