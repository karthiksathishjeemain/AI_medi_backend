from flask import Blueprint, request, jsonify
import datetime
from functools import wraps

chat_bp = Blueprint('chat', __name__)

# Re-implement the token_required decorator to be used in this blueprint
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        from app import token_required as app_token_required
        return app_token_required(f)(*args, **kwargs)
    return decorated

# Helper function to format timestamps
def format_timestamp(timestamp):
    if isinstance(timestamp, datetime.datetime):
        return timestamp.isoformat()
    return timestamp

@chat_bp.route('/api/chat/sessions', methods=['POST'])
@token_required
def create_session(current_user):
    """
    Create a new chat session
    """
    data = request.get_json()
    title = data.get('title', 'New Conversation')
    
    from app import get_db
    db = get_db()
    
    # Create a new session
    new_session = {
        'user_id': current_user['id'],
        'created_at': datetime.datetime.now(),
        'updated_at': datetime.datetime.now(),
        'title': title
    }
    
    # Add session to Firestore
    session_ref = db.collection('chat_sessions').add(new_session)
    session_id = session_ref[1].id
    
    return jsonify({
        'session_id': session_id,
        'title': title,
        'created_at': format_timestamp(new_session['created_at']),
        'updated_at': format_timestamp(new_session['updated_at'])
    }), 201

@chat_bp.route('/api/chat/sessions', methods=['GET'])
@token_required
def get_chat_sessions(current_user):
    """
    Get all chat sessions for the current user
    """
    from app import get_db
    db = get_db()
    
    # Get all sessions for the current user, ordered by most recent first
    sessions_ref = db.collection('chat_sessions').where('user_id', '==', current_user['id']).order_by('updated_at', direction='DESCENDING').get()
    
    sessions = []
    for session in sessions_ref:
        session_data = session.to_dict()
        sessions.append({
            'id': session.id,
            'title': session_data.get('title', 'New Conversation'),
            'created_at': format_timestamp(session_data.get('created_at')),
            'updated_at': format_timestamp(session_data.get('updated_at'))
        })
    
    return jsonify(sessions), 200

@chat_bp.route('/api/chat/sessions/<session_id>', methods=['GET'])
@token_required
def get_chat_session(current_user, session_id):
    """
    Get a specific chat session and its messages
    """
    from app import get_db
    db = get_db()
    
    # Check if session exists and belongs to current user
    session_ref = db.collection('chat_sessions').document(session_id).get()
    if not session_ref.exists:
        return jsonify({'message': 'Chat session not found'}), 404
        
    session_data = session_ref.to_dict()
    if session_data.get('user_id') != current_user['id']:
        return jsonify({'message': 'Unauthorized access to chat session'}), 403
    
    # Get messages for this session
    messages_ref = db.collection('chat_sessions').document(session_id).collection('messages').order_by('timestamp').get()
    
    messages = []
    for message in messages_ref:
        message_data = message.to_dict()
        messages.append({
            'id': message.id,
            'sender': message_data.get('sender'),
            'content': message_data.get('content'),
            'timestamp': format_timestamp(message_data.get('timestamp'))
        })
    
    # Create the complete session data
    complete_session = {
        'id': session_id,
        'title': session_data.get('title', 'New Conversation'),
        'created_at': format_timestamp(session_data.get('created_at')),
        'updated_at': format_timestamp(session_data.get('updated_at')),
        'messages': messages
    }
    
    return jsonify(complete_session), 200

@chat_bp.route('/api/chat/sessions/<session_id>/messages', methods=['POST'])
@token_required
def save_message(current_user, session_id):
    """
    Save a message to an existing chat session
    """
    data = request.get_json()
    
    if not data or not data.get('content') or not data.get('sender'):
        return jsonify({'message': 'Message content and sender are required'}), 400
        
    from app import get_db
    db = get_db()
    
    # Check if session exists and belongs to current user
    session_ref = db.collection('chat_sessions').document(session_id).get()
    if not session_ref.exists:
        return jsonify({'message': 'Chat session not found'}), 404
        
    session_data = session_ref.to_dict()
    if session_data.get('user_id') != current_user['id']:
        return jsonify({'message': 'Unauthorized access to chat session'}), 403
    
    # Create message object
    message_data = {
        'sender': data.get('sender'),  # 'user' or 'assistant'
        'content': data.get('content'),
        'timestamp': datetime.datetime.now()
    }
    
    # Save the message
    message_ref = db.collection('chat_sessions').document(session_id).collection('messages').add(message_data)
    message_id = message_ref[1].id
    
    # Update session timestamp
    db.collection('chat_sessions').document(session_id).update({
        'updated_at': datetime.datetime.now()
    })
    
    return jsonify({
        'id': message_id,
        'sender': message_data['sender'],
        'content': message_data['content'],
        'timestamp': format_timestamp(message_data['timestamp'])
    }), 201

