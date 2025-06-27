from openai import AzureOpenAI
from .secrets import get_secret
import re
import threading
from flask import current_app, session
import uuid
from functools import partial
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import time
from .api_utils import is_stop_event_set

interviewer_id = get_secret('INTERVIEWER-US')
assistant_id = get_secret('ASSISTANT-US')
analyzer_id = get_secret('ANALYZER-US')

AzureClient = AzureOpenAI(   
    api_key=get_secret('KEY1-AI-US'),  
    api_version="2024-02-15-preview",
    azure_endpoint = get_secret('AI-ENDPOINT-US')
)

def initialize_thread():
    # Create a thread and return its ID
    thread = AzureClient.beta.threads.create()
    return thread.id

def delete_thread(thread_id):
    if not thread_id or thread_id == "Not set":
        print("thread not set")
        return
    try:
        response = AzureClient.beta.threads.delete(thread_id)
        return response
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def extract_segments(text):

    # Regular expression to find the variable enclosed within single #
    match = re.search(r'#(.*?)#', text)
    
    # If the variable exists, extract it and split the text
    if match:
        variable = match.group(1)

        before_text, after_text = text.split(f'#{variable}#', 1)

    else:
        # If no variable is found, set default values

        variable = "table"
        before_text, after_text = text, ''

    return variable, before_text, after_text

def interviewer_response(thread_id, question, assistant_instructions=None):
    try:
        message = AzureClient.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=question
        )
        interviewer_id = get_secret('INTERVIEWER-US')
        run_args = {
            "thread_id": thread_id,
            "assistant_id": interviewer_id
        }
        if assistant_instructions:
            run_args["instructions"] = assistant_instructions

        run = AzureClient.beta.threads.runs.create(**run_args)
        run_id = run.id

        start_time = time.time()
        while time.time() - start_time < 60:  # 60-second timeout for run completion
            if is_stop_event_set():
                try:
                    current_run = AzureClient.beta.threads.runs.retrieve(
                        thread_id=thread_id,
                        run_id=run_id
                    )
                    if current_run.status != "completed":
                        AzureClient.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id)
                except Exception as e:
                    # If we can't cancel, it's likely already completed or cancelled
                    pass
                return None, None, None
            
            current_run = AzureClient.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )
            if current_run.status == "completed":
                thread_messages = AzureClient.beta.threads.messages.list(thread_id)
                for message in thread_messages.data:
                    if message.role == "assistant":
                        video_variable, response_text, question_text = extract_segments(message.content[0].text.value)
                        return response_text, question_text, video_variable
            elif current_run.status in ["failed", "cancelled"]:
                return None, None, None

            time.sleep(1)  # Add a small delay to prevent excessive API calls

        return None, None, None

    except Exception:
        return None, None, None

def assistant_response(thread_id, question, assistant_instructions=None):
    try:
        message = AzureClient.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=question
        )

        run_args = {
            "thread_id": thread_id,
            "assistant_id": assistant_id
        }
        if assistant_instructions:
            run_args["instructions"] = assistant_instructions

        run = AzureClient.beta.threads.runs.create(**run_args)
        run_id = run.id

        start_time = time.time()
        while time.time() - start_time < 60:  # 60-second timeout for run completion
            if is_stop_event_set():
                try:
                    current_run = AzureClient.beta.threads.runs.retrieve(
                        thread_id=thread_id,
                        run_id=run_id
                    )
                    if current_run.status != "completed":
                        AzureClient.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id)
                except Exception as e:
                    # If we can't cancel, it's likely already completed or cancelled
                    pass
                return None, None, None

            current_run = AzureClient.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )
            if current_run.status == "completed":
                thread_messages = AzureClient.beta.threads.messages.list(thread_id)
                for message in thread_messages.data:
                    if message.role == "assistant":
                        video_variable, response_text, question_text = extract_segments(message.content[0].text.value)
                        return response_text, question_text, video_variable
            elif current_run.status in ["failed", "cancelled"]:
                return None, None, None

            time.sleep(1)  # Add a small delay to prevent excessive API calls

        return None, None, None

    except Exception:
        return None, None, None    

def analyze_candidate(thread_id, transcript):
    max_retries = 3
    retry_count = 0

    # Get the current application object
    app = current_app._get_current_object()
    # Create a local stop event for this specific call
    local_stop_event = threading.Event()

    def _execute_analysis(app, local_stop_event, transcript):
        with app.app_context():
            try:
                transcript = str(transcript)
                message = AzureClient.beta.threads.messages.create(
                    thread_id=thread_id,
                    role="user",
                    content=transcript
                )

                run_args = {
                    "thread_id": thread_id,
                    "assistant_id": analyzer_id
                }
   
                run = AzureClient.beta.threads.runs.create(**run_args) 
                current_app.logger.debug(f"Run created for thread {thread_id}")

                while True:
                    if local_stop_event.is_set():
                        return {'result': None, 'error': "Analysis stopped due to timeout"}

                    current_run = AzureClient.beta.threads.runs.retrieve(
                        thread_id=thread_id,
                        run_id=run.id
                    )

                    if current_run.status == "completed":
                        break
                    elif current_run.status in ["failed", "cancelled"]:
                        error_msg = f"Run ended with status: {current_run.status} for thread {thread_id}"
                        current_app.logger.error(error_msg)
                        return {'result': None, 'error': error_msg}
                    
                    time.sleep(1)  # Add a small delay to prevent excessive API calls

                thread_messages = AzureClient.beta.threads.messages.list(thread_id)

                output = ""  # Initialize output as an empty string
                for message in thread_messages.data:
                    if message.role == "assistant":
                        content = message.content[0].text.value
                        output += content + "\n"

                return {'result': output, 'error': None}
            
            except Exception as e:
                error_msg = f"An error occurred for thread {thread_id}: {e}"
                current_app.logger.error(error_msg)
                return {'result': None, 'error': error_msg}

    while retry_count < max_retries:
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_execute_analysis, app, local_stop_event, transcript)
                return future.result(timeout=20)  # 20-second timeout
        except TimeoutError:
            retry_count += 1
            current_app.logger.warning(f"Analysis timed out for thread {thread_id}. Retrying... (Attempt {retry_count}/{max_retries})")
        except Exception as e:
            error_msg = f"An unexpected error occurred for thread {thread_id}: {e}"
            current_app.logger.error(error_msg)
            return {'result': None, 'error': error_msg}

    error_msg = f"Max retries reached. Analysis failed for thread {thread_id}."
    current_app.logger.error(error_msg)
    return {'result': None, 'error': error_msg}