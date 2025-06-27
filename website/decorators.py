from functools import wraps
from flask import jsonify, current_app, session
from flask_login import current_user
from flask_cors import cross_origin

def candidate_login_required(f):
    @wraps(f)
    @cross_origin(supports_credentials=True)
    def decorated_view(*args, **kwargs):
        
        if not current_user.is_authenticated:
            current_app.logger.warning("User not authenticated")
            return jsonify({"error": "Authentication required"}), 401

        return f(*args, **kwargs)
    return decorated_view
