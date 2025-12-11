# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
import jwt
from functools import wraps
from datetime import datetime, timedelta
from groq import Groq
import PyPDF2
import hashlib
import sqlite3
from pathlib import Path
import json
import pyotp
import qrcode
import io
import base64
import smtplib
from email.mime.text import MIMEText
import secrets
import time
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import new modules
from evaluation_engine import EvaluationEngine
from improvement_generator import ImprovementPlanGenerator

app = Flask(__name__)
CORS(app)

# Configuration
app.config['SECRET_KEY'] = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'secure_uploads'
app.config['DATABASE'] = 'interview_system.db'
app.config['GROQ_API_KEY'] = os.environ.get('GROQ_API_KEY', '')
app.config['JWT_EXPIRATION_HOURS'] = 24

# ============ ZERO TRUST ARCHITECTURE CONFIGURATION ============
# Token expiry times
app.config['ACCESS_TOKEN_EXPIRY'] = 900  # 15 minutes in seconds
app.config['REFRESH_TOKEN_EXPIRY'] = 604800  # 7 days in seconds
app.config['SESSION_EXPIRY'] = 86400  # 24 hours in seconds

# Encryption key for sensitive data (store in environment variable in production)
app.config['ENCRYPTION_KEY'] = os.environ.get('ENCRYPTION_KEY', Fernet.generate_key())
cipher_suite = Fernet(app.config['ENCRYPTION_KEY'])

# Rate limiting configuration
RATE_LIMITS = {
    'login': {'requests': 5, 'window': 900},  # 5 per 15 minutes
    'upload_resume': {'requests': 5, 'window': 3600},  # 5 per hour
    'start_interview': {'requests': 10, 'window': 86400},  # 10 per day
    'submit_answer': {'requests': 100, 'window': 3600},  # 100 per hour
    'default': {'requests': 1000, 'window': 3600}  # 1000 per hour
}

# Session management
app.config['MAX_CONCURRENT_SESSIONS'] = 3

# Ensure upload directory exists
Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)

# Database initialization
def init_db():
    with sqlite3.connect(app.config['DATABASE']) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS interviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                job_role TEXT NOT NULL,
                resume_path TEXT NOT NULL,
                score FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS interview_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interview_id INTEGER,
                question TEXT NOT NULL,
                answer TEXT,
                score FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (interview_id) REFERENCES interviews (id)
            )
        ''')

        # Add new columns if they do not exist
        try:
            conn.execute("ALTER TABLE users ADD COLUMN totp_secret TEXT;")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            conn.execute("ALTER TABLE users ADD COLUMN totp_verified BOOLEAN DEFAULT FALSE;")
        except sqlite3.OperationalError:
            pass  # Column already exists


        try:
            conn.execute("ALTER TABLE interviews ADD COLUMN violations INTEGER DEFAULT 0;")
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute("ALTER TABLE interviews ADD COLUMN violation_summary TEXT DEFAULT '';")
        except sqlite3.OperationalError:
            pass
        
        # New columns for role-based interviews
        try:
            conn.execute("ALTER TABLE interviews ADD COLUMN role_id TEXT;")
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute("ALTER TABLE interviews ADD COLUMN difficulty_level TEXT;")
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute("ALTER TABLE interviews ADD COLUMN duration_minutes INTEGER;")
        except sqlite3.OperationalError:
            pass
        
        # New columns for interview customization
        try:
            conn.execute("ALTER TABLE interviews ADD COLUMN job_description TEXT;")
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute("ALTER TABLE interviews ADD COLUMN focus_areas TEXT;")
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute("ALTER TABLE interviews ADD COLUMN evaluation_weights TEXT;")
        except sqlite3.OperationalError:
            pass
        
        # Time-based interview columns
        try:
            conn.execute("ALTER TABLE interviews ADD COLUMN total_time_limit_minutes INTEGER DEFAULT 30;")
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute("ALTER TABLE interviews ADD COLUMN started_at TIMESTAMP;")
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute("ALTER TABLE interviews ADD COLUMN completed_at TIMESTAMP;")
        except sqlite3.OperationalError:
            pass
        
        # Follow-up question tracking columns
        try:
            conn.execute("ALTER TABLE interview_questions ADD COLUMN question_type TEXT DEFAULT 'main';")
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute("ALTER TABLE interview_questions ADD COLUMN parent_question_id INTEGER;")
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute("ALTER TABLE interview_questions ADD COLUMN time_limit_seconds INTEGER DEFAULT 300;")
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute("ALTER TABLE interview_questions ADD COLUMN time_spent_seconds INTEGER;")
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute("ALTER TABLE interview_questions ADD COLUMN requires_followup BOOLEAN DEFAULT FALSE;")
        except sqlite3.OperationalError:
            pass
        
        # Create evaluation_metrics table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interview_id INTEGER,
                communication_score FLOAT,
                technical_score FLOAT,
                confidence_score FLOAT,
                average_overall FLOAT,
                performance_level TEXT,
                total_questions INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (interview_id) REFERENCES interviews (id)
            )
        ''')
        
        # Create improvement_plans table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS improvement_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interview_id INTEGER,
                weak_areas TEXT,
                improvement_steps TEXT,
                recommended_resources TEXT,
                practice_plan TEXT,
                overall_recommendation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (interview_id) REFERENCES interviews (id)
            )
        ''')
        
        # Learning paths table for personalized feedback
        conn.execute('''
            CREATE TABLE IF NOT EXISTS learning_paths (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interview_id INTEGER NOT NULL,
                strengths TEXT,
                weaknesses TEXT,
                roadmap TEXT,
                recommended_resources TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (interview_id) REFERENCES interviews (id)
            )
        ''')
        
        
        # Interview rounds table for multi-round interviews
        conn.execute('''
            CREATE TABLE IF NOT EXISTS interview_rounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interview_id INTEGER NOT NULL,
                round_name TEXT NOT NULL,
                round_type TEXT NOT NULL,
                round_order INTEGER NOT NULL,
                duration_minutes INTEGER,
                question_count INTEGER,
                focus_areas TEXT,
                status TEXT DEFAULT 'pending',
                score FLOAT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (interview_id) REFERENCES interviews (id)
            )
        ''')
        
        # Add columns to interview_questions for detailed evaluation
        try:
            conn.execute("ALTER TABLE interview_questions ADD COLUMN technical_score FLOAT;")
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute("ALTER TABLE interview_questions ADD COLUMN communication_score FLOAT;")
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute("ALTER TABLE interview_questions ADD COLUMN confidence_score FLOAT;")
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute("ALTER TABLE interview_questions ADD COLUMN feedback TEXT;")
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute("ALTER TABLE interview_questions ADD COLUMN topic TEXT;")
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute("ALTER TABLE interview_questions ADD COLUMN round_id INTEGER;")
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute("ALTER TABLE interview_questions ADD COLUMN expected_points TEXT;")
        except sqlite3.OperationalError:
            pass
        
        # Create custom_roles table for user-created interview roles
        conn.execute('''
            CREATE TABLE IF NOT EXISTS custom_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                description TEXT,
                icon TEXT DEFAULT '🎯',
                evaluation_criteria TEXT, -- JSON object with weights
                is_public BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create custom_questions table for user-created questions
        conn.execute('''
            CREATE TABLE IF NOT EXISTS custom_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id INTEGER,
                question TEXT NOT NULL,
                topic TEXT,
                difficulty_level TEXT,
                expected_points TEXT, -- JSON array
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (role_id) REFERENCES custom_roles (id) ON DELETE CASCADE
            )
        ''')
        
        # Create custom_resources table for user-created learning resources
        conn.execute('''
            CREATE TABLE IF NOT EXISTS custom_resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT NOT NULL,
                type TEXT, -- course, book, article, video, platform
                url TEXT,
                description TEXT,
                tags TEXT, -- JSON array for filtering
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # ============ ZERO TRUST ARCHITECTURE TABLES ============
        
        # Refresh tokens table for token rotation
        conn.execute('''
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL UNIQUE,
                device_id TEXT,
                ip_address TEXT,
                user_agent TEXT,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                revoked BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Audit logs table for security monitoring
        conn.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                resource TEXT,
                resource_id INTEGER,
                ip_address TEXT,
                user_agent TEXT,
                details TEXT,
                success BOOLEAN DEFAULT TRUE,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Rate limit tracking table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS rate_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                request_count INTEGER DEFAULT 1,
                window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(identifier, endpoint)
            )
        ''')
        
        # User sessions table for session management
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_id TEXT NOT NULL UNIQUE,
                device_id TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # ============ ZTA PHASE 2: RBAC ============
        
        # User roles table for role-based access control
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT 'candidate',
                permissions TEXT,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                granted_by INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (granted_by) REFERENCES users (id)
            )
        ''')
        
        
        
init_db()


# ============ ZERO TRUST ARCHITECTURE HELPER FUNCTIONS ============

def log_audit(user_id, action, resource=None, resource_id=None, details=None, success=True):
    """Log security-relevant actions to audit log"""
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO audit_logs (user_id, action, resource, resource_id, ip_address, user_agent, details, success)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                action,
                resource,
                resource_id,
                request.remote_addr,
                request.headers.get('User-Agent', ''),
                details,
                success
            ))
    except Exception as e:
        print(f"Audit logging error: {str(e)}")


