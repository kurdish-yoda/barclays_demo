from flask import Blueprint, render_template, request, jsonify, session, current_app
from flask_login import current_user
import asyncio
from .api_utils import stop_api_event
from flask_cors import cross_origin
from .ai_call import AzureAIAgent
import re

agent = AzureAIAgent()
candidate_view = Blueprint('candidate_view', __name__)

def run_async(func, *args):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(func(*args))

async def async_record_conversation(user_input=None, response=None):
    if 'conversation_log' not in session:
        await agent.load_system_prompt_from_file()

    # Append user input to the conversation log if provided
    if user_input is not None:
        session['conversation_log'].append({"role": "user", "content": user_input})

    # Append response to the conversation log if provided
    if response is not None:
        session['conversation_log'].append({"role": "assistant", "content": response})

    session.modified = True


def process_job_title_from_response(response):
    """
    Extract job title from response, update Wix DB, and return modified response.
    Since Section 4 is typically the last section, we'll handle it accordingly.

    Args:
        response (str): The original AI response

    Returns:
        str: The response with job title section removed
    """
    modified_response = response
    job_title = None

    # Check if this is a response that contains section 4
    if "<!--SECTION 3!-->" in response:
        # Since Section 4 is the last section, capture everything from its marker to the end
        section4_match = re.search(r'<!--SECTION 3!-->(.*?)$', response, re.DOTALL)

        if section4_match:
            # Get the entire section content including the marker
            full_section4 = "<!--SECTION 3!-->" + section4_match.group(1)

            # Extract the job title from the section content if it exists
            title_match = re.search(r'<b>Job Title: (.*?)</b>', full_section4)

            if title_match:
                job_title = title_match.group(1).strip()

                # Simply remove the entire section 4 from the end of the response
                modified_response = response.replace(full_section4, "").rstrip()

                # Update the Wix database with the job title
                try:
                    wix_db = current_app.extensions.get('wix_db')

                    if wix_db and session.get('user_data', {}).get('item_id'):
                        # Update coach counter with job title
                        wix_db.update_job_title(
                            item_id=session['user_data']['item_id'],
                            new_job_title=job_title
                        )
                        current_app.logger.info(f"Updated Wix DB with job title: {job_title}")
                    else:
                        current_app.logger.error("WixDatabase not initialized or user_ID not found.")
                except Exception as e:
                    current_app.logger.error(f"Error updating Wix DB: {str(e)}")

    return modified_response

def update_usage_counter(response):
    """
    Updates the usage counter in the Wix database if the response contains section markers.

    Args:
        response (str): The AI response to check for section markers

    Returns:
        bool: True if counter was updated, False otherwise
    """
    # Check if the response contains any section marker (<!--SECTION x!-->)
    if re.search(r'<!--SECTION \d!-->', response):
        try:
            wix_db = current_app.extensions.get('wix_db')
            if wix_db and session.get('user_data', {}).get('item_id'):
                wix_db.update_use_count(item_id=session['user_data']['item_id'])
                current_app.logger.info(f"Updated usage counter for item ID: {session['user_data']['item_id']}")
                return True
            else:
                current_app.logger.error("WixDatabase not initialized or item_id not found in session.")
                return False
        except Exception as e:
            current_app.logger.error(f"Error updating usage counter: {str(e)}")
            return False
    else:
        current_app.logger.info("Response does not contain section markers. Usage counter not updated.")
        return False

@candidate_view.route('/interface', methods=['GET', 'POST'])
@cross_origin(supports_credentials=True)
def interface():

    if request.method == 'GET':
        return render_template('interface.html', user=current_user)

    async def async_interface():
        try:
            message = request.form.get('chat')

            if not message:
                return jsonify({"error": "Missing chat message"}), 400
            elif message == "<-START->" or message == "&lt;-START-&gt":
                pass
            elif isinstance(session.get('conversation_log'), list) and len(session['conversation_log']) > 1:
                await async_record_conversation(user_input=message)

            response = agent.send_to_azure_agent()
            current_app.logger.info(f"Received response from Azure Agent: {response}")
            # Process the response to extract job title, update DB, and modify response
            modified_response = process_job_title_from_response(response)

            # Update the usage counter only if the response contains section markers
            update_usage_counter(response)

            await async_record_conversation(response=modified_response)

            return jsonify({"response": modified_response})

        except Exception as e:
            current_app.logger.error(f"Error in interviewer route: {e}")
            return jsonify({"error": "Failed to process request"}), 500

    return run_async(async_interface)

@candidate_view.route('/get_coach_interactions', methods=['GET'])
def get_coach_interactions():
    return jsonify({
        "coachInteractions": session['user_data']['coachInteractions'],
        "coachCounter": session['user_data']['coachCounter']
    })

@candidate_view.route('/cleanup_session', methods=['POST'])
def cleanup_session():
    try:
        # Get the wix database connection
        wix_db = current_app.extensions.get('wix_db')
        if not wix_db:
            current_app.logger.error("WixDatabase not initialized in cleanup.")
            return jsonify({"message": "Database connection error", "success": False}), 500

        # Save metrics if they exist in session
        '''
        if 'user_metrics' in session and 'user_ID' in session['user_metrics']:
            try:
                current_app.logger.info(f"Saving metrics during cleanup: {session['user_metrics']}")
                #result = wix_db.update_user_metrics(session['user_metrics'])
                #current_app.logger.info(f"Metrics update result: {result}")
            except Exception as e:
                current_app.logger.error(f"Error updating metrics during cleanup: {str(e)}")
        else:
            current_app.logger.warning("No user metrics found in session during cleanup")
        '''
        # Stop any ongoing API calls
        stop_api_event()

        # Clear session
        if 'conversation_log' in session:
            session.clear()
            session.modified = True

        return jsonify({"message": "API call was stopped, metrics saved, and session cleared.", "success": True})

    except Exception as e:
        current_app.logger.error(f"Error in cleanup_session: {str(e)}")
        return jsonify({"message": f"Error during cleanup: {str(e)}", "success": False}), 500

@candidate_view.route('/user_agreement', methods=['GET', 'POST'])
def user_agreement():
    return render_template('user-agreement.html')

@candidate_view.route('/error')
def error_page():
    return render_template('error.html', error_message="Authentication required. Please log in.")


@candidate_view.route('/record_usage', methods=['POST'])
def record_usage():
    if not request.is_json:
        current_app.logger.error("Request content type is not JSON")
        return jsonify({'error': 'Content type must be application/json'}), 415

    recording_seconds = request.json.get('recording_seconds')

    if recording_seconds is None or not isinstance(recording_seconds, (int, float)):
        current_app.logger.error(f"Invalid recording_seconds: {recording_seconds}")
        return jsonify({'error': 'Invalid recording_seconds value'}), 400

    try:
        # Add the recording duration to the total
        session['user_metrics']['recordingsCoach'] += recording_seconds
        session.modified = True
        return jsonify({
            'success': True,
            'recorded_seconds': recording_seconds,
            'total_seconds': session['user_metrics']['recordingsCoach']
        })

    except Exception as e:
        current_app.logger.error(f"Error recording usage: {str(e)}")
        return jsonify({'error': str(e)}), 500