# @chat_bp.route('/api/chat/sessions/<session_id>', methods=['DELETE'])
# @token_required
# def delete_chat_session(current_user, session_id):
#     """
#     Delete a chat session and all its messages
#     """
#     from app import get_db
#     db = get_db()
    
#     # Check if session exists and belongs to current user
#     session_ref = db.collection('chat_sessions').document(session_id).get()
#     if not session_ref.exists:
#         return jsonify({'message': 'Chat session not found'}), 404
        
#     session_data = session_ref.to_dict()
#     if session_data.get('user_id') != current_user['id']:
#         return jsonify({'message': 'Unauthorized access to chat session'}), 403
    
#     # Delete all messages in the session
#     messages_ref = db.collection('chat_sessions').document(session_id).collection('messages').get()
#     for message in messages_ref:
#         message.reference.delete()
    
#     # Delete the session
#     db.collection('chat_sessions').document(session_id).delete()
    
#     return jsonify({'message': 'Chat session deleted successfully'}), 200

@chat_bp.route('/api/chat/sessions/<session_id>', methods=['PUT'])
@token_required
def update_session_title(current_user, session_id):
    """
    Update the title of a chat session
    """
    data = request.get_json()
    if not data or not data.get('title'):
        return jsonify({'message': 'Title is required'}), 400
    
    new_title = data.get('title')
    
    from app import get_db
    db = get_db()
    
    # Check if session exists and belongs to current user
    session_ref = db.collection('chat_sessions').document(session_id).get()
    if not session_ref.exists:
        return jsonify({'message': 'Chat session not found'}), 404
        
    session_data = session_ref.to_dict()
    if session_data.get('user_id') != current_user['id']:
        return jsonify({'message': 'Unauthorized access to chat session'}), 403
    
    # Update the title
    db.collection('chat_sessions').document(session_id).update({
        'title': new_title,
        'updated_at': datetime.datetime.now()
    })
    
    return jsonify({'message': 'Session title updated successfully'}), 200
# @chat_bp.route('/api/chat/sessions/batch-delete', methods=['POST'])
# @token_required
# def batch_delete_chat_sessions(current_user):
#     """
#     Delete multiple chat sessions and all their messages
#     """
#     data = request.get_json()
    
#     if not data or not data.get('session_ids') or not isinstance(data.get('session_ids'), list):
#         return jsonify({'message': 'A list of session_ids is required'}), 400
    
#     session_ids = data.get('session_ids')
#     from app import get_db
#     db = get_db()
    
#     results = {
#         'successful': [],
#         'failed': []
#     }
    
#     for session_id in session_ids:
#         try:
#             # Check if session exists and belongs to current user
#             session_ref = db.collection('chat_sessions').document(session_id).get()
#             if not session_ref.exists:
#                 results['failed'].append({
#                     'id': session_id,
#                     'reason': 'Chat session not found'
#                 })
#                 continue
                
#             session_data = session_ref.to_dict()
#             if session_data.get('user_id') != current_user['id']:
#                 results['failed'].append({
#                     'id': session_id,
#                     'reason': 'Unauthorized access to chat session'
#                 })
#                 continue
            
#             # Delete all messages in the session
#             messages_ref = db.collection('chat_sessions').document(session_id).collection('messages').get()
#             for message in messages_ref:
#                 message.reference.delete()
            
#             # Delete the session
#             db.collection('chat_sessions').document(session_id).delete()
            
#             results['successful'].append(session_id)
            
#         except Exception as e:
#             results['failed'].append({
#                 'id': session_id,
#                 'reason': str(e)
#             })
    
#     return jsonify({
#         'message': f"Successfully deleted {len(results['successful'])} sessions, {len(results['failed'])} failed",
#         'results': results
#     }), 200