def check_rate_limit(identifier, endpoint='default'):
    """Check if request is within rate limit"""
    limit_config = RATE_LIMITS.get(endpoint, RATE_LIMITS['default'])
    max_requests = limit_config['requests']
    window_seconds = limit_config['window']
    
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Get current rate limit record
            cursor.execute('''
                SELECT request_count, window_start FROM rate_limits
                WHERE identifier = ? AND endpoint = ?
            ''', (identifier, endpoint))
            
            record = cursor.fetchone()
            current_time = datetime.now()
            
            if record:
                count, window_start = record
                window_start = datetime.fromisoformat(window_start)
                
                # Check if window has expired
                if (current_time - window_start).total_seconds() > window_seconds:
                    # Reset window
                    cursor.execute('''
                        UPDATE rate_limits
                        SET request_count = 1, window_start = ?
                        WHERE identifier = ? AND endpoint = ?
                    ''', (current_time, identifier, endpoint))
                    return True
                elif count < max_requests:
                    # Increment count
                    cursor.execute('''
                        UPDATE rate_limits
                        SET request_count = request_count + 1
                        WHERE identifier = ? AND endpoint = ?
                    ''', (identifier, endpoint))
                    return True
                else:
                    # Rate limit exceeded
                    return False
            else:
                # Create new record
                cursor.execute('''
                    INSERT INTO rate_limits (identifier, endpoint, request_count, window_start)
                    VALUES (?, ?, 1, ?)
                ''', (identifier, endpoint, current_time))
                return True
    except Exception as e:
        print(f"Rate limit check error: {str(e)}")
        return True  # Allow on error to avoid blocking legitimate users


def rate_limit(endpoint='default'):
    """Decorator for rate limiting endpoints"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Use user_id if authenticated, otherwise use IP
            identifier = request.remote_addr
            if hasattr(request, 'user_id'):
                identifier = f"user_{request.user_id}"
            
            if not check_rate_limit(identifier, endpoint):
                log_audit(
                    getattr(request, 'user_id', None),
                    'rate_limit_exceeded',
                    endpoint,
                    None,
                    f"Exceeded {RATE_LIMITS[endpoint]['requests']} requests",
                    False
                )
                return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def encrypt_data(data):
    """Encrypt sensitive data"""
    if data is None:
        return None
    return cipher_suite.encrypt(data.encode()).decode()


def decrypt_data(encrypted_data):
    """Decrypt sensitive data"""
    if encrypted_data is None:
        return None
    try:
        return cipher_suite.decrypt(encrypted_data.encode()).decode()
    except:
        return encrypted_data  # Return as-is if decryption fails (for backward compatibility)


def generate_tokens(user_id):
    """Generate access and refresh tokens"""
    # Access token (short-lived)
    access_payload = {
        'user_id': user_id,
        'type': 'access',
        'exp': datetime.utcnow() + timedelta(seconds=app.config['ACCESS_TOKEN_EXPIRY'])
    }
    access_token = jwt.encode(access_payload, app.config['SECRET_KEY'], algorithm='HS256')
    
    # Refresh token (long-lived)
    refresh_payload = {
        'user_id': user_id,
        'type': 'refresh',
        'jti': secrets.token_urlsafe(32),  # Unique token ID
        'exp': datetime.utcnow() + timedelta(seconds=app.config['REFRESH_TOKEN_EXPIRY'])
    }
    refresh_token = jwt.encode(refresh_payload, app.config['SECRET_KEY'], algorithm='HS256')
    
    # Store refresh token in database
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            expires_at = datetime.utcnow() + timedelta(seconds=app.config['REFRESH_TOKEN_EXPIRY'])
            device_id = request.headers.get('X-Device-ID', 'unknown')
            
            cursor.execute('''
                INSERT INTO refresh_tokens (user_id, token, device_id, ip_address, user_agent, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                refresh_token,
                device_id,
                request.remote_addr,
                request.headers.get('User-Agent', ''),
                expires_at
            ))
    except Exception as e:
        print(f"Error storing refresh token: {str(e)}")
    
    return access_token, refresh_token


def create_session(user_id):
    """Create a new user session"""
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Check concurrent sessions limit
            cursor.execute('''
                SELECT COUNT(*) FROM user_sessions
                WHERE user_id = ? AND active = TRUE AND expires_at > ?
            ''', (user_id, datetime.utcnow()))
            
            active_sessions = cursor.fetchone()[0]
            
            if active_sessions >= app.config['MAX_CONCURRENT_SESSIONS']:
                # Revoke oldest session
                cursor.execute('''
                    UPDATE user_sessions
                    SET active = FALSE
                    WHERE id = (
                        SELECT id FROM user_sessions
                        WHERE user_id = ? AND active = TRUE
                        ORDER BY created_at ASC
                        LIMIT 1
                    )
                ''', (user_id,))
            
            # Create new session
            session_id = secrets.token_urlsafe(32)
            device_id = request.headers.get('X-Device-ID', 'unknown')
            expires_at = datetime.utcnow() + timedelta(seconds=app.config['SESSION_EXPIRY'])
            
            cursor.execute('''
                INSERT INTO user_sessions (user_id, session_id, device_id, ip_address, user_agent, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                session_id,
                device_id,
                request.remote_addr,
                request.headers.get('User-Agent', ''),
                expires_at
            ))
            
            return session_id
    except Exception as e:
        print(f"Error creating session: {str(e)}")
        return None


# ============ ZTA PHASE 2: ADDITIONAL HELPER FUNCTIONS ============

def get_device_fingerprint():
    """Generate device fingerprint from request headers"""
    fingerprint_data = {
        'user_agent': request.headers.get('User-Agent', ''),
        'accept_language': request.headers.get('Accept-Language', ''),
        'accept_encoding': request.headers.get('Accept-Encoding', ''),
        'ip_address': request.remote_addr
    }
    fingerprint_string = json.dumps(fingerprint_data, sort_keys=True)
    return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:16]


def assign_default_role(user_id):
    """Assign default 'candidate' role to new user"""
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_roles (user_id, role, permissions)
                VALUES (?, 'candidate', ?)
            ''', (user_id, json.dumps(['take_interview', 'view_own_results'])))
    except Exception as e:
        print(f"Error assigning default role: {str(e)}")


def get_user_role(user_id):
    """Get user's role"""
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT role FROM user_roles WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result[0] if result else 'candidate'
    except:
        return 'candidate'


def require_role(*allowed_roles):
    """Decorator to check if user has required role"""
    def decorator(f):
        @wraps(f)
        def decorated_function(current_user_id, *args, **kwargs):
            user_role = get_user_role(current_user_id)
            if user_role not in allowed_roles:
                log_audit(current_user_id, 'unauthorized_access', f.__name__, None, 
                         f"Required role: {allowed_roles}, has: {user_role}", False)
                return jsonify({'error': 'Insufficient permissions'}), 403
            return f(current_user_id, *args, **kwargs)
        return decorated_function
    return decorator


def check_suspicious_activity(user_id):
    """Detect suspicious behavior patterns"""
    risk_score = 0
    
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Check 1: Multiple failed logins in last hour
            cursor.execute('''
                SELECT COUNT(*) FROM audit_logs
                WHERE user_id = ? AND action = 'login_failed'
                AND timestamp > datetime('now', '-1 hour')
            ''', (user_id,))
            failed_logins = cursor.fetchone()[0]
            if failed_logins > 3:
                risk_score += 30
            
            # Check 2: Login from new location (different IP)
            cursor.execute('''
                SELECT DISTINCT ip_address FROM audit_logs
                WHERE user_id = ? AND action = 'login_success'
                ORDER BY timestamp DESC LIMIT 5
            ''', (user_id,))
            recent_ips = [row[0] for row in cursor.fetchall()]
            current_ip = request.remote_addr
            
            if current_ip not in recent_ips and len(recent_ips) > 0:
                risk_score += 20  # New location
            
            # Check 3: Rapid API calls (potential bot)
            cursor.execute('''
                SELECT COUNT(*) FROM audit_logs
                WHERE user_id = ? AND timestamp > datetime('now', '-5 minutes')
            ''', (user_id,))
            recent_actions = cursor.fetchone()[0]
            if recent_actions > 50:
                risk_score += 40  # Too many actions
            
            return min(risk_score, 100)
    except:
        return 0


def cleanup_old_data():
    """Delete old data based on retention policy (30 days default)"""
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Delete old audit logs (keep 90 days)
            cursor.execute('''
                DELETE FROM audit_logs
                WHERE timestamp < datetime('now', '-90 days')
            ''')
            
            # Delete expired refresh tokens
            cursor.execute('''
                DELETE FROM refresh_tokens
                WHERE expires_at < datetime('now')
            ''')
            
            # Delete inactive sessions
            cursor.execute('''
                DELETE FROM user_sessions
                WHERE expires_at < datetime('now') OR active = FALSE
            ''')
            
            # Delete old rate limit records (keep 7 days)
            cursor.execute('''
                DELETE FROM rate_limits
                WHERE window_start < datetime('now', '-7 days')
            ''')
            
            print(f"Cleaned up old data at {datetime.now()}")
    except Exception as e:
        print(f"Error cleaning up data: {str(e)}")


