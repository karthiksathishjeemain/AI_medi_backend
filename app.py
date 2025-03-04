# First, you need to install the required packages
# pip install flask flask-cors firebase-admin PyJWT python-dotenv flask-mail

from flask import Flask, request, jsonify, Blueprint
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import os
from functools import wraps
import json
from dotenv import load_dotenv
import random
import string
from flask_mail import Mail, Message

from logs import logs_bp
from patient_routes import patient_bp

load_dotenv()
app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Configure Flask-Mail
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 465))
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'your-email@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'your-app-password')
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'False').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'True').lower() == 'true'
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', app.config['MAIL_USERNAME'])

mail = Mail(app)

# Firebase initialization
if not firebase_admin._apps:
    if 'FIREBASE_CREDENTIALS' in os.environ:
        # For production (Vercel)
        cred_dict = json.loads(os.environ.get('FIREBASE_CREDENTIALS'))
        cred = credentials.Certificate(cred_dict)
    else:
        # For local development
        cred = credentials.Certificate('serviceAccountKey.json')
    
    firebase_admin.initialize_app(cred)

def get_db():
    return firestore.client()

db = get_db()

app.register_blueprint(patient_bp)

app.register_blueprint(logs_bp)
# Create a blueprint for MFA-related routes
mfa_bp = Blueprint('mfa', __name__)
JWT_EXPIRATION = datetime.timedelta(minutes=60*6)  # 360 minutes
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
            
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user_id = data['user_id']
           
            user_ref = db.collection('users').document(current_user_id).get()
            if not user_ref.exists:
                return jsonify({'message': 'User not found!'}), 401
                
            current_user = user_ref.to_dict()
            current_user['id'] = current_user_id
            
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!', 'code': 'TOKEN_EXPIRED'}), 401
        except Exception as e:
            return jsonify({'message': f'Token is invalid! {str(e)}'}), 401
            
        return f(current_user, *args, **kwargs)
    
    return decorated

@app.route('/api/refresh-token', methods=['POST'])
@token_required
def refresh_token(current_user):
    """Endpoint to refresh the JWT token based on current user activity"""
    
    # Generate a new JWT token with a fresh expiration time
    token = jwt.encode(
        {
            'user_id': current_user['id'],
            'email': current_user['email'],
            'role': current_user.get('role', 'doctor'),
            'exp': datetime.datetime.now() + JWT_EXPIRATION
        },
        app.config['SECRET_KEY'],
        algorithm="HS256"
    )
    
    return jsonify({
        'token': token,
        'message': 'Token refreshed successfully'
    }), 200


def generate_totp(length=6):
    """Generate a numeric TOTP of specified length"""
    return ''.join(random.choices(string.digits, k=length))

def send_email_totp(email, totp):
    """Send TOTP via email using Flask-Mail"""
    try:
        msg = Message(
            subject="Your Verification Code",
            recipients=[email]
        )
        msg.body = f"Your verification code is: {totp}\n\nThis code will expire in 10 minutes."
        mail.send(msg)
        return True, "Email sent successfully"
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False, str(e)

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
   
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Missing email or password'}), 400
    
    email = data.get('email')
    
    users_ref = db.collection('users')
    query = users_ref.where('email', '==', email).limit(1).get()
    
    if len(query) > 0:
        return jsonify({'message': 'User already exists'}), 409
    
    # Generate hashed password
    hashed_password = generate_password_hash(data.get('password'), method='pbkdf2:sha256')
    
    # Generate a temporary user record
    new_user = {
        'email': email,
        'password': hashed_password,
        'name': data.get('name', ''),
        'role': 'doctor',  # Default role
        'verified': False,  # User not verified until TOTP is confirmed
        'created_at': datetime.datetime.now()
    }
    
    # Generate TOTP
    totp = generate_totp()
    
    # Store TOTP in a temporary collection with expiration
    verification_data = {
        'email': email,
        'totp': totp,
        'created_at': datetime.datetime.now(),
        'expires_at': datetime.datetime.now() + datetime.timedelta(minutes=10),  # TOTP expires in 10 minutes
        'user_data': new_user
    }
    
    
    
    
    # Send TOTP via email
    success, message = send_email_totp(email, totp)
    
    if not success:
        return jsonify({
            'message': 'Failed to send verification code',
            'error': message
        }), 500
    # Add verification record to database
    verification_ref = db.collection('verification_tokens').add(verification_data)
    
    return jsonify({
        'message': 'Verification code sent to your email',
        'verification_id': verification_ref[1].id,
        'email': email
    }), 200

