from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from models import db, User, Job, Application, Education
import traceback,requests,json,cloudinary.uploader,os
from cloudinary.utils import cloudinary_url
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from werkzeug.utils import secure_filename
from helper import configure_genai, get_gemini_response, extract_pdf_text, prepare_prompt
from dotenv import load_dotenv

app = Blueprint('routes', __name__)

@app.route("/")
def home():
    if"email" in session:
        return redirect(url_for('routes.dashboard'))
    return render_template("index.html")

# Register Route
@app.route("/register", methods=['GET','POST'])
def register():
    if request.method == "POST":
        try:
            fullname = request.form.get('fullname')
            email = request.form.get('email')
            phone = request.form.get('phone')
            password = request.form.get('password')
            user_type = request.form.get('user_type')
            
            print(f"Register Attempt: {fullname}, {email}, {phone}, {user_type}")

            if not all([fullname, email, phone, password, user_type]):
                flash("All fields are required!", "danger")
                return redirect(url_for('routes.register'))
            
            # Check if email or phone already exists
            if User.query.filter_by(email=email).first():
                flash("Email already exists!", "danger")
                return redirect(url_for('routes.register'))
    
            if User.query.filter_by(phone=phone).first():  
                flash("Phone number already exists!", "danger")
                return redirect(url_for('routes.register'))

            new_user = User(fullname=fullname, email=email, phone=phone, user_type=user_type)
            new_user.set_password(password)

            db.session.add(new_user)
            db.session.commit()
            
            print("User successfully saved to database!")
            session['email'] = email
            session['user_type'] = user_type
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('routes.login'))
        
        except Exception as e:
            print("Database Error:", e)
            return "An error occurred. Check the console for details."
        # except Exception:
        #     print("Error occurred during registration:")
        #     print(traceback.format_exc())
        #     flash("An error occurred during registration. Check the console for details.", "danger")
    
    return render_template("register.html")

# Login Route
@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        try:
            email = request.form.get('email')
            password = request.form.get('password')
            user_type = request.form.get('user_type')

            if not all([email, password, user_type]):
                flash("All fields are required!", "danger")
                return redirect(url_for('routes.login'))

            user = User.query.filter_by(email=email).first()

            if user and user.check_password(password) and user.user_type == user_type:
                session['email'] = user.email
                session['user_type'] = user.user_type
                session["user_id"] = user.id
                flash("Login successful!", "success")
                return redirect(url_for('routes.dashboard'))
            
            flash("Invalid credentials or user type!", "danger")
        
        except Exception:
            print("Error occurred during login:")
            print(traceback.format_exc())
            flash("An error occurred during login. Check the console for details.", "danger")
    
    return render_template("login.html")

# Logout Route
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('routes.home'))

# Dashboard Route
@app.route('/dashboard')
def dashboard():
    if 'email' not in session or 'user_type' not in session:
        flash('You need to log in first.', 'danger')
        return redirect(url_for('routes.login'))

    user_type = session['user_type']
    email = session['email']
    user_id = session['user_id']
    user = User.query.filter_by(email=email).first()

    if user_type == 'student':
        # Fetch the student's education details
        education = Education.query.filter_by(student_id=user.id).first()
        if not education:
            flash('Please complete your educational profile before applying for jobs.', 'danger')
            return redirect(url_for('routes.profile'))

        user = User.query.get(user_id)
        # Fetch all available jobs
        jobs = Job.query.all()
        
        applied_jobs = Application.query.filter_by(student_id=user.id).all()
        applied_job_ids = {application.job_id for application in applied_jobs}
        
        applied_jobs_data = []
        for application in applied_jobs:
            job = Job.query.get(application.job_id)
            if job:
                applied_jobs_data.append({
                    'title': job.title,
                    'company': job.company,
                    'location': job.location,
                    'status': application.status,
                    'applied_on': application.applied_on.strftime('%Y-%m-%d')
                })
    
        # Filter jobs based on eligibility criteria
        eligible_jobs = []
        for job in jobs:
            if education:
                try:
                    # Safely parse required fields of study
                    required_fields = json.loads(job.required_field_of_study) if job.required_field_of_study else []
                    if isinstance(required_fields, str): 
                        required_fields = [required_fields]
                except json.JSONDecodeError:
                    required_fields = []

                try:
                    # Safely parse required streams of study
                    required_streams = json.loads(job.required_stream_of_study) if job.required_stream_of_study else []
                    if isinstance(required_streams, str): 
                        required_streams = [required_streams]
                except json.JSONDecodeError:
                    required_streams = []

                # Check eligibility
                if (
                    (job.min_class_10_marks is None or float(education.class_10_marks) >= job.min_class_10_marks) and
                    (job.min_class_12_marks is None or float(education.class_12_marks) >= job.min_class_12_marks) and
                    (job.min_university_marks is None or float(education.university_marks) >= job.min_university_marks) and
                    (not required_fields or education.field_of_study in required_fields) and
                    (not required_streams or education.stream_of_studies in required_streams)
                ):
                    eligible_jobs.append(job)

        return render_template('student_dashboard.html', jobs=eligible_jobs, applied_jobs=applied_jobs_data, applied_job_ids=applied_job_ids, user=user)

    elif user.user_type == 'university':
        # Fetch all jobs, including those posted by other universities
        all_jobs = Job.query.all()
        
        # Prepare jobs data for rendering
        jobs_data = []
        for job in all_jobs:
            # Fetch applications for this job
            applications = Application.query.filter_by(job_id=job.id).all()
            
            applicants = []
            for application in applications:
                applicant = User.query.get(application.student_id)
                if applicant:
                    applicants.append({
                        "id": application.id,
                        'fullname': applicant.fullname,
                        'email': applicant.email,
                        'phone': applicant.phone,
                        'status': application.status,
                        'cv_url': applicant.cv_url,
                        'cv_filename': applicant.cv_filename                        
                    })
            
            jobs_data.append({
                'job': job,
                'applicants': applicants,
                'is_own_job': job.posted_by == user.id  # Check if this job belongs to the logged-in university user
            })
        
        return render_template(
            "university_dashboard.html", 
            user=user, 
            jobs_data=jobs_data
        )

    else:
        flash('Invalid user type!', 'danger')
        return redirect(url_for('routes.login'))