def generate_personalized_feedback(interview_id):
    """Generate personalized feedback with strengths, weaknesses, and learning path"""
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Get interview data
            cursor.execute('''
                SELECT job_role, score FROM interviews WHERE id = ?
            ''', (interview_id,))
            interview_data = cursor.fetchone()
            
            if not interview_data:
                return None
            
            job_role, overall_score = interview_data
            
            # Get all questions and answers with scores
            cursor.execute('''
                SELECT question, answer, score, technical_score, communication_score, 
                       confidence_score, feedback, question_type
                FROM interview_questions
                WHERE interview_id = ?
                ORDER BY id
            ''', (interview_id,))
            questions_data = cursor.fetchall()
            
            # Prepare data for LLM analysis
            performance_summary = {
                'overall_score': overall_score or 0,
                'job_role': job_role,
                'questions': []
            }
            
            total_technical = 0
            total_communication = 0
            total_confidence = 0
            count = 0
            
            for q in questions_data:
                question, answer, score, tech, comm, conf, feedback, q_type = q
                if score is not None:
                    performance_summary['questions'].append({
                        'question': question,
                        'answer': answer,
                        'score': score,
                        'technical': tech or 0,
                        'communication': comm or 0,
                        'confidence': conf or 0,
                        'type': q_type or 'main'
                    })
                    
                    if tech: total_technical += tech
                    if comm: total_communication += comm
                    if conf: total_confidence += conf
                    count += 1
            
            avg_technical = total_technical / count if count > 0 else 0
            avg_communication = total_communication / count if count > 0 else 0
            avg_confidence = total_confidence / count if count > 0 else 0
            
            # Generate feedback using LLM
            prompt = f"""Analyze this interview performance and generate personalized feedback.

Job Role: {job_role}
Overall Score: {overall_score:.1f}/100

Average Scores:
- Technical: {avg_technical:.1f}/100
- Communication: {avg_communication:.1f}/100
- Confidence: {avg_confidence:.1f}/100

Performance Details:
{json.dumps(performance_summary['questions'], indent=2)}

Generate a JSON response with:
1. "strengths": Array of 3-5 specific strengths based on high scores (>=85) and good performance
2. "weaknesses": Array of 3-5 specific areas for improvement based on low scores (<60) and gaps
3. "roadmap": Object with three arrays:
   - "immediate": 3-4 actionable items for 1-2 weeks (critical weaknesses)
   - "short_term": 3-4 goals for 1-3 months (skill building)
   - "long_term": 2-3 mastery goals for 3-6 months
4. "resources": Array of 5-7 recommended resources (courses, books, platforms) with:
   - "title": Resource name
   - "type": "course", "book", "platform", or "video"
   - "description": Brief description
   - "url": URL or "N/A"
   - "priority": "high", "medium", or "low"

Respond with ONLY valid JSON, no other text."""

            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an expert career coach and technical interviewer. Generate detailed, actionable feedback."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            feedback_json = response.choices[0].message.content.strip()
            
            # Parse JSON response
            try:
                feedback_data = json.loads(feedback_json)
            except json.JSONDecodeError:
                # Try to extract JSON if wrapped in markdown
                json_match = re.search(r'```json\n(.*?)\n```', feedback_json, re.DOTALL)
                if json_match:
                    feedback_data = json.loads(json_match.group(1))
                else:
                    feedback_data = json.loads(feedback_json)
            
            # Store in database
            cursor.execute('''
                INSERT INTO learning_paths (interview_id, strengths, weaknesses, roadmap, recommended_resources)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                interview_id,
                json.dumps(feedback_data.get('strengths', [])),
                json.dumps(feedback_data.get('weaknesses', [])),
                json.dumps(feedback_data.get('roadmap', {})),
                json.dumps(feedback_data.get('resources', []))
            ))
            
            return feedback_data
            
    except Exception as e:
        print(f"Error generating personalized feedback: {str(e)}")
        return None



def suggest_interview_rounds(job_role, job_description=""):
    """Use LLM to suggest appropriate interview rounds based on job role"""
    try:
        prompt = f"""Based on the following job role, suggest appropriate interview rounds.

Job Role: {job_role}
Job Description: {job_description or "Not provided"}

Suggest 3-5 interview rounds that are commonly used for this role. For each round, provide:
1. round_name: Name of the round (e.g., "HR Screening", "Technical Round")
2. round_type: Type (hr, technical, system_design, behavioral)
3. description: Brief description
4. duration_minutes: Suggested duration
5. question_count: Number of questions
6. focus_areas: Array of 3-4 key focus areas

Common round types:
- hr: HR screening, background check, culture fit
- technical: Coding, algorithms, technical concepts
- system_design: Architecture, scalability, design patterns
- behavioral: Leadership, teamwork, STAR method questions

Respond with ONLY valid JSON in this format:
{{
  "suggested_rounds": [
    {{
      "round_name": "HR Screening",
      "round_type": "hr",
      "description": "Initial screening to assess background and cultural fit",
      "duration_minutes": 20,
      "question_count": 5,
      "focus_areas": ["Background", "Motivation", "Culture fit", "Expectations"]
    }}
  ]
}}"""

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an expert HR consultant and technical recruiter. Suggest appropriate interview rounds based on job roles."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        result_json = response.choices[0].message.content.strip()
        
        # Parse JSON
        try:
            result = json.loads(result_json)
        except json.JSONDecodeError:
            json_match = re.search(r'```json\n(.*?)\n```', result_json, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                result = json.loads(result_json)
        
        return result.get('suggested_rounds', [])
        
    except Exception as e:
        print(f"Error suggesting rounds: {str(e)}")
        return []


def generate_round_questions(round_type, round_name, job_role, job_description, question_count=5):
    """Generate questions specific to the round type"""
    try:
        # Round-specific prompts
        round_prompts = {
            'hr': f"""Generate {question_count} HR screening questions for a {job_role} position.
Focus on: background, motivation, cultural fit, expectations, availability.
Questions should assess: work history, career goals, company fit, salary expectations, notice period.""",
            
            'technical': f"""Generate {question_count} technical interview questions for a {job_role} position.
Focus on: coding problems, algorithms, data structures, technical concepts, problem-solving.
Questions should be open-ended and test practical knowledge.
Job Description: {job_description or "Not provided"}""",
            
            'system_design': f"""Generate {question_count} system design questions for a {job_role} position.
Focus on: scalable architecture, design patterns, trade-offs, database design, API design.
Questions should test high-level thinking and architectural skills.
Job Description: {job_description or "Not provided"}""",
            
            'behavioral': f"""Generate {question_count} behavioral/managerial questions for a {job_role} position.
Focus on: leadership, teamwork, conflict resolution, decision-making, project management.
Use STAR method format (Situation, Task, Action, Result).
Job Description: {job_description or "Not provided"}"""
        }
        
        base_prompt = round_prompts.get(round_type, f"Generate {question_count} interview questions for {round_name}")
        
        prompt = f"""{base_prompt}

Generate exactly {question_count} questions in JSON format:
{{
  "questions": [
    {{
      "question": "Question text here",
      "expected_points": ["Point 1", "Point 2", "Point 3"]
    }}
  ]
}}

Respond with ONLY valid JSON, no other text."""

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": f"You are an expert interviewer conducting a {round_name}. Generate relevant, insightful questions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=2000
        )
        
        result_json = response.choices[0].message.content.strip()
        
        # Parse JSON
        try:
            result = json.loads(result_json)
        except json.JSONDecodeError:
            json_match = re.search(r'```json\n(.*?)\n```', result_json, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                result = json.loads(result_json)
        
        return result.get('questions', [])
        
    except Exception as e:
        print(f"Error generating round questions: {str(e)}")
        return []


# User Registration Endpoint
@app.route('/api/register', methods=['POST'])
@rate_limit('login')
def register():
    data = request.json
    
    if not all(k in data for k in ['email', 'password', 'name']):
        log_audit(None, 'registration_failed', 'user', None, 'Missing required fields', False)
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Check if user already exists
            cursor.execute('SELECT id FROM users WHERE email = ?', (data['email'],))
            if cursor.fetchone():
                log_audit(None, 'registration_failed', 'user', None, f"Email already exists: {data['email']}", False)
                return jsonify({'error': 'Email already registered'}), 409
            
            # Generate a random secret key for TOTP
            totp_secret = pyotp.random_base32()
            
            # Hash password and create user
            password_hash = generate_password_hash(data['password'])
            cursor.execute(
                'INSERT INTO users (email, password_hash, name, totp_secret, totp_verified) VALUES (?, ?, ?, ?, ?)',
                (data['email'], password_hash, data['name'], totp_secret, False)
            )
            
            user_id = cursor.lastrowid
            
            # Assign default role
            assign_default_role(user_id)
            
            # Log successful registration
            log_audit(user_id, 'user_registered', 'user', user_id, f"New user: {data['name']}", True)
            
            # Generate QR code
            totp = pyotp.TOTP(totp_secret)
            provisioning_uri = totp.provisioning_uri(data['email'], issuer_name="Interview Assistant")
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(provisioning_uri)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            buffered = io.BytesIO()
            img.save(buffered)
            qr_code_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            return jsonify({
                'message': 'User registered successfully',
                'user_id': user_id,
                'totp_secret': totp_secret,
                'qr_code': qr_code_base64
            }), 201
            
    except Exception as e:
        log_audit(None, 'registration_failed', 'user', None, str(e), False)
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
@rate_limit('login')
def login():
    data = request.json
    
    if not all(k in data for k in ['email', 'password']):
        return jsonify({'error': 'Missing email or password'}), 400
    
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, password_hash, name, totp_secret, totp_verified FROM users WHERE email = ?',
                (data['email'],)
            )
            user = cursor.fetchone()
            
            if not user or not check_password_hash(user[1], data['password']):
                log_audit(None, 'login_failed', 'user', None, f"Failed login attempt: {data['email']}", False)
                return jsonify({'error': 'Invalid email or password'}), 401
            
            # Check if TOTP verification is needed
            if user[4]:  # totp_verified is True
                if 'totp_code' not in data:
                    return jsonify({
                        'require_totp': True,
                        'message': 'Please enter your Google Authenticator code'
                    }), 200
                
                # Verify TOTP code
                totp = pyotp.TOTP(user[3])  # user[3] is totp_secret
                if not totp.verify(data['totp_code']):
                    log_audit(user[0], 'login_failed', 'user', user[0], 'Invalid TOTP code', False)
                    return jsonify({'error': 'Invalid authenticator code'}), 401
            
            user_id = user[0]
            
            # Check for suspicious activity
            risk_score = check_suspicious_activity(user_id)
            
            # Generate tokens (access + refresh)
            access_token, refresh_token = generate_tokens(user_id)
            
            # Create session
            session_id = create_session(user_id)
            
            # Get device fingerprint
            device_id = get_device_fingerprint()
            
            # Log successful login
            log_audit(user_id, 'login_success', 'user', user_id, f"Device: {device_id}", True)
            
            return jsonify({
                'access_token': access_token,
                'refresh_token': refresh_token,
                'session_id': session_id,
                'risk_score': risk_score,
                'require_additional_verification': risk_score > 70,
                'user': {
                    'id': user_id,
                    'email': data['email'],
                    'name': user[2],
                    'role': get_user_role(user_id)
                }
            })
                
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    

@app.route('/api/verify-totp', methods=['POST'])
def verify_totp():
    data = request.json
    
    if not all(k in data for k in ['email', 'totp_code']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, totp_secret FROM users WHERE email = ?',
                (data['email'],)
            )
            user = cursor.fetchone()
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Verify TOTP code
            totp = pyotp.TOTP(user[1])  # user[1] is totp_secret
            if totp.verify(data['totp_code']):
                # Mark TOTP as verified
                cursor.execute(
                    'UPDATE users SET totp_verified = ? WHERE id = ?',
                    (True, user[0])
                )
                
                return jsonify({
                    'message': 'TOTP verification successful',
                    'verified': True
                }), 200
            else:
                return jsonify({
                    'message': 'Invalid TOTP code',
                    'verified': False
                }), 400
                
    except Exception as e:
        return jsonify({'error': str(e)}), 500  

# JWT token required decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        try:
            token = token.split(" ")[1]  # Remove 'Bearer ' prefix
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user_id = data['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token'}), 401
        return f(current_user_id, *args, **kwargs)
    return decorated

# Password Reset Request Endpoint
@app.route('/api/reset-password-request', methods=['POST'])
def reset_password_request():
    data = request.json
    
    if 'email' not in data:
        return jsonify({'error': 'Email is required'}), 400
    
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM users WHERE email = ?', (data['email'],))
            user = cursor.fetchone()
            
            if user:
                # Generate reset token
                reset_token = jwt.encode({
                    'user_id': user[0],
                    'exp': datetime.utcnow() + timedelta(hours=1)
                }, app.config['SECRET_KEY'], algorithm="HS256")
                
                # In a production environment, send this token via email
                # For development, we'll return it directly
                return jsonify({
                    'message': 'Password reset link sent',
                    'reset_token': reset_token  # Remove this in production
                })
            else:
                # Don't reveal if email exists or not
                return jsonify({'message': 'If email exists, reset link will be sent'}), 200
                
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Password Reset Endpoint
@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    data = request.json
    
    if not all(k in data for k in ['reset_token', 'new_password']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        # Verify reset token
        token_data = jwt.decode(data['reset_token'], app.config['SECRET_KEY'], algorithms=["HS256"])
        user_id = token_data['user_id']
        
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            # Update password
            password_hash = generate_password_hash(data['new_password'])
            cursor.execute(
                'UPDATE users SET password_hash = ? WHERE id = ?',
                (password_hash, user_id)
            )
            
            return jsonify({'message': 'Password updated successfully'})
            
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Reset token has expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid reset token'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Initialize Groq client
groq_client = Groq(api_key=app.config['GROQ_API_KEY'])

# Initialize evaluation engine and improvement generator
evaluation_engine = EvaluationEngine(app.config['GROQ_API_KEY'])
improvement_generator = ImprovementPlanGenerator(app.config['GROQ_API_KEY'])

def extract_text_from_pdf(pdf_path):
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text

import json
import re
from datetime import datetime, UTC

def clean_json_response(response_text):
    """Clean and format LLM response into valid JSON"""
    # Extract content between JSON tags
    match = re.search(r'<JSON>(.*?)</JSON>', response_text, re.DOTALL)
    if not match:
        raise ValueError("No JSON tags found in response")
    
    json_str = match.group(1).strip()
    
    # Remove newlines and extra whitespace
    json_str = re.sub(r'\s+', ' ', json_str)
    
    # Fix escaped underscores
    json_str = json_str.replace('\\_', '_')
    
    # Ensure property names are properly quoted
    json_str = re.sub(r'(\w+)(?=\s*:)', r'"\1"', json_str)
    
    # Ensure string values are properly quoted
    json_str = re.sub(r':\s*([^"{[\s][^,}\]]*)(?=[,}\]])', r': "\1"', json_str)
    
    return json_str

def generate_questions(resume_text, job_role):
    prompt = f"""You must respond with only valid JSON wrapped in <JSON></JSON> tags.
    Generate 5 technical interview questions based on this resume and job role.
    
    Resume: {resume_text}
    Job Role: {job_role}
    
    Respond with EXACTLY this format (maintain all quotes):
    <JSON>
    {{"questions": [
        {{"question": "Question text here?", "expected_answer_points": ["point1", "point2", "point3"]}}
    ]}}
    </JSON>

    Rules:
    - Use ONLY double quotes, never single quotes
    - Include EXACTLY 5 questions
    - Each question MUST have EXACTLY 3 answer points
    - No special characters or escape sequences in strings
    - No newlines within the JSON structure"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a JSON generator. Always use double quotes for properties and strings. Never use single quotes or special characters."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3
        )
        
        content = response.choices[0].message.content
        
        # Clean and parse JSON
        json_str = clean_json_response(content)
        
        try:
            # First attempt to parse
            result = json.loads(json_str)
        except json.JSONDecodeError:
            # If first attempt fails, try additional cleaning
            json_str = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', json_str)
            result = json.loads(json_str)
        
        # Validate structure
        if not isinstance(result, dict) or 'questions' not in result:
            raise ValueError("Missing 'questions' array in JSON")
            
        questions = result['questions']
        if not isinstance(questions, list) or len(questions) != 5:
            raise ValueError("Must have exactly 5 questions")
            
        for i, q in enumerate(questions):
            if not isinstance(q, dict):
                raise ValueError(f"Question {i+1} is not an object")
            if 'question' not in q:
                raise ValueError(f"Question {i+1} missing 'question' field")
            if 'expected_answer_points' not in q:
                raise ValueError(f"Question {i+1} missing 'expected_answer_points' field")
            if not isinstance(q['expected_answer_points'], list):
                raise ValueError(f"Question {i+1} 'expected_answer_points' must be an array")
            if len(q['expected_answer_points']) != 3:
                raise ValueError(f"Question {i+1} must have exactly 3 answer points")
        
        # Return the cleaned and validated JSON
        return json.dumps(result, ensure_ascii=True)
        
    except Exception as e:
        print(f"Error in generate_questions: {str(e)}")
        print(f"Response content: {content}")
        raise ValueError(f"Failed to generate valid questions: {str(e)}")


def generate_followup_question(original_question, user_answer, evaluation_score):
    """
    Generate dynamic follow-up question based on user's answer quality
    """
    # Determine if follow-up is needed
    if evaluation_score >= 85:
        prompt_type = "deeper"
    elif evaluation_score < 60:
        prompt_type = "clarification"
    else:
        return None
    
    if prompt_type == "clarification":
        prompt = f"""The candidate gave an incomplete answer to an interview question.

Original Question: {original_question}
Candidate's Answer: {user_answer}

Generate ONE follow-up question to help them elaborate on the missing points.
Respond with ONLY the follow-up question text, no extra formatting."""
    else:
        prompt = f"""The candidate gave a strong answer to an interview question.

Original Question: {original_question}
Candidate's Answer: {user_answer}

Generate ONE follow-up question that probes deeper into an interesting point they mentioned.
Respond with ONLY the follow-up question text, no extra formatting."""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an expert interviewer who asks insightful follow-up questions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )
        
        followup = response.choices[0].message.content.strip().strip('"\'')
        return followup
    except Exception as e:
        print(f"Error generating follow-up: {str(e)}")
        return None


def evaluate_answer(question, expected_points, actual_answer):
    prompt = f"""You must wrap your numerical score in <SCORE></SCORE> tags.
    
    Evaluate this technical interview answer:
    Question: {question}
    Expected Answer Points: {expected_points}
    Candidate's Answer: {actual_answer}

    Calculate score (0-100) based on:
    - Technical accuracy (0-100)
    - Completeness vs expected points (0-100)
    - Clarity of explanation (0-100)

    Requirements:
    - Respond with EXACTLY this format: <SCORE>85.5</SCORE>
    - Must be a single number between 0 and 100
    - Include up to 2 decimal places
    - NO text outside the tags"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a scoring system. Respond only with a number between 0-100 wrapped in <SCORE></SCORE> tags."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1
        )
        
        # Extract score
        score_match = re.search(r'<SCORE>(.*?)</SCORE>', response.choices[0].message.content, re.DOTALL)
        if not score_match:
            raise ValueError("No SCORE tags found in response")
        
        score_str = score_match.group(1).strip()
        
        # Clean and validate score
        score = float(re.sub(r'[^\d.]', '', score_str))
        if score < 0 or score > 100:
            raise ValueError("Score must be between 0 and 100")
        
        return round(score, 2)
        
    except Exception as e:
        print(f"Error in evaluate_answer: {str(e)}")
        print(f"Response content: {response.choices[0].message.content}")
        raise ValueError(f"Failed to generate valid score: {str(e)}")

# # Fix for the deprecation warning
# def generate_token_expiration():
#     return datetime.now(UTC) + timedelta(hours=app.config['JWT_EXPIRATION_HOURS'])
    
@app.route('/api/upload-resume', methods=['POST'])
@token_required
@rate_limit('upload_resume')
def upload_resume(current_user_id):
    if 'resume' not in request.files:
        return jsonify({'error': 'Resume files is required'}), 400
    
    resume_file = request.files['resume']
    job_role = request.form.get('jobRole')
    job_description = request.form.get('jobDescription', '')
    focus_areas = request.form.get('focusAreas', '')
    evaluation_weights = request.form.get('evaluationWeights', '{"technical": 40, "communication": 30, "confidence": 30}')
    
    if not job_role:
        return jsonify({'error': 'No job role specified'}), 400

    if resume_file.filename == '':
        return jsonify({'error': 'File not selected'}), 400

    # Save files with secure filenames
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    resume_filename = secure_filename(resume_file.filename)
    resume_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{current_user_id}_{timestamp}_{resume_filename}")
    resume_file.save(resume_path)
    
    # Extract text and generate questions
    resume_text = extract_text_from_pdf(resume_path)
    
    # Include job description and focus areas in question generation
    context = f"Job Role: {job_role}\n"
    if job_description:
        context += f"Job Description: {job_description}\n"
    if focus_areas:
        context += f"Focus Areas: {focus_areas}\n"
    
    questions = generate_questions(resume_text, context)

    print(f"Raw questions: {questions}")

    # Ensure questions is a dictionary
    if isinstance(questions, str):
        questions = json.loads(questions)
    
    with sqlite3.connect(app.config['DATABASE']) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO interviews (user_id, job_role, resume_path, job_description, focus_areas, evaluation_weights)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (current_user_id, job_role, resume_path, job_description, focus_areas, evaluation_weights))
        interview_id = cursor.lastrowid

        # Store questions and capture the generated IDs
        questions_with_ids = []
        for question in questions['questions']:
            cursor.execute('''
                INSERT INTO interview_questions (interview_id, question)
                VALUES (?, ?)
            ''', (interview_id, question['question']))
            q_id = cursor.lastrowid
            questions_with_ids.append({'id': q_id, 'question': question['question']})
    
    return jsonify({
        'message': 'Resume uploaded and questions generated',
        'interview_id': interview_id,
        'questions': questions_with_ids,
    })
@app.route('/api/my-interviews', methods=['GET'])
@token_required
def my_interviews(current_user_id):
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM interviews WHERE user_id = ?", (current_user_id,))
            rows = cursor.fetchall()
            interviews = []
            for row in rows:
                interviews.append({
                    "id": row["id"],
                    "job_role": row["job_role"],
                    "resume_path": row["resume_path"],
                    "score": row["score"],
                    "created_at": row["created_at"],
                    "violations": row["violations"] if row["violations"] is not None else 0,
                    "violation_summary": row["violation_summary"] if row["violation_summary"] else "No security violations detected."
                })
            return jsonify({"interviews": interviews}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/api/report-violation', methods=['POST'])
@token_required
def report_violation(current_user_id):
    data = request.json
    interview_id = data.get('interviewId')
    violation_message = data.get('violation') or "Security violation detected."

    if not interview_id:
        return jsonify({'error': 'Missing interview ID'}), 400

    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            # Ensure the interview belongs to the current user
            cursor.execute('SELECT id, violations, violation_summary FROM interviews WHERE id = ? AND user_id = ?', (interview_id, current_user_id))
            interview = cursor.fetchone()
            if not interview:
                return jsonify({'error': 'Interview not found or unauthorized'}), 404

            # Increment violation count and update summary
            current_violations = interview[1] if interview[1] is not None else 0
            new_violations = current_violations + 1

            current_summary = interview[2] if interview[2] else ""
            new_violation_entry = f"{datetime.utcnow().isoformat()} - {violation_message}"
            new_summary = f"{current_summary} | {new_violation_entry}" if current_summary else new_violation_entry

            cursor.execute('UPDATE interviews SET violations = ?, violation_summary = ? WHERE id = ?', (new_violations, new_summary, interview_id))
            conn.commit()
            return jsonify({'message': 'Violation recorded', 'violations': new_violations, 'violation_summary': new_summary}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def send_final_score_email(recipient, score):
    SMTP_SERVER = "smtp.gmail.com"  # Use the correct SMTP server for your email provider
    SMTP_PORT = 587  # 465 for SSL, 587 for TLS
    EMAIL_ADDRESS = "abhisheksaraff18@gmail.com"
    EMAIL_PASSWORD = "wwtx zfew vgzq odzx"  # Use App Password if 2FA is enabled

    msg = MIMEText(f"Your final interview score is: {score:.1f} out of 100.")
    msg['Subject'] = "Your Interview Final Score"
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = recipient

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Secure the connection
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)  # Authenticate
            server.send_message(msg)
        print("Email sent successfully!")
    except Exception as e:
        print(f"Email sending failed: {str(e)}")

@app.route('/api/submit-answer', methods=['POST'])
@token_required
def submit_answer(current_user_id):
    data = request.json
    interview_id = data.get('interviewId')
    question_id = data.get('questionId')
    answer = data.get('answer')
    
    if not all([interview_id, question_id, answer]):
        return jsonify({'error': 'Missing required fields (interviewId, questionId, answer)'}), 400
    
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # First check if the interview exists and belongs to the user
            cursor.execute('''
                SELECT id, user_id 
                FROM interviews 
                WHERE id = ?
            ''', (interview_id,))
            interview = cursor.fetchone()
            
            if not interview:
                return jsonify({'error': f'Interview {interview_id} not found'}), 404
            
            if interview[1] != current_user_id:
                return jsonify({'error': 'Unauthorized access to interview'}), 403
            
            # Then check if the question exists for this interview
            cursor.execute('''
                SELECT id, question 
                FROM interview_questions 
                WHERE id = ? AND interview_id = ?
            ''', (question_id, interview_id))
            question = cursor.fetchone()
            
            if not question:
                # Debug query to see what questions exist for this interview
                cursor.execute('''
                    SELECT id, question 
                    FROM interview_questions 
                    WHERE interview_id = ?
                ''', (interview_id,))
                existing_questions = cursor.fetchall()
                
                return jsonify({
                    'error': f'Question {question_id} not found for interview {interview_id}',
                    'debug_info': {
                        'interview_id': interview_id,
                        'question_id': question_id,
                        'existing_questions': [{'id': q[0], 'question': q[1]} for q in existing_questions]
                    }
                }), 404
            
            # If we get here, both interview and question exist and belong to the user
            try:
                # Get expected points (can be null for now)
                cursor.execute('''
                    SELECT question
                    FROM interview_questions
                    WHERE id = ? AND interview_id = ?
                ''', (question_id, interview_id))
                
                question_text = cursor.fetchone()[0]
                
                # Evaluate answer
                score = evaluate_answer(question_text, [], answer)  # Using empty list for expected points for now
                
                # Store answer and score
                cursor.execute('''
                    UPDATE interview_questions
                    SET answer = ?, score = ?
                    WHERE id = ? AND interview_id = ?
                ''', (answer, score, question_id, interview_id))
                
                # Update overall interview score
                cursor.execute('''
                    UPDATE interviews
                    SET score = (
                        SELECT AVG(score)
                        FROM interview_questions
                        WHERE interview_id = ? AND score IS NOT NULL
                    )
                    WHERE id = ?
                ''', (interview_id, interview_id))
                
                return jsonify({
                    'message': 'Answer submitted and evaluated successfully',
                    'score': score,
                    'interviewId': interview_id,
                    'questionId': question_id
                })
                
            except Exception as e:
                return jsonify({
                    'error': f'Error processing answer: {str(e)}',
                    'debug_info': {
                        'interview_id': interview_id,
                        'question_id': question_id
                    }
                }), 500
                
    except Exception as e:
        return jsonify({
            'error': f'Database error: {str(e)}',
            'debug_info': {
                'interview_id': interview_id,
                'question_id': question_id
            }
        }), 500

@app.route('/api/calculate-final-score', methods=['POST'])
@token_required
def calculate_final_score(current_user_id):
    data = request.json
    interview_id = data.get('interviewId')
    
    if not interview_id:
        return jsonify({'error': 'Missing interview ID'}), 400
    
    with sqlite3.connect(app.config['DATABASE']) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT AVG(score)
            FROM interview_questions
            WHERE interview_id = ? AND score IS NOT NULL
        ''', (interview_id,))
        
        final_score = cursor.fetchone()[0]
        
        if final_score is not None:
            cursor.execute('''
                UPDATE interviews
                SET score = ?
                WHERE id = ? AND user_id = ?
            ''', (final_score, interview_id, current_user_id))
            
            # Retrieve user's email
            cursor.execute('SELECT email FROM users WHERE id = ?', (current_user_id,))
            user_email = cursor.fetchone()[0]
            
            # Send email with the final score
            send_final_score_email(user_email, final_score)
            
            return jsonify({
                'message': 'Final score calculated',
                'score': final_score
            })
        else:
            return jsonify({'error': 'No scored answers found'}), 404

