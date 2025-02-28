from flask import Flask, request, jsonify
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
# import os
load_dotenv()
app = Flask(__name__)
CORS(app)  
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')  # Use environment variable in production


# if not firebase_admin._apps:
    
#     cred = credentials.Certificate('serviceAccountKey.json')
#     firebase_admin.initialize_app(cred)
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

from patient_routes import patient_bp


app.register_blueprint(patient_bp)

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
            
        except Exception as e:
            return jsonify({'message': f'Token is invalid! {str(e)}'}), 401
            
        return f(current_user, *args, **kwargs)
    
    return decorated


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
    
   
    hashed_password = generate_password_hash(data.get('password'), method='pbkdf2:sha256')
    
    new_user = {
        'email': email,
        'password': hashed_password,
        'name': data.get('name', ''),
        'role': 'doctor',  # Default role
        'created_at': firestore.SERVER_TIMESTAMP
    }
    
  
    user_ref = users_ref.add(new_user)
    
    return jsonify({
        'message': 'User registered successfully',
        'user_id': user_ref[1].id
    }), 201


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Missing email or password'}), 400
    
    
    users_ref = db.collection('users')
    query = users_ref.where('email', '==', data.get('email')).limit(1).get()
    
    if len(query) == 0:
        return jsonify({'message': 'Invalid credentials'}), 401
    
    user_id = query[0].id
    user_data = query[0].to_dict()
    
  
    if not check_password_hash(user_data.get('password'), data.get('password')):
        return jsonify({'message': 'Invalid credentials'}), 401
    
   
    token = jwt.encode(
        {
            'user_id': user_id,
            'email': user_data.get('email'),
            'role': user_data.get('role', 'doctor'),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
        },
        app.config['SECRET_KEY'],
        algorithm="HS256"
    )
    
    return jsonify({
        'token': token,
        'user': {
            'id': user_id,
            'email': user_data.get('email'),
            'name': user_data.get('name', ''),
            'role': user_data.get('role', 'doctor')
        }
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
    
   
    db.collection('users').document('placeholder').set({'placeholder': True})
    db.collection('patients').document('placeholder').set({'placeholder': True})
    
  
    db.collection('users').document('placeholder').delete()
    db.collection('patients').document('placeholder').delete()
    
    return jsonify({'message': 'Database initialized successfully'}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)