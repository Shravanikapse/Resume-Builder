# Multi-Resume Generation and Management System

<div align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask"/>
  <img src="https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white" alt="MySQL"/>
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"/>
  <img src="https://img.shields.io/badge/Render-46E3B7?style=for-the-badge&logo=render&logoColor=white" alt="Render"/>
  <img src="https://img.shields.io/badge/Groq-000000?style=for-the-badge&logo=groq&logoColor=white" alt="Groq"/>
  <br />
  <strong><a href="https://resume-builder-ay3z.onrender.com/" target="_blank">View Live Website</a></strong>
</div>

<br />

A comprehensive, enterprise-grade web application built to streamline the resume creation and management process. This platform provides intelligent tools for students and job seekers to craft visually stunning resumes while offering robust administrative capabilities for bulk resume generation.

## Core Functionality

- **Dual-Role Authentication:** Secure access utilizing **Privy** for both 'Student' and 'Admin' roles.
- **Single Resume Builder:** Intuitive form-based interface allowing users to input their professional details, skills, experiences, and educational background to generate a polished resume.
- **Batch Resume Generation (Admin):** Seamlessly ingest bulk candidate data directly from Google Sheets to produce downloadable `.zip` archives containing hundreds of customized PDF resumes in seconds.
- **AI-Powered ATS Evaluator:** Integrates with the **Groq AI LLaMA-3 Model** to analyze resumes against specific Job Descriptions. It calculates a compatibility score (0-100) and provides actionable feedback on missing keywords or formatting improvements.
- **Multiple Layout Templates:** Offers 5 distinct, professionally designed template layouts to suit various industries (e.g., Minimalist, Dark Sidebar, Creative Bold).
- **History Tracking & Management:** Automatically saves generated resumes securely to the database, allowing users to revisit, view, and re-download past iterations.

## Technology Stack

### Backend & Core
- <img src="https://img.shields.io/badge/Python_3.10-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/> **Python 3.10**: Core programming language.
- <img src="https://img.shields.io/badge/Flask-000000?style=flat-square&logo=flask&logoColor=white" alt="Flask"/> **Flask 3.1**: Lightweight, robust web framework handling routing and backend logic.
- <img src="https://img.shields.io/badge/Pandas-150458?style=flat-square&logo=pandas&logoColor=white" alt="Pandas"/> **Pandas**: Utilized for extracting, transforming, and processing tabular candidate data from Google Sheets.
- <img src="https://img.shields.io/badge/Werkzeug-FF5722?style=flat-square&logoColor=white" alt="Werkzeug"/> **Werkzeug**: Secure password hashing and URL routing utilities.

### Database
- <img src="https://img.shields.io/badge/MySQL-4479A1?style=flat-square&logo=mysql&logoColor=white" alt="MySQL"/> **MySQL (Cloud via Aiven)**: Relational database storing user credentials, settings, and historical resume payload data natively as JSON strings.
- <img src="https://img.shields.io/badge/mysql--connector--python-4479A1?style=flat-square&logo=mysql&logoColor=white" alt="MySQL Connector"/> **MySQL Connector Python**: Facilitates secure database transactions and SSL connections using standard certificates (`ca.pem`).

### Security & Authentication
- <img src="https://img.shields.io/badge/Privy-111111?style=flat-square&logo=security&logoColor=white" alt="Privy"/> **Privy Integration**: Next-generation authentication via JWTs for decentralized login flows.
- <img src="https://img.shields.io/badge/PyJWT-000000?style=flat-square&logo=jsonwebtokens&logoColor=white" alt="PyJWT"/> **PyJWT & Cryptography**: Verification and decoding of secure session tokens.

### File Processing & Rendering
- <img src="https://img.shields.io/badge/wkhtmltopdf-000000?style=flat-square&logo=html5&logoColor=white" alt="wkhtmltopdf"/> **wkhtmltopdf / pdfkit**: Robust HTML to PDF conversion engine utilizing WebKit, ensuring pixel-perfect layout preservation.
- <img src="https://img.shields.io/badge/Base64-000000?style=flat-square&logo=data&logoColor=white" alt="Base64"/> **Base64 / IO / Zipfile**: In-memory processing of profile photos and dynamic generation of ZIP archives to avoid unnecessary disk I/O.

### AI Engine
- <img src="https://img.shields.io/badge/Groq_API-000000?style=flat-square&logo=groq&logoColor=white" alt="Groq API"/> **Groq Inference Engine**: Leverages the `llama3-8b-8192` model via REST API for ultra-low latency, highly accurate natural language processing in the ATS Analyzer module.

### Infrastructure & Deployment
- <img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker"/> **Docker**: Fully containerized environment ensuring parity across development and production environments.
- <img src="https://img.shields.io/badge/Gunicorn-499848?style=flat-square&logo=gunicorn&logoColor=white" alt="Gunicorn"/> **Gunicorn**: High-performance Python WSGI HTTP Server serving the production deployment.
- <img src="https://img.shields.io/badge/Render-46E3B7?style=flat-square&logo=render&logoColor=white" alt="Render"/> **Render**: Platform-as-a-Service (PaaS) utilizing the `Dockerfile` for seamless deployment, autoscaling, and SSL management.

---

## Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
   cd "BUILDER RESUME"
   ```

2. **Set up virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *Note: `wkhtmltopdf` must be installed on your system independently and available in your system's PATH.*

4. **Environment Variables (`.env`):**
   Create a `.env` file referencing `.env.example`:
   ```ini
   FLASK_SECRET_KEY=your_secure_secret
   DB_HOST=your_mysql_host
   DB_USER=your_db_username
   DB_PASSWORD=your_db_password
   DB_NAME=your_db_name
   DB_PORT=3306
   PRIVY_APP_ID=your_privy_app_id
   GROQ_API_KEY=your_groq_api_key
   ```

5. **Run the Application:**
   ```bash
   python app.py
   ```
   The application will be accessible at `http://localhost:5000`.

## Production Deployment
The application is pre-configured for Dockerized deployment. Simply map the port and environment variables:
```bash
docker build -t resume-builder .
docker run -p 10000:10000 --env-file .env resume-builder
```