@app.route('/api/interview-violations/<interview_id>', methods=['GET'])
@token_required
def get_interview_violations(current_user_id, interview_id):
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            # Ensure the interview belongs to the current user
            cursor.execute('SELECT violations, violation_summary FROM interviews WHERE id = ? AND user_id = ?', 
                          (interview_id, current_user_id))
            result = cursor.fetchone()
            
            if not result:
                return jsonify({'error': 'Interview not found or unauthorized'}), 404
                
            violations, violation_summary = result
            
            return jsonify({
                'violations': violations if violations is not None else 0,
                'violation_summary': violation_summary if violation_summary else ""
            }), 200
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        

# ============ NEW ENDPOINTS FOR ROLE-BASED INTERVIEWS ============

# ============ DYNAMIC ROLE MANAGEMENT ENDPOINTS ============

@app.route('/api/roles', methods=['GET'])
@token_required
def get_roles(current_user_id):
    """Get all available roles (user's custom roles)"""
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get user's custom roles
            cursor.execute('''
                SELECT id, name, description, icon, evaluation_criteria, created_at
                FROM custom_roles
                WHERE user_id = ? OR is_public = TRUE
                ORDER BY created_at DESC
            ''', (current_user_id,))
            
            roles = []
            for row in cursor.fetchall():
                roles.append({
                    'id': row['id'],
                    'name': row['name'],
                    'description': row['description'],
                    'icon': row['icon'],
                    'evaluation_criteria': json.loads(row['evaluation_criteria']) if row['evaluation_criteria'] else None
                })
            
            return jsonify({'roles': roles}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/roles', methods=['POST'])
@token_required
def create_role(current_user_id):
    """Create a new custom role"""
    data = request.json
    
    if 'name' not in data:
        return jsonify({'error': 'Role name is required'}), 400
    
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Default evaluation criteria
            default_criteria = {
                'technical_weight': 0.4,
                'communication_weight': 0.3,
                'confidence_weight': 0.3
            }
            
            evaluation_criteria = data.get('evaluation_criteria', default_criteria)
            
            cursor.execute('''
                INSERT INTO custom_roles (user_id, name, description, icon, evaluation_criteria, is_public)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                current_user_id,
                data['name'],
                data.get('description', ''),
                data.get('icon', '🎯'),
                json.dumps(evaluation_criteria),
                data.get('is_public', False)
            ))
            
            role_id = cursor.lastrowid
            
            return jsonify({
                'message': 'Role created successfully',
                'role_id': role_id
            }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/roles/<int:role_id>', methods=['GET'])
@token_required
def get_role(current_user_id, role_id):
    """Get detailed information about a specific role"""
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM custom_roles
                WHERE id = ? AND (user_id = ? OR is_public = TRUE)
            ''', (role_id, current_user_id))
            
            role = cursor.fetchone()
            if not role:
                return jsonify({'error': 'Role not found'}), 404
            
            # Get questions for this role
            cursor.execute('''
                SELECT id, question, topic, difficulty_level, expected_points
                FROM custom_questions
                WHERE role_id = ?
                ORDER BY difficulty_level, id
            ''', (role_id,))
            
            questions = []
            for q in cursor.fetchall():
                questions.append({
                    'id': q['id'],
                    'question': q['question'],
                    'topic': q['topic'],
                    'difficulty_level': q['difficulty_level'],
                    'expected_points': json.loads(q['expected_points']) if q['expected_points'] else []
                })
            
            return jsonify({
                'role': {
                    'id': role['id'],
                    'name': role['name'],
                    'description': role['description'],
                    'icon': role['icon'],
                    'evaluation_criteria': json.loads(role['evaluation_criteria']) if role['evaluation_criteria'] else None,
                    'questions': questions
                }
            }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/roles/<int:role_id>', methods=['PUT'])
@token_required
def update_role(current_user_id, role_id):
    """Update a role"""
    data = request.json
    
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Verify ownership
            cursor.execute('SELECT user_id FROM custom_roles WHERE id = ?', (role_id,))
            role = cursor.fetchone()
            
            if not role or role[0] != current_user_id:
                return jsonify({'error': 'Role not found or unauthorized'}), 404
            
            # Update fields
            update_fields = []
            params = []
            
            if 'name' in data:
                update_fields.append('name = ?')
                params.append(data['name'])
            if 'description' in data:
                update_fields.append('description = ?')
                params.append(data['description'])
            if 'icon' in data:
                update_fields.append('icon = ?')
                params.append(data['icon'])
            if 'evaluation_criteria' in data:
                update_fields.append('evaluation_criteria = ?')
                params.append(json.dumps(data['evaluation_criteria']))
            if 'is_public' in data:
                update_fields.append('is_public = ?')
                params.append(data['is_public'])
            
            if update_fields:
                params.append(role_id)
                cursor.execute(f'''
                    UPDATE custom_roles
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                ''', params)
            
            return jsonify({'message': 'Role updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/roles/<int:role_id>', methods=['DELETE'])
@token_required
def delete_role(current_user_id, role_id):
    """Delete a role"""
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Verify ownership
            cursor.execute('SELECT user_id FROM custom_roles WHERE id = ?', (role_id,))
            role = cursor.fetchone()
            
            if not role or role[0] != current_user_id:
                return jsonify({'error': 'Role not found or unauthorized'}), 404
            
            cursor.execute('DELETE FROM custom_roles WHERE id = ?', (role_id,))
            
            return jsonify({'message': 'Role deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ QUESTION MANAGEMENT ENDPOINTS ============

@app.route('/api/roles/<int:role_id>/questions', methods=['POST'])
@token_required
def add_question(current_user_id, role_id):
    """Add a question to a role"""
    data = request.json
    
    if 'question' not in data:
        return jsonify({'error': 'Question text is required'}), 400
    
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Verify role ownership
            cursor.execute('SELECT user_id FROM custom_roles WHERE id = ?', (role_id,))
            role = cursor.fetchone()
            
            if not role or role[0] != current_user_id:
                return jsonify({'error': 'Role not found or unauthorized'}), 404
            
            cursor.execute('''
                INSERT INTO custom_questions (role_id, question, topic, difficulty_level, expected_points)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                role_id,
                data['question'],
                data.get('topic', ''),
                data.get('difficulty_level', 'medium'),
                json.dumps(data.get('expected_points', []))
            ))
            
            question_id = cursor.lastrowid
            
            return jsonify({
                'message': 'Question added successfully',
                'question_id': question_id
            }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/questions/<int:question_id>', methods=['PUT'])
@token_required
def update_question(current_user_id, question_id):
    """Update a question"""
    data = request.json
    
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Verify ownership through role
            cursor.execute('''
                SELECT cr.user_id
                FROM custom_questions cq
                JOIN custom_roles cr ON cq.role_id = cr.id
                WHERE cq.id = ?
            ''', (question_id,))
            
            result = cursor.fetchone()
            if not result or result[0] != current_user_id:
                return jsonify({'error': 'Question not found or unauthorized'}), 404
            
            # Update fields
            update_fields = []
            params = []
            
            if 'question' in data:
                update_fields.append('question = ?')
                params.append(data['question'])
            if 'topic' in data:
                update_fields.append('topic = ?')
                params.append(data['topic'])
            if 'difficulty_level' in data:
                update_fields.append('difficulty_level = ?')
                params.append(data['difficulty_level'])
            if 'expected_points' in data:
                update_fields.append('expected_points = ?')
                params.append(json.dumps(data['expected_points']))
            
            if update_fields:
                params.append(question_id)
                cursor.execute(f'''
                    UPDATE custom_questions
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                ''', params)
            
            return jsonify({'message': 'Question updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/questions/<int:question_id>', methods=['DELETE'])
@token_required
def delete_question(current_user_id, question_id):
    """Delete a question"""
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Verify ownership through role
            cursor.execute('''
                SELECT cr.user_id
                FROM custom_questions cq
                JOIN custom_roles cr ON cq.role_id = cr.id
                WHERE cq.id = ?
            ''', (question_id,))
            
            result = cursor.fetchone()
            if not result or result[0] != current_user_id:
                return jsonify({'error': 'Question not found or unauthorized'}), 404
            
            cursor.execute('DELETE FROM custom_questions WHERE id = ?', (question_id,))
            
            return jsonify({'message': 'Question deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ RESOURCE MANAGEMENT ENDPOINTS ============

@app.route('/api/resources', methods=['GET'])
@token_required
def get_resources(current_user_id):
    """Get all learning resources"""
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM custom_resources
                WHERE user_id = ?
                ORDER BY created_at DESC
            ''', (current_user_id,))
            
            resources = []
            for row in cursor.fetchall():
                resources.append({
                    'id': row['id'],
                    'title': row['title'],
                    'type': row['type'],
                    'url': row['url'],
                    'description': row['description'],
                    'tags': json.loads(row['tags']) if row['tags'] else []
                })
            
            return jsonify({'resources': resources}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/resources', methods=['POST'])
@token_required
def create_resource(current_user_id):
    """Create a new learning resource"""
    data = request.json
    
    if 'title' not in data:
        return jsonify({'error': 'Resource title is required'}), 400
    
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO custom_resources (user_id, title, type, url, description, tags)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                current_user_id,
                data['title'],
                data.get('type', 'article'),
                data.get('url', ''),
                data.get('description', ''),
                json.dumps(data.get('tags', []))
            ))
            
            resource_id = cursor.lastrowid
            
            return jsonify({
                'message': 'Resource created successfully',
                'resource_id': resource_id
            }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/resources/<int:resource_id>', methods=['PUT'])
@token_required
def update_resource(current_user_id, resource_id):
    """Update a resource"""
    data = request.json
    
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Verify ownership
            cursor.execute('SELECT user_id FROM custom_resources WHERE id = ?', (resource_id,))
            resource = cursor.fetchone()
            
            if not resource or resource[0] != current_user_id:
                return jsonify({'error': 'Resource not found or unauthorized'}), 404
            
            # Update fields
            update_fields = []
            params = []
            
            if 'title' in data:
                update_fields.append('title = ?')
                params.append(data['title'])
            if 'type' in data:
                update_fields.append('type = ?')
                params.append(data['type'])
            if 'url' in data:
                update_fields.append('url = ?')
                params.append(data['url'])
            if 'description' in data:
                update_fields.append('description = ?')
                params.append(data['description'])
            if 'tags' in data:
                update_fields.append('tags = ?')
                params.append(json.dumps(data['tags']))
            
            if update_fields:
                params.append(resource_id)
                cursor.execute(f'''
                    UPDATE custom_resources
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                ''', params)
            
            return jsonify({'message': 'Resource updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/resources/<int:resource_id>', methods=['DELETE'])
@token_required
def delete_resource(current_user_id, resource_id):
    """Delete a resource"""
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Verify ownership
            cursor.execute('SELECT user_id FROM custom_resources WHERE id = ?', (resource_id,))
            resource = cursor.fetchone()
            
            if not resource or resource[0] != current_user_id:
                return jsonify({'error': 'Resource not found or unauthorized'}), 404
            
            cursor.execute('DELETE FROM custom_resources WHERE id = ?', (resource_id,))
            
            return jsonify({'message': 'Resource deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ MULTI-ROUND INTERVIEW ENDPOINTS ============

@app.route('/api/suggest-rounds', methods=['POST'])
@token_required
def api_suggest_rounds(current_user_id):
    """Suggest appropriate interview rounds based on job role"""
    data = request.json
    job_role = data.get('jobRole')
    job_description = data.get('jobDescription', '')
    
    if not job_role:
        return jsonify({'error': 'Job role is required'}), 400
    
    try:
        suggested_rounds = suggest_interview_rounds(job_role, job_description)
        return jsonify({'suggested_rounds': suggested_rounds}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/start-multi-round-interview', methods=['POST'])
@token_required
@rate_limit('start_interview')
def start_multi_round_interview(current_user_id):
    """Start a multi-round interview with selected rounds"""
    data = request.json
    job_role = data.get('jobRole')
    job_description = data.get('jobDescription', '')
    selected_rounds = data.get('selectedRounds', [])
    
    if not job_role or not selected_rounds:
        return jsonify({'error': 'Job role and selected rounds are required'}), 400
    
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Create interview
            cursor.execute('''
                INSERT INTO interviews (user_id, job_role, status, created_at)
                VALUES (?, ?, 'in_progress', datetime('now'))
            ''', (current_user_id, job_role))
            
            interview_id = cursor.lastrowid
            
            # Create rounds
            round_ids = []
            for idx, round_data in enumerate(selected_rounds):
                cursor.execute('''
                    INSERT INTO interview_rounds (
                        interview_id, round_name, round_type, round_order,
                        duration_minutes, question_count, focus_areas, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
                ''', (
                    interview_id,
                    round_data['round_name'],
                    round_data['round_type'],
                    idx + 1,
                    round_data.get('duration_minutes', 30),
                    round_data.get('question_count', 5),
                    json.dumps(round_data.get('focus_areas', []))
                ))
                round_ids.append(cursor.lastrowid)
            
            return jsonify({
                'interview_id': interview_id,
                'round_ids': round_ids,
                'message': 'Multi-round interview created successfully'
            }), 200
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/start-round/<int:round_id>', methods=['POST'])
@token_required
def start_round(current_user_id, round_id):
    """Start a specific interview round and generate questions"""
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Get round details
            cursor.execute('''
                SELECT ir.*, i.job_role, i.user_id
                FROM interview_rounds ir
                JOIN interviews i ON ir.interview_id = i.id
                WHERE ir.id = ?
            ''', (round_id,))
            
            round_data = cursor.fetchone()
            if not round_data:
                return jsonify({'error': 'Round not found'}), 404
            
            # Verify ownership
            if round_data[10] != current_user_id:  # user_id from join
                return jsonify({'error': 'Unauthorized'}), 403
            
            round_name = round_data[2]
            round_type = round_data[3]
            question_count = round_data[6]
            job_role = round_data[9]
            
            # Generate questions for this round
            questions = generate_round_questions(
                round_type, round_name, job_role, '', question_count
            )
            
            # Store questions
            question_ids = []
            for q in questions:
                cursor.execute('''
                    INSERT INTO interview_questions (
                        interview_id, round_id, question, expected_points,
                        question_type, time_limit_seconds
                    ) VALUES (?, ?, ?, ?, 'main', 300)
                ''', (
                    round_data[1],  # interview_id
                    round_id,
                    q['question'],
                    json.dumps(q.get('expected_points', []))
                ))
                question_ids.append(cursor.lastrowid)
            
            # Update round status
            cursor.execute('''
                UPDATE interview_rounds
                SET status = 'in_progress', started_at = datetime('now')
                WHERE id = ?
            ''', (round_id,))
            
            # Get full question details
            cursor.execute('''
                SELECT id, question, expected_points
                FROM interview_questions
                WHERE id IN ({})
            '''.format(','.join('?' * len(question_ids))), question_ids)
            
            questions_with_ids = [
                {
                    'id': row[0],
                    'question': row[1],
                    'expected_points': json.loads(row[2]) if row[2] else []
                }
                for row in cursor.fetchall()
            ]
            
            return jsonify({
                'round_id': round_id,
                'round_name': round_name,
                'round_type': round_type,
                'questions': questions_with_ids
            }), 200
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/complete-round/<int:round_id>', methods=['POST'])
@token_required
def complete_round(current_user_id, round_id):
    """Complete a round and calculate score"""
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Get round and verify ownership
            cursor.execute('''
                SELECT ir.interview_id, i.user_id
                FROM interview_rounds ir
                JOIN interviews i ON ir.interview_id = i.id
                WHERE ir.id = ?
            ''', (round_id,))
            
            result = cursor.fetchone()
            if not result:
                return jsonify({'error': 'Round not found'}), 404
            
            interview_id, user_id = result
            if user_id != current_user_id:
                return jsonify({'error': 'Unauthorized'}), 403
            
            # Calculate round score
            cursor.execute('''
                SELECT AVG(score)
                FROM interview_questions
                WHERE round_id = ? AND score IS NOT NULL
            ''', (round_id,))
            
            avg_score = cursor.fetchone()[0] or 0
            
            # Update round
            cursor.execute('''
                UPDATE interview_rounds
                SET status = 'completed', score = ?, completed_at = datetime('now')
                WHERE id = ?
            ''', (avg_score, round_id))
            
            # Get next round
            cursor.execute('''
                SELECT id, round_name, round_type
                FROM interview_rounds
                WHERE interview_id = ? AND status = 'pending'
                ORDER BY round_order
                LIMIT 1
            ''', (interview_id,))
            
            next_round = cursor.fetchone()
            
            response = {
                'round_score': avg_score,
                'message': 'Round completed successfully'
            }
            
            if next_round:
                response['next_round'] = {
                    'id': next_round[0],
                    'name': next_round[1],
                    'type': next_round[2]
                }
            else:
                response['all_rounds_complete'] = True
            
            return jsonify(response), 200
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ INTERVIEW FLOW ENDPOINTS ============

@app.route('/api/start-role-interview', methods=['POST'])
@token_required
@rate_limit('start_interview')
def start_role_interview(current_user_id):
    """Start a role-based interview"""
    data = request.json
    
    if 'roleId' not in data:
        return jsonify({'error': 'Role ID is required'}), 400
    
    role_id = data['roleId']
    difficulty_level = data.get('difficultyLevel', 'medium')
    
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Get role information
            cursor.execute('''
                SELECT name, evaluation_criteria
                FROM custom_roles
                WHERE id = ? AND (user_id = ? OR is_public = TRUE)
            ''', (role_id, current_user_id))
            
            role = cursor.fetchone()
            if not role:
                return jsonify({'error': 'Role not found'}), 404
            
            role_name = role[0]
            
            # Get questions for this role and difficulty
            cursor.execute('''
                SELECT id, question, topic, expected_points
                FROM custom_questions
                WHERE role_id = ? AND (difficulty_level = ? OR difficulty_level IS NULL)
                ORDER BY id
            ''', (role_id, difficulty_level))
            
            questions = cursor.fetchall()
            
            if not questions:
                return jsonify({'error': 'No questions found for this role and difficulty level'}), 404
            
            # Create interview record with timestamp
            started_at = datetime.utcnow()
            cursor.execute('''
                INSERT INTO interviews (user_id, job_role, resume_path, role_id, difficulty_level, duration_minutes, started_at, total_time_limit_minutes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (current_user_id, role_name, None, role_id, difficulty_level, 30, started_at, 30))
            
            interview_id = cursor.lastrowid
            
            # Store questions in interview_questions table
            questions_with_ids = []
            for q in questions:
                cursor.execute('''
                    INSERT INTO interview_questions (interview_id, question, topic, expected_points)
                    VALUES (?, ?, ?, ?)
                ''', (interview_id, q[1], q[2], q[3]))
                
                q_id = cursor.lastrowid
                questions_with_ids.append({
                    'id': q_id,
                    'question': q[1],
                    'topic': q[2]
                })
            
            return jsonify({
                'message': 'Interview started successfully',
                'interview_id': interview_id,
                'role': role_name,
                'difficulty': difficulty_level,
                'questions': questions_with_ids
            }), 200
            
        return jsonify({'error': str(e)}), 500


@app.route('/api/submit-answer-enhanced', methods=['POST'])
@token_required
@rate_limit('submit_answer')
def submit_answer_enhanced(current_user_id):
    """Submit answer with enhanced multi-dimensional evaluation"""
    data = request.json
    interview_id = data.get('interviewId')
    question_id = data.get('questionId')
    answer = data.get('answer')
    
    if not all([interview_id, question_id, answer]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Verify interview belongs to user and get evaluation weights
            cursor.execute('SELECT id, role_id, evaluation_weights FROM interviews WHERE id = ? AND user_id = ?', 
                          (interview_id, current_user_id))
            interview = cursor.fetchone()
            
            if not interview:
                return jsonify({'error': 'Interview not found or unauthorized'}), 404
            
            role_id = interview[1]
            custom_weights = interview[2]
            
            # Get question details
            cursor.execute('''
                SELECT question, expected_points
                FROM interview_questions
                WHERE id = ? AND interview_id = ?
            ''', (question_id, interview_id))
            
            question_data = cursor.fetchone()
            if not question_data:
                return jsonify({'error': 'Question not found'}), 404
            
            question_text = question_data[0]
            expected_points = json.loads(question_data[1]) if question_data[1] else []
            
            # Get evaluation criteria - prioritize custom weights from interview
            evaluation_criteria = {'technical_weight': 0.4, 'communication_weight': 0.3, 'confidence_weight': 0.3}  # Default
            
            # First, try to use custom weights from interview
            if custom_weights:
                try:
                    evaluation_criteria = json.loads(custom_weights)
                except:
                    pass
            # If no custom weights, try role-based weights
            elif role_id:
                cursor.execute('SELECT evaluation_criteria FROM custom_roles WHERE id = ?', (role_id,))
                role_data = cursor.fetchone()
                if role_data and role_data[0]:
                    evaluation_criteria = json.loads(role_data[0])
            
            # Evaluate the answer using the enhanced evaluation engine
            evaluation_result = evaluation_engine.evaluate_response(
                question_text,
                answer,
                expected_points,
                evaluation_criteria
            )
            
            # Store answer and detailed scores
            cursor.execute('''
                UPDATE interview_questions
                SET answer = ?, 
                    score = ?,
                    technical_score = ?,
                    communication_score = ?,
                    confidence_score = ?,
                    feedback = ?
                WHERE id = ? AND interview_id = ?
            ''', (
                answer,
                evaluation_result['overall_score'],
                evaluation_result['technical_score'],
                evaluation_result['communication_score'],
                evaluation_result['confidence_score'],
                evaluation_result['feedback'],
                question_id,
                interview_id
            ))
            
            # Update overall interview score
            cursor.execute('''
                UPDATE interviews
                SET score = (
                    SELECT AVG(score)
                    FROM interview_questions
                    WHERE interview_id = ? AND score IS NOT NULL
                )
                WHERE id = ?
            ''', (interview_id, interview_id))
            
            # Generate follow-up question if needed
            followup_question = None
            followup_question_id = None
            overall_score = evaluation_result['overall_score']
            
            # Check if this is a main question (not already a follow-up)
            cursor.execute('SELECT question_type FROM interview_questions WHERE id = ?', (question_id,))
            q_type_result = cursor.fetchone()
            is_main_question = q_type_result and q_type_result[0] == 'main'
            
            if is_main_question and (overall_score < 60 or overall_score >= 85):
                followup_question = generate_followup_question(
                    question_text,
                    answer,
                    overall_score
                )
                
                if followup_question:
                    # Store follow-up question in database
                    cursor.execute('''
                        INSERT INTO interview_questions 
                        (interview_id, question, question_type, parent_question_id, time_limit_seconds, expected_points)
                        VALUES (?, ?, 'followup', ?, 120, ?)
                    ''', (interview_id, followup_question, question_id, json.dumps([])))
                    
                    followup_question_id = cursor.lastrowid
                    
                    # Mark main question as having follow-up
                    cursor.execute('''
                        UPDATE interview_questions
                        SET requires_followup = TRUE
                        WHERE id = ?
                    ''', (question_id,))
            
            response_data = {
                'message': 'Answer evaluated successfully',
                'evaluation': evaluation_result,
                'interviewId': interview_id,
                'questionId': question_id
            }
            
            # Add follow-up if generated
            if followup_question:
                response_data['followup'] = {
                    'question': followup_question,
                    'questionId': followup_question_id,
                    'timeLimit': 120  # 2 minutes for follow-up
                }
            
            return jsonify(response_data), 200
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/complete-interview', methods=['POST'])
@token_required
def complete_interview(current_user_id):
    """Complete interview and generate comprehensive evaluation and improvement plan"""
    data = request.json
    interview_id = data.get('interviewId')
    
    if not interview_id:
        return jsonify({'error': 'Missing interview ID'}), 400
    
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Verify interview belongs to user
            cursor.execute('SELECT id, role_id FROM interviews WHERE id = ? AND user_id = ?',
                          (interview_id, current_user_id))
            interview = cursor.fetchone()
            
            if not interview:
                return jsonify({'error': 'Interview not found or unauthorized'}), 404
            
            role_id = interview[1]
            
            # Get all question responses with scores
            cursor.execute('''
                SELECT question, answer, score, technical_score, communication_score, 
                       confidence_score, feedback
                FROM interview_questions
                WHERE interview_id = ? AND score IS NOT NULL
            ''', (interview_id,))
            
            responses = cursor.fetchall()
            
            if not responses:
                return jsonify({'error': 'No scored answers found'}), 404
            
            # Prepare response data for evaluation
            all_responses = []
            interview_data = []
            
            for resp in responses:
                response_dict = {
                    'overall_score': resp[2],
                    'technical_score': resp[3],
                    'communication_score': resp[4],
                    'confidence_score': resp[5]
                }
                all_responses.append(response_dict)
                
                interview_data.append({
                    'question': resp[0],
                    'answer': resp[1],
                    'feedback': resp[6]
                })
            
            # Calculate aggregate metrics
            evaluation_metrics = evaluation_engine.calculate_interview_metrics(all_responses)
            
            # Store evaluation metrics
            cursor.execute('''
                INSERT INTO evaluation_metrics 
                (interview_id, communication_score, technical_score, confidence_score, 
                 average_overall, performance_level, total_questions)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                interview_id,
                evaluation_metrics['average_communication'],
                evaluation_metrics['average_technical'],
                evaluation_metrics['average_confidence'],
                evaluation_metrics['average_overall'],
                evaluation_metrics['performance_level'],
                evaluation_metrics['total_questions']
            ))
            
            # Generate improvement plan
            improvement_plan = improvement_generator.generate_improvement_plan(
                interview_data,
                evaluation_metrics,
                role_id
            )
            
            # Store improvement plan
            cursor.execute('''
                INSERT INTO improvement_plans
                (interview_id, weak_areas, improvement_steps, recommended_resources, 
                 practice_plan, overall_recommendation)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                interview_id,
                json.dumps(improvement_plan['weak_areas']),
                json.dumps(improvement_plan['improvement_steps']),
                json.dumps(improvement_plan['recommended_resources']),
                improvement_plan['practice_plan'],
                improvement_plan['overall_recommendation']
            ))
            
            # Generate personalized feedback and learning path
            personalized_feedback = generate_personalized_feedback(interview_id)
            
            # Get user email for notification
            cursor.execute('SELECT email FROM users WHERE id = ?', (current_user_id,))
            user_email = cursor.fetchone()[0]
            
            # Send email with final score
            send_final_score_email(user_email, evaluation_metrics['average_overall'])
            
            response_data = {
                'message': 'Interview completed successfully',
                'evaluation_metrics': evaluation_metrics,
                'improvement_plan': improvement_plan
            }
            
            # Add personalized feedback if generated
            if personalized_feedback:
                response_data['personalized_feedback'] = personalized_feedback
            
            return jsonify(response_data), 200
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/personalized-feedback/<int:interview_id>', methods=['GET'])
@token_required
def get_personalized_feedback(current_user_id, interview_id):
    """Get personalized feedback and learning path for an interview"""
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cursor = conn.cursor()
            
            # Verify interview belongs to user
            cursor.execute('SELECT id FROM interviews WHERE id = ? AND user_id = ?',
                          (interview_id, current_user_id))
            if not cursor.fetchone():
                return jsonify({'error': 'Interview not found or unauthorized'}), 404
            
            # Get personalized feedback
            cursor.execute('''
                SELECT strengths, weaknesses, roadmap, recommended_resources, created_at
                FROM learning_paths
                WHERE interview_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            ''', (interview_id,))
            
            feedback_data = cursor.fetchone()
            
            if not feedback_data:
                # Generate if not exists
                personalized_feedback = generate_personalized_feedback(interview_id)
                if personalized_feedback:
                    return jsonify(personalized_feedback), 200
                else:
                    return jsonify({'error': 'Could not generate feedback'}), 500
            
            # Parse and return existing feedback
            return jsonify({
                'strengths': json.loads(feedback_data[0]),
                'weaknesses': json.loads(feedback_data[1]),
                'roadmap': json.loads(feedback_data[2]),
                'resources': json.loads(feedback_data[3]),
                'generated_at': feedback_data[4]
            }), 200
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/interview-results/<int:interview_id>', methods=['GET'])
@token_required
def get_interview_results(current_user_id, interview_id):
    """Get complete interview results including evaluation and improvement plan"""
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get interview details
            cursor.execute('''
                SELECT * FROM interviews 
                WHERE id = ? AND user_id = ?
            ''', (interview_id, current_user_id))
            
            interview = cursor.fetchone()
            if not interview:
                return jsonify({'error': 'Interview not found or unauthorized'}), 404
            
            # Get all questions and answers
            cursor.execute('''
                SELECT question, answer, score, technical_score, communication_score,
                       confidence_score, feedback, topic
                FROM interview_questions
                WHERE interview_id = ?
                ORDER BY id
            ''', (interview_id,))
            
            questions = cursor.fetchall()
            
            # Get evaluation metrics
            cursor.execute('''
                SELECT * FROM evaluation_metrics
                WHERE interview_id = ?
            ''', (interview_id,))
            
            metrics = cursor.fetchone()
            
            # Get improvement plan
            cursor.execute('''
                SELECT * FROM improvement_plans
                WHERE interview_id = ?
            ''', (interview_id,))
            
            improvement_plan = cursor.fetchone()
            
            # Format response
            result = {
                'interview': {
                    'id': interview['id'],
                    'role': interview['job_role'],
                    'difficulty': interview['difficulty_level'],
                    'score': interview['score'],
                    'created_at': interview['created_at']
                },
                'questions': [
                    {
                        'question': q['question'],
                        'answer': q['answer'],
                        'topic': q['topic'],
                        'scores': {
                            'overall': q['score'],
                            'technical': q['technical_score'],
                            'communication': q['communication_score'],
                            'confidence': q['confidence_score']
                        },
                        'feedback': q['feedback']
                    }
                    for q in questions
                ],
                'evaluation_metrics': {
                    'average_technical': metrics['technical_score'],
                    'average_communication': metrics['communication_score'],
                    'average_confidence': metrics['confidence_score'],
                    'average_overall': metrics['average_overall'],
                    'performance_level': metrics['performance_level'],
                    'total_questions': metrics['total_questions']
                } if metrics else None,
                'improvement_plan': {
                    'weak_areas': json.loads(improvement_plan['weak_areas']) if improvement_plan else [],
                    'improvement_steps': json.loads(improvement_plan['improvement_steps']) if improvement_plan else [],
                    'recommended_resources': json.loads(improvement_plan['recommended_resources']) if improvement_plan else [],
                    'practice_plan': improvement_plan['practice_plan'] if improvement_plan else '',
                    'overall_recommendation': improvement_plan['overall_recommendation'] if improvement_plan else ''
                } if improvement_plan else None
            }
            
            return jsonify(result), 200
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

        
if __name__ == '__main__':
    app.run(debug=True, ssl_context='adhoc')