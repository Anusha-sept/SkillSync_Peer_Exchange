from datetime import datetime
from flask_login import UserMixin
from app import db, bcrypt


user_skills = db.Table('user_skills',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('skill_id', db.Integer, db.ForeignKey('skills.id'), primary_key=True)
)

user_wanted_skills = db.Table('user_wanted_skills',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('skill_id', db.Integer, db.ForeignKey('skills.id'), primary_key=True)
)


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    avatar = db.Column(db.String(500), default='default.png')
    bio = db.Column(db.Text)
    experience_level = db.Column(db.String(50), default='beginner')
    timezone = db.Column(db.String(100), default='UTC')
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_online = db.Column(db.Boolean, default=False)
    credits = db.Column(db.Integer, default=50)
    total_credits_earned = db.Column(db.Integer, default=0)
    profile_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    offered_skills = db.relationship('Skill', secondary=user_skills, back_populates='users_offering')
    wanted_skills = db.relationship('Skill', secondary=user_wanted_skills, back_populates='users_wanting')
    
    sessions_as_requester = db.relationship('Session', foreign_keys='Session.requester_id', back_populates='requester', lazy='dynamic')
    sessions_as_provider = db.relationship('Session', foreign_keys='Session.provider_id', back_populates='provider', lazy='dynamic')
    
    wallet_transactions = db.relationship('WalletTransaction', back_populates='user', lazy='dynamic')
    
    reviews_given = db.relationship('Review', foreign_keys='Review.reviewer_id', back_populates='reviewer', lazy='dynamic')
    reviews_received = db.relationship('Review', foreign_keys='Review.reviewed_id', back_populates='reviewed', lazy='dynamic')
    
    notifications = db.relationship('Notification', back_populates='user', lazy='dynamic')
    
    availability = db.relationship('Availability', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    
    certificates = db.relationship('Certificate', back_populates='user', lazy='dynamic')
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def average_rating(self):
        reviews = Review.query.filter_by(reviewed_id=self.id).all()
        if not reviews:
            return 0
        return sum(r.rating for r in reviews) / len(reviews)
    
    @property
    def achievement_title(self):
        if self.total_credits_earned >= 500:
            return 'Master Collaborator'
        elif self.total_credits_earned >= 300:
            return 'Expert'
        elif self.total_credits_earned >= 150:
            return 'Mentor'
        elif self.total_credits_earned >= 50:
            return 'Skilled'
        return 'Beginner'
    
    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Skill(db.Model):
    __tablename__ = 'skills'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    category = db.Column(db.String(100))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    users_offering = db.relationship('User', secondary=user_skills, back_populates='offered_skills')
    users_wanting = db.relationship('User', secondary=user_wanted_skills, back_populates='wanted_skills')
    
    def __repr__(self):
        return f'<Skill {self.name}>'


class UserSkillPreference(db.Model):
    __tablename__ = 'user_skill_preferences'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id'), nullable=False)
    duration_minutes = db.Column(db.Integer, default=60)
    credits = db.Column(db.Integer, default=50)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('skill_preferences', lazy='dynamic', cascade='all, delete-orphan'))
    skill = db.relationship('Skill')
    
    __table_args__ = (db.UniqueConstraint('user_id', 'skill_id', name='unique_user_skill'),)
    
    def __repr__(self):
        return f'<UserSkillPreference user={self.user_id} skill={self.skill_id}>'


class Availability(db.Model):
    __tablename__ = 'availability'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    
    user = db.relationship('User', back_populates='availability')
    
    def __repr__(self):
        return f'<Availability user_id={self.user_id} day={self.day_of_week}>'


class Session(db.Model):
    __tablename__ = 'sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    requester_skill_id = db.Column(db.Integer, db.ForeignKey('skills.id'), nullable=False)
    provider_skill_id = db.Column(db.Integer, db.ForeignKey('skills.id'), nullable=False)
    
    scheduled_start = db.Column(db.DateTime, nullable=False)
    scheduled_end = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    credits_amount = db.Column(db.Integer, nullable=False)
    
    status = db.Column(db.String(20), default='pending')
    agora_channel = db.Column(db.String(100))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    requester = db.relationship('User', foreign_keys=[requester_id], back_populates='sessions_as_requester')
    provider = db.relationship('User', foreign_keys=[provider_id], back_populates='sessions_as_provider')
    
    requester_skill = db.relationship('Skill', foreign_keys=[requester_skill_id])
    provider_skill = db.relationship('Skill', foreign_keys=[provider_skill_id])
    
    reviews = db.relationship('Review', back_populates='session', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Session {self.id} status={self.status}>'


class WalletTransaction(db.Model):
    __tablename__ = 'wallet_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(255))
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', back_populates='wallet_transactions')
    session = db.relationship('Session')
    
    def __repr__(self):
        return f'<WalletTransaction {self.id} {self.transaction_type}>'


class Review(db.Model):
    __tablename__ = 'reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewed_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    session = db.relationship('Session', back_populates='reviews')
    reviewer = db.relationship('User', foreign_keys=[reviewer_id], back_populates='reviews_given')
    reviewed = db.relationship('User', foreign_keys=[reviewed_id], back_populates='reviews_received')
    
    def __repr__(self):
        return f'<Review {self.id} rating={self.rating}>'


class Certificate(db.Model):
    __tablename__ = 'certificates'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    credits_at_achievement = db.Column(db.Integer, nullable=False)
    certificate_code = db.Column(db.String(50), unique=True, nullable=False)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', back_populates='certificates')
    
    def __repr__(self):
        return f'<Certificate {self.title}>'


class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    link = db.Column(db.String(255))
    
    user = db.relationship('User', back_populates='notifications')
    
    def __repr__(self):
        return f'<Notification {self.id}>'


class AdminLog(db.Model):
    __tablename__ = 'admin_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AdminLog {self.id} {self.action}>'