@app.route('/api/verify-registration', methods=['POST'])
def verify_registration():
    data = request.get_json()
    
    if not data or not data.get('verification_id') or not data.get('totp'):
        return jsonify({'message': 'Missing verification ID or code'}), 400
    
    verification_id = data.get('verification_id')
    totp = data.get('totp')
    
    # Get verification record
    verification_ref = db.collection('verification_tokens').document(verification_id).get()
    
    if not verification_ref.exists:
        return jsonify({'message': 'Invalid verification ID'}), 400
    
    verification_data = verification_ref.to_dict()
    
    # Check if TOTP has expired
    if datetime.datetime.now() > verification_data.get('expires_at').replace(tzinfo=None):
        return jsonify({'message': 'Verification code has expired'}), 400
    
    # Verify TOTP
    if verification_data.get('totp') != totp:
        return jsonify({'message': 'Invalid verification code'}), 400
    
    # Get user data from verification record
    user_data = verification_data.get('user_data')
    user_data['verified'] = True
    
    # Add user to database
    user_ref = db.collection('users').add(user_data)
    user_id = user_ref[1].id
    
    # Delete verification record
    db.collection('verification_tokens').document(verification_id).delete()
    
    return jsonify({
        'message': 'User registered successfully',
        'user_id': user_id
    }), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Missing email or password'}), 400
    
    # Find user by email
    users_ref = db.collection('users')
    query = users_ref.where('email', '==', data.get('email')).limit(1).get()
    
    if len(query) == 0:
        return jsonify({'message': 'Invalid credentials'}), 401
    
    user_id = query[0].id
    user_data = query[0].to_dict()
    
    # Verify password
    if not check_password_hash(user_data.get('password'), data.get('password')):
        return jsonify({'message': 'Invalid credentials'}), 401
    
    # Generate TOTP for login
    totp = generate_totp()
    
    # Store TOTP in a temporary collection with expiration
    login_verification = {
        'user_id': user_id,
        'email': user_data.get('email'),
        'totp': totp,
        'created_at': datetime.datetime.now(),
        'expires_at': datetime.datetime.now() + datetime.timedelta(minutes=10)  # TOTP expires in 10 minutes
    }
    
    # Add login verification record to database
    verification_ref = db.collection('login_verifications').add(login_verification)
    
    # Send TOTP via email
    success, message = send_email_totp(user_data.get('email'), totp)
    
    if not success:
        return jsonify({
            'message': 'Failed to send verification code',
            'error': message
        }), 500
    
    return jsonify({
        'message': 'Verification code sent to your email',
        'verification_id': verification_ref[1].id,
        'email': user_data.get('email')
    }), 200