# Apply to Job Route (For Students)
@app.route('/apply/<int:job_id>', methods=['POST'])
def apply_job(job_id):
    if "email" not in session or session["user_type"] != "student":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("routes.home"))
    
    user_id = session.get("user_id")
    if not user_id:
        flash("User is not logged in properly. Please log in again.", "danger")
        return redirect(url_for("routes.login"))
    
    try:
        user = User.query.get(user_id)
        job = Job.query.get(job_id)
        
        if not user:
            flash("User not found in the database.", "danger")
            return redirect(url_for("routes.login"))

        if not job:
            flash("Job not found!", "danger")
            return redirect(url_for("routes.dashboard"))

        # Check if the user already applied
        existing_application = Application.query.filter_by(job_id=job_id, student_id=user_id).first()
        if existing_application:
            flash("You have already applied for this job.", "warning")
            return redirect(url_for("routes.dashboard"))

        # Save the application
        new_application = Application(job_id=job_id, student_id=user_id)
        db.session.add(new_application)
        db.session.commit()

        flash("Application submitted successfully! Your ATS score is calculated.", "success")
        
    except Exception as e:
        print("Error applying to job:", e)
        flash("An error occurred while applying for the job.", "danger")

    return redirect(url_for("routes.dashboard"))

# Post a New Job (For Universities)
@app.route('/post_job', methods=['GET', 'POST'])
def post_job():
    if 'email' not in session or session['user_type'] != 'university':
        flash('You need to log in as a university to post jobs.', 'danger')
        return redirect(url_for('routes.login'))

    if request.method == 'POST':
        try:
            email = session['email']
            user = User.query.filter_by(email=email).first()

            title = request.form.get('title')
            company = request.form.get('company')
            description = request.form.get('description')
            location = request.form.get('location')
            salary = request.form.get('salary')
            min_class_10_marks = request.form.get('min_class_10_marks')
            min_class_12_marks = request.form.get('min_class_12_marks')
            min_university_marks = request.form.get('min_university_marks')
            required_field_of_study = json.dumps(request.form.getlist('required_field_of_study'))
            required_stream_of_study = json.dumps(request.form.getlist('required_stream_of_study'))

            new_job = Job(
                title=title,
                company=company,
                description=description,
                location=location,
                salary=salary,
                posted_by=user.id,
                min_class_10_marks=float(min_class_10_marks) if min_class_10_marks else None,
                min_class_12_marks=float(min_class_12_marks) if min_class_12_marks else None,
                min_university_marks=float(min_university_marks) if min_university_marks else None,
                required_field_of_study=required_field_of_study,
                required_stream_of_study=required_stream_of_study
            )

            db.session.add(new_job)
            db.session.commit()

            flash('Job posted successfully!', 'success')
            return redirect(url_for('routes.dashboard'))
        except Exception:
            flash('An error occurred while posting the job. Please try again.', 'danger')

    return render_template('post_job.html')

