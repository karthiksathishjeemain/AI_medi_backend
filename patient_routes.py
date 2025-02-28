from flask import Blueprint, request, jsonify
from firebase_admin import firestore
import jwt
from functools import wraps
from datetime import datetime
import uuid



patient_bp = Blueprint('patient', __name__)


def get_db():
    return firestore.client()


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        from app import app 
        
        token = None
        db = get_db()
        
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


@patient_bp.route('/api/patients', methods=['POST'])
@token_required
def add_patient(current_user):
    db = get_db()
    data = request.get_json()
    
   
    if not data or not data.get('name') or not data.get('age'):
        return jsonify({'message': 'Patient name and age are required'}), 400
    
    
    new_patient = {
        'name': data.get('name'),
        'age': data.get('age'),
        'doctor_id': current_user['id'], 
        'created_at': firestore.SERVER_TIMESTAMP,
        'updated_at': firestore.SERVER_TIMESTAMP
    }
    
  
    if data.get('gender'):
        new_patient['gender'] = data.get('gender')
        
    if data.get('notes'):
        new_patient['notes'] = data.get('notes')
   
    patient_ref = db.collection('patients').add(new_patient)
    
  
    return jsonify({
        'message': 'Patient added successfully',
        'patient_id': patient_ref[1].id
    }), 201


