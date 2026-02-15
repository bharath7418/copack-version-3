from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

import subprocess, uuid, os
import os
from flask_migrate import Migrate
from flask import request



app = Flask(__name__)
app.config['SECRET_KEY'] = 'pro_secret_key_99'

raw_db_url = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_DATABASE_URI'] = raw_db_url.replace("postgres://", "postgresql://", 1) if raw_db_url else 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'student_login'
# ... after db = SQLAlchemy(app) ...
migrate = Migrate(app, db)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(50))


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    content = db.Column(db.Text)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.String(10), unique=True)
    title = db.Column(db.String(100))
    description = db.Column(db.Text)
    input_format = db.Column(db.Text)
    constraints = db.Column(db.Text)
    output_format = db.Column(db.Text)
    explanation = db.Column(db.Text)
    difficulty = db.Column(db.String(50))
    
    # This links the Question to multiple rows in the TestCase table
    test_cases = db.relationship('TestCase', backref='question', cascade="all, delete-orphan")

class TestCase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    input_data = db.Column(db.Text)
    expected_output = db.Column(db.Text)
    # Foreign Key linking back to Question.id
    question_root_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    
 
class Student(UserMixin, db.Model):
    # Fixed primary_key typo (lowercase 'y')
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    username = db.Column(db.String(15), unique=True) # Good idea to make this unique
    password = db.Column(db.String(100)) 
    department = db.Column(db.String(60))
    year = db.Column(db.String(60))
    solved = db.Column(db.Integer)
    rating = db.Column(db.Integer)
    badge = db.Column(db.String(20))

@login_manager.user_loader
def load_user(user_id):
    student = Student.query.get(int(user_id))
    if student:
        return student
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()
    if not Student.query.filter_by(username='username').first():
        db.session.add(Student(username='username', password='password'))
        db.session.commit()
    
    
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()
    # Initial Student
    if not Student.query.filter_by(username='username').first():
        db.session.add(Student(username='username', password='password', name="Default Student"))
    
    # Initial Admin
    if not User.query.filter_by(username='arun').first():
        db.session.add(User(username='arun', password='arun123'))
        
    db.session.commit()
    
    
    
@app.route('/')
def home():
    return render_template('start_page.html')




@app.route('/student_signup', methods=['GET', 'POST'])
def student_signup():
    if request.method == 'POST':
        # Create a small helper to handle empty strings
        def safe_int(value, default=0):
            if value and value.strip():
                try:
                    return int(value)
                except ValueError:
                    return default
            return default

        new_student = Student(
            name=request.form.get('name'),
            username=request.form.get('username'),
            password=request.form.get('password'),
            department=request.form.get('department'),
            email = request.form.get('email'),
            # Wrap numeric fields in safe_int
            year=safe_int(request.form.get('year')),
            solved=safe_int(request.form.get('solved')),
            rating=safe_int(request.form.get('rating')),
            badge=request.form.get('badge')
        )
        
        db.session.add(new_student)
        db.session.commit()
        return redirect(url_for('student_login'))
    
    return render_template('student_signup.html')        


@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    # If the user is already logged in, don't show the login page
    if current_user.is_authenticated:
        return redirect(url_for('student_problem_view'))
    if request.method == 'POST':
        user_in = request.form.get('username')
        pass_in = request.form.get('password')

        student = Student.query.filter_by(username=user_in).first()

        if student and student.password == pass_in:
            login_user(student)
            
            next_page = request.args.get('next')
            
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('student_problem_view')
                
            flash(f"Welcome, {student.name}!", "success")
            return redirect(next_page)
        else:
            flash("Invalid username or password.", "danger")

    return render_template('student_login.html')


@app.route('/student_problem_view',methods = ['GET','POST'])
def student_problem_view() :
    
    questions = Question.query.all()
    student = Student.query.all()
    return render_template("student_problem_view.html", questions=questions)

@app.route('/student_profile/<string:username>',methods=['GET','POST'])
def student_profile(username):
    # Use filter_by because username is not the Primary Key
    student = Student.query.filter_by(username=username).first_or_404()
    return render_template('student_profile.html', student=student)


@app.route('/solve_and_compiler_page/<int:id>')
def solve_and_compiler_page(id):
    q = Question.query.get_or_404(id)
    test_cases = TestCase.query.all()
    # REMOVE: cases = json.loads(q.test_cases) <--- This was the cause of the error
    
    return render_template('solve_and_compiler_page.html', q=q, test_cases=test_cases)

  
@app.route('/admin')
@login_required
def admin_panel():
    messages = Message.query.all()
    questions = Question.query.all()
    return render_template('admin.html',  messages=messages, questions=questions)