# Edit Job Route (Only the job owner can access this)
@app.route('/edit_job/<int:job_id>', methods=['GET', 'POST'])
def edit_job(job_id):
    if 'email' not in session or session['user_type'] != 'university':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('routes.login'))
    
    user = User.query.filter_by(email=session['email']).first()
    job = Job.query.get(job_id)
    
    # Check if the logged-in user owns the job
    if job.posted_by != user.id:
        flash("You do not have permission to edit this job.", "danger")
        return redirect(url_for('routes.dashboard'))

    if request.method == 'POST':
        # Update the job details
        job.title = request.form.get('title')
        job.company = request.form.get('company')
        job.description = request.form.get('description')
        job.location = request.form.get('location')
        job.salary = request.form.get('salary')
        job.min_class_10_marks = float(request.form.get('min_class_10_marks') or 0)
        job.min_class_12_marks = float(request.form.get('min_class_12_marks') or 0)
        job.min_university_marks = float(request.form.get('min_university_marks') or 0)
        job.required_field_of_study = request.form.get('required_field_of_study')
        job.required_stream_of_study = request.form.get('required_stream_of_study')
        
        db.session.commit()
        flash("Job updated successfully!", "success")
        return redirect(url_for('routes.dashboard'))
    
    return render_template('edit_job.html', job=job)

# View & Manage Applications (For Universities)
@app.route('/manage_applications/<int:job_id>')
def manage_applications(job_id):
    if 'email' not in session or session['user_type'] != 'university':
        flash('You need to log in as a university to manage applications.', 'danger')
        return redirect(url_for('routes.login'))
    try:
        job = Job.query.get(job_id)
        if not job:
            flash("Job not found!", "danger")
            return redirect(url_for("routes.university_dashboard"))
        
        # Fetch all applications related to the job
        applications = Application.query.filter_by(job_id=job_id).all()
        applicants = []

        for application in applications:
            student = User.query.get(application.student_id)
            applicants.append({"application": application, "student": student})

        return render_template("manage_applications.html", job=job, applicants=applicants)
    
    except Exception as e:
        print("Error fetching applicants:", e)
        flash("An error occurred while fetching applicants.", "danger")
        return redirect(url_for("routes.university_dashboard"))

# Update Application Status
@app.route("/update_application/<int:application_id>", methods=["POST"])
def update_application(application_id):
    if "email" not in session or session["user_type"] != "university":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("routes.home"))

    try:
        application = Application.query.get(application_id)
        if not application:
            flash("Application not found!", "danger")
            return redirect(url_for("routes.dashboard"))

        new_status = request.form.get("status")
        
        if new_status in ["Pending", "Accepted", "Rejected"]:
            application.status = new_status
            db.session.commit()
            flash("Application status updated successfully!", "success")
        else:
            flash("Invalid status!", "danger")
            
    except Exception as e:
        print("Error updating application:", e)
        flash("An error occurred while updating the application status.", "danger")

    return redirect(url_for("routes.dashboard"))

# View and Update Profile Route
@app.route("/profile", methods=['GET', 'POST'])
def profile():
    if 'email' not in session or session['user_type'] != 'student':
        flash("You are not authorized to access this page.", "danger")
        return redirect(url_for('routes.login'))
    
    user = User.query.filter_by(email=session['email']).first()
    education = Education.query.filter_by(student_id=user.id).first()

    if request.method == 'POST':
        try:
            # Update Educational Details
            class_10_marks = request.form.get('class_10_marks')
            class_12_marks = request.form.get('class_12_marks')
            university_marks = request.form.get('university_marks')
            field_of_study = request.form.get('field_of_study')
            stream_of_studies = request.form.get('stream_of_studies')
            
            if education:
                education.class_10_marks = class_10_marks
                education.class_12_marks = class_12_marks
                education.university_marks = university_marks
                education.field_of_study = field_of_study
                education.stream_of_studies = stream_of_studies
            else:
                # Create new education record if not exists
                education = Education(
                    student_id=user.id,
                    class_10_marks=class_10_marks,
                    class_12_marks=class_12_marks,
                    university_marks=university_marks,
                    field_of_study=field_of_study,
                    stream_of_studies=stream_of_studies
                )
                db.session.add(education)
            
            db.session.commit()
            flash("Profile updated successfully!", "success")
        except Exception as e:
            print("Error updating profile:", e)
            flash("An error occurred while updating your profile.", "danger")
    
    return render_template("view_profile.html", user=user, education=education)