@patient_bp.route('/api/patients', methods=['GET'])
@token_required
def get_patients(current_user):
    db = get_db()

    patients_ref = db.collection('patients').where('doctor_id', '==', current_user['id']).get()
    
    patients = []
    for doc in patients_ref:
        patient_data = doc.to_dict()
        patient_data['id'] = doc.id
        
     
        if patient_data.get('created_at'):
            patient_data['created_at'] = patient_data['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        if patient_data.get('updated_at'):
            patient_data['updated_at'] = patient_data['updated_at'].strftime('%Y-%m-%d %H:%M:%S')
            
        patients.append(patient_data)
    
    return jsonify({
        'patients': patients,
        'count': len(patients)
    }), 200


@patient_bp.route('/api/patients/<patient_id>', methods=['GET'])
@token_required
def get_patient(current_user, patient_id):
    db = get_db()
   
    patient_ref = db.collection('patients').document(patient_id).get()
    
   
    if not patient_ref.exists:
        return jsonify({'message': 'Patient not found'}), 404
    

    patient_data = patient_ref.to_dict()
    

    if patient_data.get('doctor_id') != current_user['id']:
        return jsonify({'message': 'Unauthorized access to patient record'}), 403
    
   
    patient_data['id'] = patient_id
    
    if patient_data.get('created_at'):
        patient_data['created_at'] = patient_data['created_at'].strftime('%Y-%m-%d %H:%M:%S')
    if patient_data.get('updated_at'):
        patient_data['updated_at'] = patient_data['updated_at'].strftime('%Y-%m-%d %H:%M:%S')
    
    return jsonify(patient_data), 200


@patient_bp.route('/api/patients/<patient_id>', methods=['PUT'])
@token_required
def update_patient(current_user, patient_id):
    db = get_db()
    data = request.get_json()
    
    if not data:
        return jsonify({'message': 'No data provided'}), 400
        
  
    patient_ref = db.collection('patients').document(patient_id)
    patient = patient_ref.get()
    
   
    if not patient.exists:
        return jsonify({'message': 'Patient not found'}), 404
        
    patient_data = patient.to_dict()
    
   
    if patient_data.get('doctor_id') != current_user['id']:
        return jsonify({'message': 'Unauthorized access to patient record'}), 403
        
    
    update_data = {}
    
    if data.get('name'):
        update_data['name'] = data.get('name')
        
    if data.get('age'):
        update_data['age'] = data.get('age')
        
    if data.get('gender'):
        update_data['gender'] = data.get('gender')
        
    if data.get('notes'):
        update_data['notes'] = data.get('notes')
        
    update_data['updated_at'] = firestore.SERVER_TIMESTAMP
    
   
    patient_ref.update(update_data)
    
    return jsonify({'message': 'Patient updated successfully'}), 200


@patient_bp.route('/api/patients/<patient_id>', methods=['DELETE'])
@token_required
def delete_patient(current_user, patient_id):
    db = get_db()
 
    patient_ref = db.collection('patients').document(patient_id)
    patient = patient_ref.get()

    if not patient.exists:
        return jsonify({'message': 'Patient not found'}), 404
        
    patient_data = patient.to_dict()
   
    if patient_data.get('doctor_id') != current_user['id']:
        return jsonify({'message': 'Unauthorized access to patient record'}), 403
        
   
    patient_ref.delete()
    
    return jsonify({'message': 'Patient deleted successfully'}), 200



@patient_bp.route('/api/patients/<patient_id>/session-note', methods=['POST'])
@token_required
def save_session_note(current_user, patient_id):
    db = get_db()
    data = request.get_json()
    
   
    if not data or not data.get('note'):
        return jsonify({'message': 'Session note is required'}), 400
    
    
    patient_ref = db.collection('patients').document(patient_id).get()
    if not patient_ref.exists:
        return jsonify({'message': 'Patient not found'}), 404
        
    patient_data = patient_ref.to_dict()
    if patient_data.get('doctor_id') != current_user['id']:
        return jsonify({'message': 'Unauthorized access to patient record'}), 403
 
    session_note = {
        'id': str(uuid.uuid4()),  
        'patient_id': patient_id,
        'doctor_id': current_user['id'],
        'note': data.get('note'),
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
 
    db.collection('session_notes').document(session_note['id']).set(session_note)
    
    return jsonify({
        'message': 'Session note saved successfully',
        'session_id': session_note['id']
    }), 201

@patient_bp.route('/api/session-notes/<session_id>', methods=['PUT'])
@token_required
def update_session_note(current_user, session_id):
    db = get_db()
    data = request.get_json()
  
    if not data or not data.get('note'):
        return jsonify({'message': 'Session note is required'}), 400
    
 
    session_ref = db.collection('session_notes').document(session_id)
    session = session_ref.get()
    
    if not session.exists:
        return jsonify({'message': 'Session note not found'}), 404
        
    session_data = session.to_dict()
    

    if session_data.get('doctor_id') != current_user['id']:
        return jsonify({'message': 'Unauthorized access to session note'}), 403
    
  
    session_ref.update({
        'note': data.get('note'),
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    
    return jsonify({'message': 'Session note updated successfully'}), 200


@patient_bp.route('/api/session-notes/<session_id>', methods=['DELETE'])
@token_required
def delete_session_note(current_user, session_id):
    db = get_db()
    
 
    session_ref = db.collection('session_notes').document(session_id)
    session = session_ref.get()
    
    if not session.exists:
        return jsonify({'message': 'Session note not found'}), 404
        
    session_data = session.to_dict()
    
   
    if session_data.get('doctor_id') != current_user['id']:
        return jsonify({'message': 'Unauthorized access to session note'}), 403
    

    session_ref.delete()
    
    return jsonify({'message': 'Session note deleted successfully'}), 200


@patient_bp.route('/api/patients/<patient_id>/session-notes', methods=['GET'])
@token_required
def get_patient_session_notes(current_user, patient_id):
    db = get_db()
  
    patient_ref = db.collection('patients').document(patient_id).get()
    if not patient_ref.exists:
        return jsonify({'message': 'Patient not found'}), 404
        
    patient_data = patient_ref.to_dict()
    if patient_data.get('doctor_id') != current_user['id']:
        return jsonify({'message': 'Unauthorized access to patient record'}), 403
    
    session_notes_ref = db.collection('session_notes').where('patient_id', '==', patient_id).get()
    
    session_notes = []
    for doc in session_notes_ref:
        note_data = doc.to_dict()
        
        session_notes.append({
            'session_id': note_data.get('id'),
            'created_at': note_data.get('created_at')
        })
 
    session_notes.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    return jsonify({
        'session_notes': session_notes,
        'count': len(session_notes)
    }), 200


@patient_bp.route('/api/session-notes/<session_id>', methods=['GET'])
@token_required
def get_session_note(current_user, session_id):
    db = get_db()
    
    
    session_ref = db.collection('session_notes').document(session_id).get()
    
    if not session_ref.exists:
        return jsonify({'message': 'Session note not found'}), 404
        
    session_data = session_ref.to_dict()
    
    # Check if the session belongs to the current doctor
    if session_data.get('doctor_id') != current_user['id']:
        return jsonify({'message': 'Unauthorized access to session note'}), 403
    
    return jsonify(session_data), 200