@app.route('/api/verify-login', methods=['POST'])
def verify_login():
    data = request.get_json()
    
    if not data or not data.get('verification_id') or not data.get('totp'):
        return jsonify({'message': 'Missing verification ID or code'}), 400
    
    verification_id = data.get('verification_id')
    totp = data.get('totp')
    
    # Get login verification record
    verification_ref = db.collection('login_verifications').document(verification_id).get()
    
    if not verification_ref.exists:
        return jsonify({'message': 'Invalid verification ID'}), 400
    
    verification_data = verification_ref.to_dict()
    
    # Check if TOTP has expired
    if datetime.datetime.now() > verification_data.get('expires_at').replace(tzinfo=None):
        return jsonify({'message': 'Verification code has expired'}), 400
    
    # Verify TOTP
    if verification_data.get('totp') != totp:
        return jsonify({'message': 'Invalid verification code'}), 400
    
    # Get user data
    user_id = verification_data.get('user_id')
    user_ref = db.collection('users').document(user_id).get()
    
    if not user_ref.exists:
        return jsonify({'message': 'User not found'}), 401
    
    user_data = user_ref.to_dict()
    
    # Generate JWT token with the configured timeout
    token = jwt.encode(
        {
            'user_id': user_id,
            'email': user_data.get('email'),
            'role': user_data.get('role', 'doctor'),
            'exp': datetime.datetime.now() + JWT_EXPIRATION
        },
        app.config['SECRET_KEY'],
        algorithm="HS256"
    )
    
    # Delete login verification record
    db.collection('login_verifications').document(verification_id).delete()
    
    return jsonify({
        'token': token,
        'user': {
            'id': user_id,
            'email': user_data.get('email'),
            'name': user_data.get('name', ''),
            'role': user_data.get('role', 'doctor')
        }
    }), 200
@app.route('/api/resend-totp', methods=['POST'])
def resend_totp():
    data = request.get_json()
    
    if not data or not data.get('verification_id') or not data.get('type'):
        return jsonify({'message': 'Missing verification ID or type'}), 400
    
    verification_id = data.get('verification_id')
    verification_type = data.get('type')  # 'registration' or 'login'
    
    collection_name = 'verification_tokens' if verification_type == 'registration' else 'login_verifications'
    
    # Get verification record
    verification_ref = db.collection(collection_name).document(verification_id).get()
    
    if not verification_ref.exists:
        return jsonify({'message': 'Invalid verification ID'}), 400
    
    verification_data = verification_ref.to_dict()
    
    # Generate new TOTP
    totp = generate_totp()
    
    # Update expiration time and TOTP
    db.collection(collection_name).document(verification_id).update({
        'totp': totp,
        'created_at': datetime.datetime.now(),
        'expires_at': datetime.datetime.now() + datetime.timedelta(minutes=10)
    })
    
    # Send new TOTP via email
    success, message = send_email_totp(verification_data.get('email'), totp)
    
    if not success:
        return jsonify({
            'message': 'Failed to send verification code',
            'error': message
        }), 500
    
    return jsonify({
        'message': 'New verification code sent to your email',
        'verification_id': verification_id,
        'email': verification_data.get('email')
    }), 200

@app.route('/api/user', methods=['GET'])
@token_required
def get_user_profile(current_user):
    return jsonify({
        'id': current_user['id'],
        'email': current_user['email'],
        'name': current_user.get('name', ''),
        'role': current_user.get('role', 'doctor')
    }), 200

@app.route('/api/init-db', methods=['POST'])
def init_db():
    if request.headers.get('Admin-Secret') != app.config.get('ADMIN_SECRET', 'admin-secret-key'):
        return jsonify({'message': 'Unauthorized'}), 401
    
    # Initialize database collections
    db.collection('users').document('placeholder').set({'placeholder': True})
    db.collection('patients').document('placeholder').set({'placeholder': True})
    db.collection('verification_tokens').document('placeholder').set({'placeholder': True})
    db.collection('login_verifications').document('placeholder').set({'placeholder': True})
    
    # Clean up placeholder documents
    db.collection('users').document('placeholder').delete()
    db.collection('patients').document('placeholder').delete()
    db.collection('verification_tokens').document('placeholder').delete()
    db.collection('login_verifications').document('placeholder').delete()
    
    return jsonify({'message': 'Database initialized successfully'}), 200

# Function to clean up expired verification tokens (can be run periodically)
def cleanup_expired_verifications():
    current_time = datetime.datetime.now()
    
    # Clean up registration verifications
    expired_reg = db.collection('verification_tokens').where('expires_at', '<', current_time).get()
    for doc in expired_reg:
        doc.reference.delete()
    
    # Clean up login verifications
    expired_login = db.collection('login_verifications').where('expires_at', '<', current_time).get()
    for doc in expired_login:
        doc.reference.delete()

if __name__ == '__main__':
    app.run(debug=True, port=5000)