# Upload CV Route
@app.route("/upload_cv", methods=["POST"])
def upload_cv():
    if "email" not in session or session["user_type"] != "student":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("routes.home"))

    if "cv" not in request.files:
        flash("No file part!", "danger")
        return redirect(url_for("routes.profile"))

    file = request.files["cv"]

    if file.filename == "":
        flash("No selected file!", "danger")
        return redirect(url_for("routes.profile"))

    if file and file.filename.lower().endswith(".pdf"):
        try:
            result = cloudinary.uploader.upload(file, resource_type="auto",folder="student_cvs")
            cv_url = result["url"]
            
            # Save the CV URL to the database
            user = User.query.filter_by(email=session["email"]).first()
            user.cv_url = cv_url  # Make sure you have this field in your User model
            user.cv_filename = file.filename
            db.session.commit()
            
            flash("CV uploaded successfully!", "success")
        except Exception as e:
            print("Error uploading file:", e)
            flash("Error uploading file. Please try again.", "danger")

    else:
        flash("Only PDF files are allowed!", "danger")

    return redirect(url_for("routes.profile"))


from ollama import chat
@app.route("/chatbot", methods=["POST"])
def chatbot():
    if request.method == "POST":
        try:
            user_input = request.json.get("message")

            if not user_input:
                return jsonify({"error": "No message provided"}), 400

            # Call Ollama's model to get a response
            response = chat(model="llama2", messages=[{"role": "user", "content": user_input}])
            
            # Log the entire response for debugging
            print("Ollama Response:", response)
        
            # Make sure the response contains the reply
            if hasattr(response, 'message') and response.message.content:
                bot_reply = response.message.content
                return jsonify({"reply": bot_reply})
            else:
                return jsonify({"reply": "Sorry, I couldn't understand your request. Please try again."})
   
            # Send the response to the frontend
            return jsonify({"reply": bot_reply})
        
        except Exception as e:
            print("Error in chatbot:", e)
            return jsonify({"error": "An error occurred while processing your request."}), 500

# Define allowed file types for uploads
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    """Check if the uploaded file is a valid PDF."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Route to render the ATS Scoring page
@app.route('/ats_scoring', methods=['GET'])
def ats_scoring():
    if 'user_id' not in session:
        return redirect(url_for('routes.login'))

    jobs = Job.query.all()  # Fetch all jobs for the dropdown menu
    return render_template('ats_scoring.html', jobs=jobs)

# Route to handle ATS Scoring process
@app.route('/ats_scoring_process', methods=['POST'])
def ats_scoring_process():
    if 'user_id' not in session:
        flash("Please log in to access this feature.", "danger")
        return redirect(url_for('routes.login'))

    if 'resume' not in request.files:
        flash('No resume file provided.', 'danger')
        return redirect(url_for('routes.ats_scoring'))

    resume = request.files['resume']
    job_id = request.form.get('job_id')

    if not resume or not allowed_file(resume.filename):
        flash('Invalid file type. Only PDF files are allowed.', 'danger')
        return redirect(url_for('routes.ats_scoring'))

    if not job_id:
        flash('Please select a job from the dropdown.', 'danger')
        return redirect(url_for('routes.ats_scoring'))

    try:
        # Extract text from the uploaded resume
        resume_text = extract_pdf_text(resume)  # Directly using the uploaded file
        print("Extracted Resume Text (First 200 chars):", resume_text[:200]) 

        # Fetching the job description for the selected job
        job = Job.query.get(job_id)
        if not job:
            flash('Job not found.', 'danger')
            return redirect(url_for('routes.ats_scoring'))

        job_description = job.description
        print("Job Description (First 200 chars):", job_description[:200])  

        # Prepare the input prompt
        input_prompt = prepare_prompt(resume_text, job_description)
        print("Prepared Prompt (First 500 chars):", input_prompt[:500])

        # Get response from the Gemini model
        response = get_gemini_response(input_prompt)
        print("Gemini Response:", response)
        
        # Parse the response JSON
        response_json = json.loads(response)

        # Extract results
        match_percentage = response_json.get("JD Match", "N/A")
        missing_keywords = response_json.get("MissingKeywords", [])
        profile_summary = response_json.get("Profile Summary", "No summary available")
        
        print("Match Percentage:", match_percentage)
        print("Missing Keywords:", missing_keywords)
        print("Profile Summary:", profile_summary)
        
        # Render the result in the ats_scoring page
        return render_template('ats_scoring.html', 
                               match_percentage=match_percentage,
                               missing_keywords=missing_keywords,
                               profile_summary=profile_summary,
                               jobs=Job.query.all())
    except Exception as e:
        print("Error occurred during ATS scoring:", e)
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('routes.ats_scoring'))