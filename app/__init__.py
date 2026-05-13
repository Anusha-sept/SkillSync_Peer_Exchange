import os
import logging
from flask import Flask, g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from config import config

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
mail = Mail()
migrate = Migrate()
csrf = CSRFProtect()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def ensure_schema_updates():
    inspector = db.inspect(db.engine)
    user_columns = {column['name'] for column in inspector.get_columns('users')}
    with db.engine.begin() as connection:
        if 'timezone' not in user_columns:
            connection.exec_driver_sql("ALTER TABLE users ADD COLUMN timezone VARCHAR(100) DEFAULT 'UTC'")
        if 'profile_completed' not in user_columns:
            connection.exec_driver_sql("ALTER TABLE users ADD COLUMN profile_completed BOOLEAN DEFAULT FALSE")


@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.sessions import sessions_bp
    from app.routes.wallet import wallet_bp
    from app.routes.profile import profile_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(sessions_bp, url_prefix='/sessions')
    app.register_blueprint(wallet_bp, url_prefix='/wallet')
    app.register_blueprint(profile_bp, url_prefix='/profile')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    @app.context_processor
    def inject_models():
        from app.models import Notification
        return dict(Notification=Notification)
    
    @app.before_request
    def add_notifications():
        from app.models import Notification
        if current_user.is_authenticated:
            from flask import g
            g.notifications_menu = Notification.query.filter_by(
                user_id=current_user.id
            ).order_by(Notification.created_at.desc()).limit(5).all()
    
    with app.app_context():
        db.create_all()
        ensure_schema_updates()
        
        # Auto-create default skills
        from app.models import Skill
        default_skills = [
            ('Python', 'Programming'),
            ('JavaScript', 'Programming'),
            ('Java', 'Programming'),
            ('React', 'Web Development'),
            ('Node.js', 'Backend'),
            ('SQL', 'Database'),
            ('Machine Learning', 'AI'),
            ('Data Science', 'Analytics'),
            ('UI/UX Design', 'Design'),
            ('Graphic Design', 'Design'),
            ('Photography', 'Arts'),
            ('Video Editing', 'Media'),
            ('Content Writing', 'Writing'),
            ('Public Speaking', 'Soft Skills'),
            ('Spanish', 'Languages'),
            ('French', 'Languages'),
            ('Guitar', 'Music'),
            ('Cooking', 'Lifestyle'),
            ('Fitness', 'Health'),
            ('Yoga', 'Health'),
        ]
        for name, category in default_skills:
            if not Skill.query.filter_by(name=name).first():
                skill = Skill(name=name, category=category)
                db.session.add(skill)
        db.session.commit()
        
        from app.utils.scheduler import init_scheduler
        init_scheduler(app)
    
    return app
