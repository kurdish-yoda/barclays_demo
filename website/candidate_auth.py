from flask import Blueprint, jsonify, current_app, redirect, url_for, session, request
from flask_login import login_user
from flask_cors import cross_origin
from .models import User
from .cv_utils import get_cv_text
from .ai_parsing import process_cv_with_ai
import json

def parse_pdf(id):
    # Get the CV text
    extracted_data = get_cv_text(id)

    # Check if extraction was successful
    if not extracted_data:
        current_app.logger.error(f"Failed to extract CV text for user ID: {id}")
        return {"error": "Failed to extract CV text"}

    # Process the extracted text with AI
    parsed_cv = process_cv_with_ai(extracted_data['text'])

    # Save the parsed CV to a temporary file (for debugging)
    with open('temp_extraction.txt', 'w', encoding='utf-8') as f:
        json.dump(parsed_cv, f, indent=2)

    return parsed_cv

def load_prompt_template():
    with open('website/static/assets/prompt.txt', 'r', encoding='utf-8') as f:
        return f.read()

candidate_auth = Blueprint('candidate_auth', __name__)

@candidate_auth.route('/autoLogin', methods=['GET'])
@cross_origin(supports_credentials=True)
def autoLogin():
    try:

        # ----------------------------------------
        # Get the encoded ID from the request and decode it
        # ----------------------------------------
        item_id = request.args.get('_id')
        if not item_id:
            current_app.logger.error("No item_id provided in autoLogin.")
            return jsonify({"msg": "item_id is required"}), 400

        session.clear()
        session.modified = True

        # ----------------------------------------
        # Initialize user using WixDatabase
        # ----------------------------------------
        wix_db = current_app.extensions.get('wix_db')
        if not wix_db:
            current_app.logger.error("WixDatabase not initialized.")
            return jsonify({"msg": "Internal server error"}), 500

        current_app.logger.info(f"Getting user with item_id: {item_id}")
        user = wix_db.get_user(item_id)
        if not user:
            current_app.logger.error(f"User not found with item_id: {item_id}")
            return jsonify({"msg": "User not found"}), 404

        # Create User instance
        user_instance = User(item_id=user.item_id)

        # This now puts all relevant information into the session
        login_user(user_instance, remember=True)

        # ----------------------------------------
        # Store user data in session - adjust fields based on new schema
        # ----------------------------------------
        session['user_data'] = {
            'item_id': user.item_id,
            'user_id': user.user_id,
            'cv_path': user.cv_path,
            'uses': user.uses,
            'job_titles': user.job_titles,
            # Include any other fields from the new schema
        }

        # ----------------------------------------
        # Initialize metrics
        # ----------------------------------------
        '''
        session['user_metrics'] = {
            'user_id': user.user_id,
            'inputTokensInterviewer': 0,
            'outputTokensInterviewer': 0,
            'outputCharacterInterviewer': 0,
            'playStopPressesInterviewer': 0,
            'recordingsInterviewer': 0,
            'interviewerQuestionsAsked': 0,
            'inputTokensCoach': 0,
            'outputTokensCoach': 0,
            'outputCharacterCoach': 0,
            'playStopPressesCoach': 0,
            'recordingsCoach': 0,
            'coachQuestionsAsked': 0
        }
        '''

        # ----------------------------------------
        # Get prompt template and create prompt
        # ----------------------------------------
        try:
            prompt_template = wix_db.get_prompt("Barclays")
        except Exception as e:
            current_app.logger.error(f"Error loading prompt template, using default on local storage: {str(e)}")
            prompt_template = load_prompt_template()

        prompt = prompt_template

        # ----------------------------------------
        # Setup avatar and voice
        # ----------------------------------------

        session['avatar'] = "avatar_4"
        session['voice'] = "en-GB-OliverNeural"

        # ----------------------------------------
        # Store prompt and initialize counters
        # ----------------------------------------
        session['prompt'] = prompt
        session['total_questions'] = 0

        # ----------------------------------------
        # Redirect to candidate's start page
        # ----------------------------------------
        redirect_url = url_for('candidate_view.interface', _external=True, _scheme='https')
        return redirect(redirect_url)

    except Exception as e:
        current_app.logger.error(f"Exception in autoLogin: {str(e)}")
        return jsonify({"msg": "Internal server error"}), 500


def decode_id(encoded_id):
    """Decodes the input ID using custom character substitution."""
    characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    decoded = ''.join(characters[(characters.index(c) - 13) % 64] if c in characters else c for c in encoded_id)
    return decoded

def get_avatar(interviewType, run, avatar_data):
    """Fetch avatars from the provided avatar_data and return the avatar matching the interviewType and run.
    If no match is found, return the default 'avatar_1'."""
    try:
        for entry in avatar_data:
            if entry['interviewType'] == interviewType and entry['run'] == run:
                return entry['avatar']
    except Exception as e:
        current_app.logger.error(f"Error fetching avatar from data: {e}")

    # Fallback to default avatar if no match is found
    return "avatar_1"

def get_voice(interviewType, run, avatar_data):
    """Fetch voice from the provided avatar_data and return the voice matching the interviewType and run.
    If no match is found, return the default 'en-US-AvaMultilingualNeural'."""
    try:
        for entry in avatar_data:
            if entry['interviewType'] == interviewType and entry['run'] == run:
                return entry['voice']
    except Exception as e:
        current_app.logger.error(f"Error fetching voice from data: {e}")

    return "en-US-AvaMultilingualNeural"

def get_speechSynthesisVoiceRate(interviewType, run, avatar_data):
    """Fetch speechSynthesisVoiceRate from the provided avatar_data and return the speechSynthesisVoiceRate
    matching the interviewType and run. If no match is found, return the default '0' (normal speed).
    """
    try:
        for entry in avatar_data:
            if entry['interviewType'] == interviewType and entry['run'] == run:
                return entry['speechSynthesisVoiceRate']
        current_app.logger.info(f"No speech rate match found for interviewType: {interviewType}, run: {run}. Using default value: 0")
        return 0  # Default to normal speed if no match found
    except Exception as e:
        current_app.logger.error(f"Error fetching speechSynthesisVoiceRate from data: {e}")
        return 0  # Return default value in case of any error

@candidate_auth.route('/get_session_data')
def get_session_data():
    # Safely remove 'conversation_log' from session if it exists
    session.pop('conversation_log', None)
    return jsonify(session.get('user_data', {}))

@candidate_auth.route('/get_avatar')
def get_session_avatar():
    return jsonify({"avatar": session.get('avatar', None)})
