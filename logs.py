from flask import Blueprint, request, jsonify
from functools import wraps
import datetime
from flask import current_app
import jwt
from firebase_admin import firestore

# Create a blueprint for logs-related routes
logs_bp = Blueprint('logs', __name__)

def get_db():
    from firebase_admin import firestore
    return firestore.client()

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
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user_id = data['user_id']
           
            db = get_db()
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

@logs_bp.route('/api/logs', methods=['POST'])
@token_required
def create_audit_log(current_user):
    """
    API to create an audit log entry in the database
    
    Expected JSON payload:
    {
        "action_type": "login",  # Type of action (login, logout, patient_view, etc.)
        "location": "New York",  # Optional
        "device": "iPhone 13"    # Optional
    }
    """
    data = request.get_json()
    
    if not data or not data.get('action_type'):
        return jsonify({'message': 'Missing required fields'}), 400
    
    db = get_db()
    
    log_entry = {
        'user_id': current_user['id'],
        'user_email': current_user['email'],
        'timestamp': datetime.datetime.now(),
        'action_type': data.get('action_type'),
        'location': data.get('location', ''),
        'device': data.get('device', ''),
        'details': data.get('details', {})
    }
    
    # Add log to database
    log_ref = db.collection('audit_logs').add(log_entry)
    
    return jsonify({
        'message': 'Audit log created successfully',
        'log_id': log_ref[1].id
    }), 201

@logs_bp.route('/api/logs', methods=['GET'])
@token_required
def get_audit_logs(current_user):
    """
    API to retrieve audit logs for a user
    
    Query parameters:
    - start_date: Optional start date for filtering (ISO format)
    - end_date: Optional end date for filtering (ISO format)
    - action_type: Optional action type for filtering
    - limit: Optional limit on number of results (default: 100)
    
    Note: This API requires a composite index in Firestore. If you get an error, follow the URL
    in the error message to create the necessary index.
    """
    db = get_db()
    
    # Start with basic query filtered by user_id
    query = db.collection('audit_logs').where('user_id', '==', current_user['id'])
    
    # Order by timestamp (descending) first - this is important for Firestore composite indexes
    query = query.order_by('timestamp', direction=firestore.Query.DESCENDING)
    
    # Apply action_type filter if provided
    action_type = request.args.get('action_type')
    if action_type:
        query = query.where('action_type', '==', action_type)
    
    # Apply date filters if provided
    # Note: We need to be careful with the order of operations for Firestore queries
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        try:
            start_datetime = datetime.datetime.fromisoformat(start_date)
            # For descending order, the "start" date becomes the "<=" condition
            query = query.where('timestamp', '>=', start_datetime)
        except ValueError:
            return jsonify({'message': 'Invalid start_date format'}), 400
    
    if end_date:
        try:
            end_datetime = datetime.datetime.fromisoformat(end_date)
            # For descending order, the "end" date becomes the ">=" condition
            query = query.where('timestamp', '<=', end_datetime)
        except ValueError:
            return jsonify({'message': 'Invalid end_date format'}), 400
    
    # Apply limit
    try:
        limit = int(request.args.get('limit', 100))
        query = query.limit(limit)
    except ValueError:
        return jsonify({'message': 'Invalid limit parameter'}), 400
    
    # Execute query
    results = query.get()
    
    # Format results
    logs = []
    for doc in results:
        log_data = doc.to_dict()
        log_data['id'] = doc.id
        
        # Convert timestamp to ISO format string for JSON serialization
        if 'timestamp' in log_data and log_data['timestamp']:
            log_data['timestamp'] = log_data['timestamp'].isoformat()
            
        logs.append(log_data)
    
    return jsonify({
        'logs': logs,
        'count': len(logs)
    }), 200

# To register this blueprint in your main app, add the following code to your app.py:
# from logs import logs_bp
# app.register_blueprint(logs_bp)