from flask import Flask, request, render_template, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os, smtplib, webbrowser

# === Flask App Config ===
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'Hello')

# === Database Config ===
database_url = os.environ.get('DATABASE_URL')

# Render / Railway fixes postgres:// → postgresql://
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# Use Postgres (preferred) or fallback only if missing
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///TrackMyCredits.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# === MODELS ===
class User(db.Model):
    _tablename_ = 'users'
    username = db.Column(db.String(120), primary_key=True)
    password = db.Column(db.String(255), nullable=False)
    courses = db.relationship('Course', backref='user', lazy=True)

class Course(db.Model):
    _tablename_ = 'courses'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(120), db.ForeignKey('users.username'), nullable=False)
    category = db.Column(db.String(50))
    course_name = db.Column(db.String(255), nullable=False)
    credits = db.Column(db.Integer, nullable=False)
    grade = db.Column(db.String(10))

class ContactMessage(db.Model):
    _tablename_ = 'contact_messages'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100))
    batch = db.Column(db.String(50))
    branch = db.Column(db.String(50))
    email = db.Column(db.String(120))
    contact = db.Column(db.String(20))
    feedback = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, server_default=db.func.now())

# === EMAIL SENDER ===
def send_email(recipient):
    sender = "trackmycredits.devteam@gmail.com"
    password = "hpsm vznm npno waat"  # App Password
    subject = "Welcome to Track My Credits – Registration Successful!"
    message = f"Hello {recipient},\n\nThank you for registering with Track My Credits.\nYou can now log in and track your academic credits.\n"
    email_message = f"Subject: {subject}\n\n{message}"

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipient, email_message)
        print(f"✅ Email sent to {recipient}")
    except Exception as e:
        print(f"❌ Email error: {e}")

# === Credit Categories ===
CATEGORIES = [
    {"code": "ec", "title": "Experiential Core", "total": 16},
    {"code": "ee", "title": "Experiential Electives", "total": 8},
    {"code": "fc", "title": "Foundation Core", "total": 44},
    {"code": "ho", "title": "Honours", "total": 20},
    {"code": "mi", "title": "Minors", "total": 20},
    {"code": "pc", "title": "Program Core", "total": 52},
    {"code": "pe", "title": "Program Electives", "total": 24},
    {"code": "ue", "title": "University Electives", "total": 16},
]

# === ROUTES ===
@app.route('/')
def Home():
    return render_template('index.html')
@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        msg = ContactMessage(
            name=request.form.get('name'),
            batch=request.form.get('batch'),
            branch=request.form.get('branch'),
            email=request.form.get('email'),
            contact=request.form.get('contact'),
            feedback=request.form.get('feedback')
        )
        db.session.add(msg)
        db.session.commit()
        flash("✅ Feedback submitted successfully!")
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user'] = username
            return redirect(url_for('personalized'))
        else:
            flash("❌ Incorrect email or password.")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('email')
        password = generate_password_hash(request.form.get('password'))

        if User.query.filter_by(username=username).first():
            flash("⚠ User already exists.")
            return redirect(url_for('register'))

        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        send_email(username)

        flash("✅ Registration successful! Please log in.")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/personalized')
def personalized():
    if 'user' not in session:
        flash("⚠ Please log in first.")
        return redirect(url_for('login'))

    username = session['user']
    courses = Course.query.filter_by(username=username).all()

    course_dict = {}
    for course in courses:
        course_dict.setdefault(course.category, []).append(course)

    total_earned = 0
    for cat in CATEGORIES:
        code = cat['code']
        earned = sum(c.credits for c in course_dict.get(code, []))
        cat['earned'] = earned
        cat['remaining'] = cat['total'] - earned
        cat['percent'] = round((earned / cat['total']) * 100) if cat['total'] else 0
        total_earned += earned

    total_possible = sum(cat['total'] for cat in CATEGORIES)
    percent_complete = round((total_earned / total_possible) * 100)

    return render_template('personalized.html',
                           username=username,
                           categories=CATEGORIES,
                           total_credits_earned=total_earned,
                           total_credits_remaining=total_possible - total_earned,
                           percentage_complete=percent_complete)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('Home'))

@app.route('/add_course', methods=['POST'])
def add_course():
    if 'user' not in session:
        flash("⚠ Please log in first.")
        return redirect(url_for('login'))

    new_course = Course(
        username=session['user'],
        category=request.form.get('category_code'),
        course_name=request.form.get('course_name'),
        credits=request.form.get('course_credits'),
        grade=request.form.get('course_grade')
    )
    db.session.add(new_course)
    db.session.commit()
    return redirect(url_for('personalized'))

@app.route('/delete_course', methods=['POST'])
def delete_course():
    if 'user' not in session:
        return jsonify({"success": False, "error": "Not logged in"})

    data = request.get_json()
    course = Course.query.filter_by(
        username=session['user'],
        category=data.get('category'),
        course_name=data.get('course_name')
    ).first()

    if not course:
        return jsonify({"success": False, "error": "Course not found"})

    db.session.delete(course)
    db.session.commit()
    return jsonify({"success": True})
# === TEMPORARY INITIALIZER (Use Once, Then Delete) ===
@app.route('/initdb')
def initdb():
    with app.app_context():
        db.create_all()
    return "✅ Database tables created successfully!"

# === MAIN APP ENTRY FOR RENDER ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))