@app.route('/admin/question_add', methods=['POST'])
def admin_question_add():
    if request.method == 'POST':
        # 1. Create the Question
        new_q = Question(
            question_id=request.form.get('question_id'),
            title=request.form.get('title'),
            description=request.form.get('description'),
            input_format=request.form.get('input_format'),
            constraints=request.form.get('constraints'),
            output_format=request.form.get('output_format'),
            explanation=request.form.get('explanation'),
            difficulty=request.form.get('difficulty')
        )
        db.session.add(new_q)
        db.session.flush() # This generates the 'id' for new_q immediately

        # 2. Extract the dynamic lists from the HTML form
        inputs = request.form.getlist('test_inputs[]')
        outputs = request.form.getlist('test_outputs[]')

        # 3. Create TestCase entries for each pair
        for i in range(len(inputs)):
            if inputs[i].strip(): # Skip empty inputs
                new_case = TestCase(
                    input_data=inputs[i],
                    expected_output=outputs[i],
                    question_root_id=new_q.id
                )
                db.session.add(new_case)

        db.session.commit()
        return redirect(url_for('admin_panel'))
    
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.password == request.form.get('password'):
            login_user(user)
            return redirect(url_for('admin_panel'))
        flash('Invalid Credentials')
    return render_template('admin_login.html')



@app.route('/admin/update/<int:id>', methods=['GET', 'POST'])
@login_required
def update_question(id):
    questions = Question.query.get_or_404(id)
    if request.method == 'POST':
        new_q = Question(
        question_id = request.form.get('question_id'),
        title=request.form.get('title'),
        description=request.form.get('description'),
        input_format = request.form.get('input_format'),
        constraints=request.form.get('constraints'),
        output_format = request.form.get('output_format'),
        sample_input = request.form.get('sample_input'),
        sample_output = request.form.get('sample_output'),
        explanation = request.form.get('explanation'),
        difficulty = request.form.get('difficulty')
    )
        db.session.add(new_q)
        db.session.commit()
        return redirect(url_for('admin_panel'))
    return render_template('edit_questions.html', questions=questions)

@app.route('/admin/delete_question/<int:id>')
@login_required
def delete_question(id):
    db.session.delete(Question.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # 1. Collect data from the form
        name = request.form.get('name')
        email = request.form.get('email')
        content = request.form.get('content')

        # 2. Create a new Message object
        new_message = Message(name=name, email=email, content=content)

        # 3. Add to session and save to the database
        db.session.add(new_message)
        db.session.commit()

        flash('Message Successfully Sent!')
        return redirect(url_for('student_problem_view'))

    # If GET, just fetch messages or render the page
    messages = Message.query.all()
    return render_template('contact.html', messages=messages)


@app.route('/admin/delete_msg/<int:id>')
@login_required
def delete_msg(id):
    db.session.delete(Message.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))


# Compiler Run Module
@app.route("/run", methods=["POST"])
def run_code():
    data = request.json
    code = data["code"]
    lang = data["language"]
    user_input = data["input"]

    uid = uuid.uuid4().hex
    filename = ""
    command = []

    try:
        # ---------- PYTHON ----------
        if lang == "python":
            filename = f"{uid}.py"
            with open(filename, "w") as f:
                f.write(code)
            command = ["python", filename]

        # ---------- C ----------
        elif lang == "c":
            filename = f"{uid}.c"
            exe = f"{uid}.out"
            with open(filename, "w") as f:
                f.write(code)

            compile = subprocess.run(
                ["gcc", filename, "-o", exe],
                capture_output=True,
                text=True
            )
            if compile.returncode != 0:
                return jsonify({"output": "", "error": compile.stderr})

            command = [f"./{exe}"]

        # ---------- C++ ----------
        elif lang == "cpp":
            filename = f"{uid}.cpp"
            exe = f"{uid}.out"
            with open(filename, "w") as f:
                f.write(code)

            compile = subprocess.run(
                ["g++", filename, "-o", exe],
                capture_output=True,
                text=True
            )
            if compile.returncode != 0:
                return jsonify({"output": "", "error": compile.stderr})

            command = [f"./{exe}"]

        # ---------- JAVA ----------
        elif lang == "java":
            filename = "Main.java"
            with open(filename, "w") as f:
                f.write(code)

            compile = subprocess.run(
                ["javac", filename],
                capture_output=True,
                text=True
            )
            if compile.returncode != 0:
                return jsonify({"output": "", "error": compile.stderr})

            command = ["java", "Main"]

        # ---------- RUN ----------
        result = subprocess.run(
            command,
            input=user_input + "\n",   # 🔥 INPUT FIX
            capture_output=True,
            text=True,
            timeout=5
        )

        return jsonify({
            "output": result.stdout,
            "error": result.stderr
        })

    except subprocess.TimeoutExpired:
        return jsonify({"output": "", "error": "⏰ Time Limit Exceeded"})

    finally:
        for file in os.listdir():
            if uid in file or file in ["Main.java", "Main.class"]:
                try:
                    os.remove(file)
                except:
                    pass


if __name__ == "__main__":
    app.run(debug=True)