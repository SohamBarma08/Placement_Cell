from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


# ------------------ User Model ------------------
class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(25), nullable=False)
    email = db.Column(db.String(25), unique=True, nullable=False)
    phone = db.Column(db.String(25), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    user_type = db.Column(db.String(10), nullable=False)
    cv_url = db.Column(db.String(500))
    cv_filename = db.Column(db.String(200))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# ------------------ Job Model ------------------
class Job(db.Model):
    __tablename__ = 'job'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    company = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    salary = db.Column(db.String(50), nullable=True)
    posted_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # ForeignKey to User table
    user = db.relationship('User', backref=db.backref('jobs', lazy=True))
    posted_on = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    #Filters for Minimum Requirements
    min_class_10_marks = db.Column(db.Float, nullable=True)
    min_class_12_marks = db.Column(db.Float, nullable=True)
    min_university_marks = db.Column(db.Float, nullable=True)
    required_field_of_study = db.Column(db.Text, nullable=True)
    required_stream_of_study = db.Column(db.Text, nullable=True)
    
# ------------------ Application Model ------------------ 
class Application(db.Model):
    __tablename__ = 'application'
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    applied_on = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.String(20), default="Pending")
    ats_score = db.Column(db.Float)

    # Relationships
    job = db.relationship('Job', backref=db.backref('applications', lazy=True))
    student = db.relationship('User', backref=db.backref('applications', lazy=True))

# ------------------ Education Model ------------------
class Education(db.Model):
    __tablename__ = 'education'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    class_10_marks = db.Column(db.String(10))
    class_12_marks = db.Column(db.String(10))
    university_marks = db.Column(db.String(10))
    field_of_study = db.Column(db.String(100))
    stream_of_studies = db.Column(db.String(100))

    student = db.relationship('User', backref=db.backref('education', uselist=False))
