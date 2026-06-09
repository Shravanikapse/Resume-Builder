from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify, flash
import mysql.connector # CHANGED: Imported MySQL connector
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import pdfkit
import io
import zipfile
from datetime import datetime
import json 
import base64 
import requests 
from urllib.parse import urlparse, parse_qs 
import re 
import os
from dotenv import load_dotenv
import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "your_secret_key_here")

# =================== DATABASE CONFIG ===================
# Helper function to get database connection
def get_db_connection():
    try:
        # Configure connection kwargs
        conn_kwargs = {
            "host": os.environ.get("DB_HOST", "localhost"),
            "user": os.environ.get("DB_USER", "root"),
            "password": os.environ.get("DB_PASSWORD", "qoemgsjk#36@5"),
            "database": os.environ.get("DB_NAME", "resume_db"),
            "port": int(os.environ.get("DB_PORT", 3306))
        }
        
        # Aiven MySQL requires SSL. If ca.pem exists, use it.
        ca_path = os.path.join(os.path.dirname(__file__), 'ca.pem')
        if os.path.exists(ca_path):
            conn_kwargs["ssl_ca"] = ca_path
            
        conn = mysql.connector.connect(**conn_kwargs)
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to DB: {err}")
        return None

# =================== DATABASE INIT ===================
def init_db():
    conn = get_db_connection()
    if conn is None:
        print("Could not connect to MySQL to initialize DB.")
        return

    c = conn.cursor()
    
    # CHANGED: Syntax for MySQL (INT AUTO_INCREMENT PRIMARY KEY instead of INTEGER ... AUTOINCREMENT)
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INT AUTO_INCREMENT PRIMARY KEY,
                  username VARCHAR(255) UNIQUE NOT NULL,
                  password VARCHAR(255) NOT NULL,
                  role VARCHAR(50) NOT NULL DEFAULT 'student')''')
    
    # CHANGED: user_id INT, and data LONGTEXT (because base64 images are big)
    c.execute('''CREATE TABLE IF NOT EXISTS history
                 (id INT AUTO_INCREMENT PRIMARY KEY,
                  user_id INT NOT NULL,
                  resume_name VARCHAR(255) NOT NULL,
                  generation_date VARCHAR(255) NOT NULL,
                  data LONGTEXT NOT NULL, 
                  template_choice VARCHAR(255) NOT NULL,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')

    # Check for admin
    c.execute("SELECT * FROM users WHERE username='admin'")
    if c.fetchone() is None:
        hashed_password = generate_password_hash('admin')
        # CHANGED: ? to %s for MySQL placeholders
        c.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                  ('admin', hashed_password, 'admin'))

    # Initialize settings table for config values like google_form_link
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key_name VARCHAR(255) PRIMARY KEY,
                  value_text TEXT NOT NULL)''')

    # Seed default Google Form URL if not set or empty
    c.execute("SELECT value_text FROM settings WHERE key_name='google_form_link'")
    row = c.fetchone()
    if row is None or not row[0].strip():
        default_form_link = 'https://docs.google.com/forms/d/e/1FAIpQLSd98uQGML7ppBFuP98B5KjTCeBrQNLacNuxRvOT2YvaU3KhWQ/viewform?usp=sharing&ouid=111161165457577862945'
        c.execute("""
            INSERT INTO settings (key_name, value_text) 
            VALUES ('google_form_link', %s) 
            ON DUPLICATE KEY UPDATE value_text = %s
        """, (default_form_link, default_form_link))
        
    conn.commit()
    c.close()
    conn.close()

# Initialize tables
init_db()

# Login and Signup routes removed, auth is handled entirely on the landing page via Privy


PRIVY_APP_ID = os.getenv("PRIVY_APP_ID", "cmq6wlxuo00w90ckzc61oibin")
JWKS_URL = f"https://auth.privy.io/api/v1/apps/{PRIVY_APP_ID}/jwks.json"

jwks_client = jwt.PyJWKClient(JWKS_URL)

@app.route('/privy_login', methods=['POST'])
def privy_login():
    data = request.json
    token = data.get('access_token')
    if not token:
        return jsonify({"error": "No token provided"}), 400
        
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        # Verify signature, but ignore audience/issuer mismatches just in case
        decoded = jwt.decode(
            token, 
            signing_key.key, 
            algorithms=["RS256"], 
            options={"verify_aud": False, "verify_iss": False}
        )
        user_id = decoded['sub'] 
        
        try:
            conn = get_db_connection()
            c = conn.cursor(dictionary=True)
            c.execute("SELECT * FROM users WHERE username=%s", (user_id,))
            user = c.fetchone()
            
            if not user:
                hashed_password = generate_password_hash("privy_dummy_pass")
                c.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, 'student')", (user_id, hashed_password))
                conn.commit()
                
                c.execute("SELECT * FROM users WHERE username=%s", (user_id,))
                user = c.fetchone()
                
            c.close()
            conn.close()
            
            session['user'] = {'id': user['id'], 'Username': user['username'], 'Role': user['role']}
        except Exception as db_e:
            print(f"DB Error during Privy login, falling back to dummy session: {db_e}")
            session['user'] = {'id': 999, 'Username': 'Test User', 'Role': 'student'}
            
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"Privy Login Error: {e}")
        return jsonify({"error": str(e)}), 401


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('landing'))

# =================== PROTECT ROUTES ===================
@app.before_request
def require_login():
    allowed_routes = ['landing', 'static', 'privy_login']
    if request.endpoint not in allowed_routes and 'user' not in session:
        return redirect(url_for('landing'))

# =================== CORE PAGES ===================
@app.route('/')
def landing():
    return render_template('landing.html', privy_app_id=PRIVY_APP_ID)

@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    google_form_link = ""
    recent_history = []
    total_resumes = 0
    
    if conn:
        try:
            c = conn.cursor(dictionary=True)
            # Fetch settings
            c.execute("SELECT value_text FROM settings WHERE key_name = 'google_form_link'")
            row = c.fetchone()
            if row:
                google_form_link = row['value_text']
                
            # Fetch user stats and history
            if 'user' in session:
                user_id = session['user']['id']
                user_role = session['user']['Role']
                
                if user_role == 'admin':
                    c.execute("SELECT COUNT(*) as total FROM history")
                    total_resumes = c.fetchone()['total']
                    
                    c.execute('''
                        SELECT h.id, h.resume_name, h.generation_date, h.template_choice, u.username 
                        FROM history h 
                        JOIN users u ON h.user_id = u.id 
                        ORDER BY h.id DESC LIMIT 5
                    ''')
                    items = c.fetchall()
                    recent_history = [{
                        'id': item['id'],
                        'name': item['resume_name'],
                        'user': item['username'],
                        'template': item['template_choice'],
                        'date': datetime.strptime(item['generation_date'], '%Y-%m-%d %H:%M:%S.%f').strftime('%b %d, %Y')
                    } for item in items]
                else:
                    c.execute("SELECT COUNT(*) as total FROM history WHERE user_id = %s", (user_id,))
                    total_resumes = c.fetchone()['total']
                    
                    c.execute("SELECT id, resume_name, generation_date, template_choice FROM history WHERE user_id = %s ORDER BY id DESC LIMIT 5", (user_id,))
                    items = c.fetchall()
                    recent_history = [{
                        'id': item['id'],
                        'name': item['resume_name'],
                        'template': item['template_choice'],
                        'date': datetime.strptime(item['generation_date'], '%Y-%m-%d %H:%M:%S.%f').strftime('%b %d, %Y')
                    } for item in items]
                    
            c.close()
        except mysql.connector.Error as err:
            print(f"Error fetching dashboard data: {err}")
        finally:
            conn.close()
            
    return render_template('index.html', google_form_link=google_form_link, recent_history=recent_history, total_resumes=total_resumes)


@app.route('/save_settings', methods=['POST'])
def save_settings():
    if 'user' not in session or session['user'].get('Role') != 'admin':
        return redirect(url_for('dashboard'))
    
    google_form_link = request.form.get('google_form_link', '').strip()
    
    conn = get_db_connection()
    if conn:
        try:
            c = conn.cursor()
            # MySQL syntax for insert or update
            c.execute("""
                INSERT INTO settings (key_name, value_text) 
                VALUES ('google_form_link', %s) 
                ON DUPLICATE KEY UPDATE value_text = %s
            """, (google_form_link, google_form_link))
            conn.commit()
            c.close()
        except mysql.connector.Error as err:
            print(f"Error saving setting: {err}")
        finally:
            conn.close()
            
    return redirect(url_for('dashboard'))


# =================== HISTORY PAGE ===================
@app.route('/history')
def history():
    user_id = session.get('user', {}).get('id')
    user_role = session.get('user', {}).get('Role')
    
    if not user_id:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    # CHANGED: dictionary=True
    c = conn.cursor(dictionary=True)

    if user_role == 'admin':
        # CHANGED: SQL syntax is standard, usually fine, just ensure no ? placeholders
        c.execute('''
            SELECT h.id, h.resume_name, h.generation_date, u.username 
            FROM history h 
            JOIN users u ON h.user_id = u.id 
            ORDER BY h.id DESC
        ''')
        history_items = c.fetchall()
        
        history_list = []
        for item in history_items:
            history_list.append({
                'id': item['id'],
                'name': item['resume_name'],
                'user': {'Username': item['username']}, 
                'date': datetime.strptime(item['generation_date'], '%Y-%m-%d %H:%M:%S.%f').strftime('%B %d, %Y')
            })
        
        c.close()
        conn.close()
        return render_template('history.html', all_history=history_list)

    else:
        # CHANGED: ? to %s
        c.execute("SELECT id, resume_name, generation_date FROM history WHERE user_id = %s ORDER BY id DESC", (user_id,))
        history_items = c.fetchall()
        c.close()
        conn.close()
        
        history_list = [{
            'id': item['id'],
            'name': item['resume_name'], 
            'date': datetime.strptime(item['generation_date'], '%Y-%m-%d %H:%M:%S.%f').strftime('%B %d, %Y')
        } for item in history_items]
        
        return render_template('history.html', history=history_list)

# =================== VIEW/RE-DOWNLOAD RESUME ===================
@app.route('/view_resume/<int:history_id>')
def view_resume(history_id):
    user_id = session.get('user', {}).get('id')
    user_role = session.get('user', {}).get('Role')
    if not user_id:
        return redirect(url_for('login'))

    conn = get_db_connection()
    c = conn.cursor(dictionary=True)
    
    if user_role == 'admin':
        # CHANGED: ? to %s
        c.execute("SELECT * FROM history WHERE id = %s", (history_id,))
    else:
        # CHANGED: ? to %s
        c.execute("SELECT * FROM history WHERE id = %s AND user_id = %s", (history_id, user_id))
        
    item = c.fetchone()
    c.close()
    conn.close()

    if not item:
        return redirect(url_for('history'))
        
    resume_data = json.loads(item['data'])
    template_choice = item['template_choice']
    rendered = render_template(template_choice, **resume_data)
    
    options = {
        'enable-local-file-access': None,
        'encoding': "UTF-8"
    }
    if template_choice == 'template2.html':
        template2_settings = {
            'page-size': 'A4',
            'margin-top': '0mm', 'margin-right': '0mm',
            'margin-bottom': '0mm', 'margin-left': '0mm',
            'no-stop-slow-scripts': None,
            'disable-smart-shrinking': None,
            'user-style-sheet': ['static/pdf_full_height.css'] 
        }
        options.update(template2_settings)
    
    pdf_bytes = pdfkit.from_string(rendered, False, options=options)
    
    return send_file(
        io.BytesIO(pdf_bytes), 
        as_attachment=True, 
        download_name=item['resume_name'], 
        mimetype="application/pdf"
    )

# =================== HELPER FUNCTION FOR G-DRIVE ===================
def convert_drive_link(url):
    if not isinstance(url, str): return ""
    url = url.strip()
    if not url: return ""

    file_id = None
    try:
        parsed_url = urlparse(url)
        if "drive.google.com" in parsed_url.netloc and parsed_url.path == '/open':
            query_params = parse_qs(parsed_url.query)
            if 'id' in query_params and query_params['id']:
                file_id = query_params['id'][0]
        elif "drive.google.com" in parsed_url.netloc and ('/d/' in parsed_url.path or '/file/d/' in parsed_url.path):
            path_parts = parsed_url.path.split('/')
            for i, part in enumerate(path_parts):
                if part == 'd' and i + 1 < len(path_parts):
                    potential_id = path_parts[i+1]
                    if len(potential_id) > 20: 
                        file_id = potential_id
                        break 
        if file_id:
            file_id = file_id.split('?')[0].split('&')[0]
            return f"https://drive.google.com/uc?id={file_id}"
        if "drive.google.com" in parsed_url.netloc:
            return "" 
    except Exception as e:
        print(f"Error converting GDrive link {url}: {e}")
        return "" 
    if url.startswith("http://") or url.startswith("https://"):
        return url 
    return url 

# =================== GOOGLE SHEET BASED GENERATION (ADMIN) ===================
@app.route('/generate', methods=['POST'])
def generate():
    if session.get('user', {}).get('Role') != 'admin':
        return redirect(url_for('dashboard'))
    
    admin_user_id = session['user']['id']
    sheet_link = request.form.get('sheet_link', '').strip()
    if not sheet_link:
        flash("Google Sheet link is required.", "danger")
        return redirect(url_for('dashboard'))
    try:
        if "docs.google.com/spreadsheets" not in sheet_link:
            raise ValueError("Invalid Google Sheets link format.")
        sheet_id = sheet_link.split("/d/")[1].split("/")[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        dtype_map = {col: str for col in ['photo_url', 'linkedin', 'email', 'skills', 'achievements', 'certifications', 'project_name', 'project_description', 'experience_title', 'experience_description', 'experience_year', 'education', 'education_description', 'year', 'name', 'contact', 'location', 'summary']}
        df = pd.read_csv(csv_url, dtype=dtype_map, keep_default_na=False)
    except Exception as e:
        flash("Failed to read spreadsheet. Make sure it is a valid, publicly viewable Google Sheet with correctly named columns.", "danger")
        return redirect(url_for('dashboard'))
        
    template_choice = request.form.get("template_choice", "template1.html")
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for i, row in df.iterrows():
            projects_list, experience_list, achievements_list, skills_list, certifications_list, education_list = [], [], [], [], [], []
            
            if str(row.get("project_name", "")):
                names = str(row.get("project_name", "")).split(";")
                descriptions = str(row.get("project_description", "")).split(";")
                for idx, name in enumerate(names):
                    projects_list.append({"title": name.strip(), "description": descriptions[idx].strip() if idx < len(descriptions) else ""})
            
            if str(row.get("experience_title", "")):
                titles = str(row.get("experience_title", "")).split(";")
                descriptions = str(row.get("experience_description", "")).split(";")
                year = str(row.get("experience_year", "")).split(";")
                for idx, title in enumerate(titles):
                    experience_list.append({"title": title.strip(), "year": year[idx].strip() if idx < len(year) else "", "description": descriptions[idx].strip() if idx < len(descriptions) else ""})
            
            if str(row.get("achievements", "")): 
                achievements_list = [a.strip() for a in str(row["achievements"]).split(";")]
            
            if str(row.get("skills", "")):
                skills_text = str(row["skills"]).replace("\n", "").replace(" ;", ";").replace("; ", ";").strip()
                skills_list = [s.strip() for s in skills_text.split(";") if s.strip()]
            
            if str(row.get("certifications", "")):
                for p in str(row["certifications"]).split(";"):
                    parts = p.strip().split("-", 1)
                    certifications_list.append({"title": parts[0].strip(), "description": parts[1].strip() if len(parts) > 1 else ""})
            
            if str(row.get("education", "")):
                educations = str(row.get("education", "")).split(";")
                descriptions = str(row.get("education_description", "")).split(";")
                year = str(row.get("year", "")).split(";")
                for idx, degree in enumerate(educations):
                    education_list.append({"degree": degree.strip(), "year": year[idx].strip() if idx < len(year) else "", "description": descriptions[idx].strip() if idx < len(descriptions) else ""})
            
            photo_data_uri = None 
            original_url = str(row.get("photo_url", "")).strip() 
            if original_url: 
                download_url = convert_drive_link(original_url) 
                if download_url:
                    try:
                        response = requests.get(download_url, timeout=10, allow_redirects=True)
                        if response.status_code == 200:
                            file_bytes = response.content
                            if file_bytes:
                                b64_string = base64.b64encode(file_bytes).decode('utf-8')
                                mime_type = response.headers.get('Content-Type', 'image/jpeg').split(';')[0]
                                if not mime_type.startswith('image/'):
                                    mime_type = 'image/jpeg'
                                photo_data_uri = f"data:{mime_type};base64,{b64_string}"
                        else:
                            print(f"Failed photo fetch {response.status_code}")
                    except Exception as e:
                        print(f"Error downloading image {download_url}: {e}")
            
            resume_data = {
                "name": str(row.get("name", "")).strip(),
                "contact": str(row.get("contact", "")).strip(),
                "email": str(row.get("email", "")).strip(),
                "linkedin": str(row.get("linkedin", "")).strip(),
                "location": str(row.get("location", "")).strip(),
                "summary": str(row.get("summary", "")).strip(),
                "skills": skills_list,
                "projects": projects_list,
                "education": education_list,
                "experience": experience_list,
                "achievements": achievements_list,
                "certifications": certifications_list,
                "photo_url": photo_data_uri
            }
            
            rendered = render_template(template_choice, **resume_data)
            
            options = {'enable-local-file-access': None, 'encoding': "UTF-8"}
            if template_choice == 'template2.html':
                template2_settings = {
                    'page-size': 'A4',
                    'margin-top': '0mm', 'margin-right': '0mm',
                    'margin-bottom': '0mm', 'margin-left': '0mm',
                    'no-stop-slow-scripts': None,
                    'disable-smart-shrinking': None,
                    'user-style-sheet': ['static/pdf_full_height.css']
                }
                options.update(template2_settings)
                
            pdf_bytes = pdfkit.from_string(rendered, False, options=options)
            pdf_filename = f"resume_{str(row.get('name', f'student_{i+1}')).strip() or f'student_{i+1}'}.pdf"
            zipf.writestr(pdf_filename, pdf_bytes)
            
            data_json = json.dumps(resume_data)
            try:
                conn = get_db_connection()
                c = conn.cursor()
                # CHANGED: ? to %s
                c.execute("INSERT INTO history (user_id, resume_name, generation_date, data, template_choice) VALUES (%s, %s, %s, %s, %s)",
                          (admin_user_id, pdf_filename, datetime.now(), data_json, template_choice))
                conn.commit()
                c.close()
                conn.close()
            except Exception as db_e:
                print(f"Database error writing history for row {i}: {db_e}")
            
    zip_buffer.seek(0)
    return send_file(zip_buffer, as_attachment=True, download_name="resumes.zip", mimetype="application/zip")

# =================== SINGLE FORM ===================
@app.route('/form')
def form():
    return render_template('form.html')

@app.route('/generate_form', methods=['POST'])
def generate_form():
    
    # Backend Validations
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    
    if not name or len(name) < 2:
        flash("Please enter a valid full name (at least 2 characters).", "danger")
        return redirect(url_for('form'))
        
    if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        flash("Please enter a valid email address.", "danger")
        return redirect(url_for('form'))
        
    photo_url = None
    photo_file = request.files.get('profile_photo')
    if photo_file and photo_file.filename != '':
        try:
            file_bytes = photo_file.read()
            b64_string = base64.b64encode(file_bytes).decode('utf-8')
            mime_type = photo_file.mimetype
            photo_url = f"data:{mime_type};base64,{b64_string}"
        except Exception as e:
            print(f"Error processing image: {e}")

    resume_data = {
        "name": request.form.get("name", "").strip(),
        "contact": request.form.get("contact"),
        "email": request.form.get("email"),
        "linkedin": request.form.get("linkedin"),
        "location": request.form.get("location"),
        "summary": request.form.get("summary"),
        "skills": [s.strip() for s in request.form.get("skills", "").split(";") if s.strip()],
        "projects": [], "experience": [], "achievements": [], "certifications": [], "education": [],
        "photo_url": photo_url 
    }
    
    if request.form.get("project_name"):
        names = request.form.get("project_name", "").split(";")
        descriptions = request.form.get("project_description", "").split(";")
        for idx, name in enumerate(names):
            resume_data["projects"].append({"title": name.strip(), "description": descriptions[idx].strip() if idx < len(descriptions) else ""})
    if request.form.get("experience_title"):
        titles = request.form.get("experience_title", "").split(";")
        descriptions = request.form.get("experience_description", "").split(";")
        years = request.form.get("experience_year", "").split(";")
        for idx, title in enumerate(titles):
            resume_data["experience"].append({"title": title.strip(), "year": years[idx].strip() if idx < len(years) else "", "description": descriptions[idx].strip() if idx < len(descriptions) else ""})
    if request.form.get("education"):
        degrees = request.form.get("education", "").split(";")
        descriptions = request.form.get("education_description", "").split(";")
        years = request.form.get("year", "").split(";")
        for idx, degree in enumerate(degrees):
            resume_data["education"].append({"degree": degree.strip(), "year": years[idx].strip() if idx < len(years) else "", "description": descriptions[idx].strip() if idx < len(descriptions) else ""})
    if request.form.get("certifications"):
        for p in request.form.get("certifications").split(";"):
            parts = p.strip().split("-", 1)
            resume_data["certifications"].append({"title": parts[0].strip(), "description": parts[1].strip() if len(parts) > 1 else ""})
    if request.form.get("achievements"):
        resume_data["achievements"] = [a.strip() for a in request.form.get("achievements").split(";")]

    template_choice = request.form.get("template_choice", "template1.html")
    rendered = render_template(template_choice, **resume_data)

    user_id = session['user']['id']
    resume_filename = f"resume_{resume_data['name']}.pdf"
    data_json = json.dumps(resume_data)
    
    conn = get_db_connection()
    c = conn.cursor()
    # CHANGED: ? to %s
    c.execute("INSERT INTO history (user_id, resume_name, generation_date, data, template_choice) VALUES (%s, %s, %s, %s, %s)",
              (user_id, resume_filename, datetime.now(), data_json, template_choice))
    conn.commit()
    c.close()
    conn.close()

    options = {
        'enable-local-file-access': None,
        'encoding': "UTF-8"
    }
    if template_choice == 'template2.html':
        template2_settings = {
            'page-size': 'A4',
            'margin-top': '0mm', 'margin-right': '0mm',
            'margin-bottom': '0mm', 'margin-left': '0mm',
            'no-stop-slow-scripts': None,
            'disable-smart-shrinking': None,
            'user-style-sheet': ['static/pdf_full_height.css']
        }
        options.update(template2_settings)
        
    pdf_bytes = pdfkit.from_string(rendered, False, options=options)
    
    return send_file(
        io.BytesIO(pdf_bytes), 
        as_attachment=True, 
        download_name=f"resume_{resume_data['name']}.pdf", 
        mimetype="application/pdf"
    )

# =================== ATS SCORE CALCULATOR ===================
# No database changes needed here
def calculate_easy_ats_score(resume_text, jd_text):
    STOP_WORDS = set([
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has', 'he',
        'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the', 'to', 'was', 'were', 'will', 'with',
        'our', 'we', 'you', 'your', 'job', 'title', 'location', 'description', 'responsibilities',
        'skills', 'qualifications', 'must', 'have', 'is', 'new', 'team', 'work', 'plus', 'like',
        'preferably', 'highly', 'valued'
    ])
    
    def clean_text(text):
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.split()
        cleaned_words = [word for word in words if word not in STOP_WORDS and not word.isdigit()]
        return set(cleaned_words)

    resume_words = clean_text(resume_text)
    jd_words = clean_text(jd_text)

    if not jd_words:
        print("ATS DEBUG: Job Description words are empty after cleaning.")
        return 0

    common_words = resume_words.intersection(jd_words)
    
    print(f"--- ATS DEBUG ---")
    print(f"Total Resume Words (Cleaned): {len(resume_words)}")
    print(f"Total JD Words (Cleaned): {len(jd_words)}")
    print(f"Common Words ({len(common_words)}): {common_words}")
    print(f"Missing JD Words: {jd_words - common_words}")

    score = (len(common_words) / len(jd_words)) * 100
    
    return int(score)


@app.route('/calculate-ats', methods=['POST'])
def handle_ats_calculation():
    data = request.json
    resume_text = data.get('resume', '')
    jd_text = data.get('jd', '')
    
    score = calculate_easy_ats_score(resume_text, jd_text)
    
    return jsonify({'score': score})


if __name__ == '__main__':
    app.run(debug=True)