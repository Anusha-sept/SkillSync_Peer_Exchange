import os
from app import create_app, db
from app.models import Skill, User

def init_db():
    app = create_app()
    
    with app.app_context():
        db.create_all()
        
        default_skills = [
            ('Python', 'Programming', 'Learn Python programming from basics to advanced'),
            ('JavaScript', 'Programming', 'Web development with JavaScript'),
            ('Java', 'Programming', 'Object-oriented programming with Java'),
            ('C++', 'Programming', 'High-performance programming with C++'),
            ('React', 'Web Development', 'Frontend library for building UIs'),
            ('Node.js', 'Backend', 'Server-side JavaScript runtime'),
            ('SQL', 'Database', 'Database design and queries'),
            ('Machine Learning', 'AI', 'ML algorithms and applications'),
            ('Data Science', 'Analytics', 'Data analysis and visualization'),
            ('UI/UX Design', 'Design', 'User interface and experience design'),
            ('Graphic Design', 'Design', 'Visual design and branding'),
            ('Photography', 'Arts', 'Photography techniques and editing'),
            ('Video Editing', 'Media', 'Video post-production'),
            ('Content Writing', 'Writing', 'Blog and article writing'),
            ('Public Speaking', 'Soft Skills', 'Presentation and communication'),
            ('Time Management', 'Soft Skills', 'Productivity and organization'),
            ('Spanish', 'Languages', 'Spanish language learning'),
            ('French', 'Languages', 'French language learning'),
            ('Mandarin', 'Languages', 'Chinese language learning'),
            ('Guitar', 'Music', 'Musical instrument training'),
            ('Piano', 'Music', 'Keyboard instrument training'),
            ('Cooking', 'Lifestyle', 'Culinary skills and recipes'),
            ('Fitness', 'Health', 'Exercise and workout routines'),
            ('Yoga', 'Health', 'Mind-body practices'),
            ('Mathematics', 'Academics', 'Math concepts and problem solving'),
            ('Physics', 'Academics', 'Physical science fundamentals'),
        ]
        
        for name, category, description in default_skills:
            if not Skill.query.filter_by(name=name).first():
                skill = Skill(name=name, category=category, description=description)
                db.session.add(skill)
        
        db.session.commit()
        
        print("Database initialized with default skills!")

if __name__ == '__main__':
    init_db()