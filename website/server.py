from flask import Blueprint, jsonify, session, current_app, Response
from flask_login import current_user
from flask_cors import cross_origin

server = Blueprint('server', __name__)

@server.route('/test-redis')
def test_redis():
    try:
        redis_client = current_app.config['SESSION_REDIS']
        redis_client.set('test_key', 'It works!')
        result = redis_client.get('test_key')
        if isinstance(result, bytes):
            result = result.decode('utf-8')
        return f"Redis is working: {result}"
    except Exception as e:
        return f"Redis test failed: {str(e)}"

@server.route('/test-cors', methods=['GET', 'POST'])
@cross_origin(supports_credentials=True)
def test_cors():
    return jsonify({"message": "CORS is working"}), 200

'''
@server.route('/transcripts/<string:job_code>')
def get_all_candidate_transcripts(job_code):
    candidates = Candidate.query.filter_by(job_code=job_code).all()

    if not candidates:
        return jsonify({"error": f"No candidates found for job code {job_code}"}), 404

    all_candidate_data = []
    for candidate in candidates:
        formatted_transcripts = []
        for transcript in candidate.get_transcripts():
            formatted_transcript = {
                'timestamp': transcript['timestamp'],
                'conversations': transcript['data']
            }
            formatted_transcripts.append(formatted_transcript)

        candidate_data = {
            'candidate_info': {
                'job_code': candidate.job_code,
                'candidate_number': candidate.candidate_number,
                'first_name': candidate.first_name,
                'interview_flow': candidate.get_interview_flow(),
                'is_disabled': candidate.is_disabled
            },
            'transcripts': formatted_transcripts
        }
        all_candidate_data.append(candidate_data)

    context = {
        'job_code': job_code,
        'candidates': all_candidate_data
    }

    if request.args.get('format') == 'json':
        return current_app.response_class(
            response=json.dumps(context, indent=2, sort_keys=True),
            status=200,
            mimetype='application/json'
        )

    return render_template('transcripts.html', **context)
'''
@server.route('/requests')
def requests():
    file_path = 'website/logs/request_log.txt'

    try:
        with open(file_path, 'r') as file:
            content = file.read()

        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Text File Contents</title>
            <style>
                body {{
                    background-color: black;
                    color: white;
                    font-family: monospace;
                    white-space: pre-wrap;
                }}
            </style>
        </head>
        <body>
        {content}
        </body>
        </html>
        """

        return Response(html_content, mimetype='text/html')

    except FileNotFoundError:
        return "Error: The specified file was not found.", 404
    except Exception as e:
        return f"An error occurred: {str(e)}", 500


@server.route('/get_overlay_data', methods=['GET'])
def get_overlay_data():
    if not current_user.is_authenticated:
        return jsonify({
            'error': 'User not logged in'
        }), 401

    # Read the overlay.txt file
    try:
        with open('website/static/assets/overlay.txt', 'r') as file:
            lines = file.readlines()
            version_number = lines[0].strip()
            environment = lines[1].strip()
            beta_version = lines[2].strip() if len(lines) > 2 else ''
    except FileNotFoundError:
        current_app.logger.error("overlay.txt file not found")
        version_number = 'Unknown'
        environment = 'Unknown'
        beta_version = ''

    # Combine version info and user_id
    overlay_data = {
        'version_number': version_number,
        'environment': environment,
        'beta_version': beta_version
    }

    # Return the data as JSON
    return jsonify(overlay_data)
