import requests
import json
import os
from .models import User  # Add this import if it's not already there
from flask import current_app, session

class WixDatabase:
    def __init__(self, api_key, site_id):
        self.api_key = api_key
        self.site_id = site_id
        self.interview_collection_id = 'RunningInterviews'
        self.candidateData_collection_id = 'CandidateData'
        # the coach pulls straight from the "Agents" collection
        self.template_collection_id = 'Interviews'
        self.avatar_selector_id = 'avatar_selector'
        self.base_url = "https://www.wixapis.com/wix-data/v2"

    def init_app(self, app):
        app.extensions['wix_db'] = self

        # If api_key and site_id weren't provided in the constructor,
        # try to get them from the app config
        if not self.api_key:
            self.api_key = app.config.get('WIX_API_KEY')
        if not self.site_id:
            self.site_id = app.config.get('WIX_SITE_ID')

    def _make_request(self, method, endpoint, data=None):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': self.api_key,
            'wix-site-id': self.site_id
        }
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.request(method, url, headers=headers, json=data)

            # Attempt to parse JSON response
            try:
                response_json = response.json()
            except json.JSONDecodeError:
                print("Failed to decode response as JSON.")
                response_json = None

            # Raise an exception for bad status codes
            response.raise_for_status()
            return response_json
        except requests.exceptions.RequestException as e:
            print(f"Error making request: {e}")
            return None

    # ----------------------------------------
    # Basic CRUD Operations


    def get_entry(self, item_id):
        """
        Retrieves the entire item data from the RunningInterviews collection.
        """
        endpoint = "items/query"
        data = {
            "dataCollectionId": self.candidateData_collection_id,
            "query": {
                "filter": {
                    "_id": item_id  # Ensure '_id' is the correct field name for item ID
                },
                "limit": 1
            }
        }
        try:
            current_app.logger.info(f"Fetching item with ID: {item_id} from collection: {self.candidateData_collection_id}")
            result = self._make_request("POST", endpoint, data)
            if result and 'dataItems' in result and len(result['dataItems']) > 0:
                return result['dataItems'][0].get('data', {})
            else:
                print(f"Item with ID {item_id} not found.")
                return None
        except Exception as e:
            print(f"Error fetching item: {str(e)}")
            return None

    def get_item(self, item_id, field_name):
        """
        Retrieves a specific field value for an item from the RunningInterviews collection.
        """
        endpoint = "items/query"
        data = {
            "dataCollectionId": self.interview_collection_id,
            "query": {
                "filter": {
                    "_id": item_id  # Assuming '_id' is the correct field for item ID
                },
                "fields": [field_name],
                "limit": 1
            }
        }
        try:
            print(f"Fetching field '{field_name}' for item ID: {item_id} from collection: {self.interview_collection_id}")
            result = self._make_request("POST", endpoint, data)
            if result and 'dataItems' in result and len(result['dataItems']) > 0:
                data_item = result['dataItems'][0].get('data', {})
                field_value = data_item.get(field_name)
                print(f"Retrieved '{field_name}': {field_value}")
                return field_value
            else:
                print(f"Failed to retrieve field '{field_name}'. Response: {result}")
                return None
        except Exception as e:
            print(f"Error getting field: {str(e)}")
            return None

    def update_item(self, item_id, field_name, new_value):
        """
        Updates a specific field value for an item within the RunningInterviews collection without affecting other fields.
        """
        # Step 1: Fetch the existing item data
        existing_data = self.get_entry(item_id)
        if not existing_data:
            return f"Item with ID {item_id} not found. Cannot update field '{field_name}'."

        # Step 2: Modify the desired field
        existing_data[field_name] = new_value

        # Step 3: Send the complete data back to update the item
        endpoint = f"items/{item_id}"
        data = {
            "dataCollectionId": self.candidateData_collection_id,
            "dataItem": {
                "data": existing_data
            }
        }
        try:
            result = self._make_request("PUT", endpoint, data)
            if result and 'dataItem' in result:
                return f"Field '{field_name}' updated successfully for item ID: {item_id}"
            else:
                return f"Failed to update field '{field_name}'. Response: {result}"
        except Exception as e:
            return f"Error updating field '{field_name}': {str(e)}"

    def remove_item(self, item_id, field_name):
        """
        Sets a specific field's value to None for an item within the RunningInterviews collection.

        :param item_id: The ID of the item to update.
        :param field_name: The name of the field to set to None.
        :return: Success or error message.
        """
        return self.update_item(item_id, field_name, None)

    # ----------------------------------------
    # User Management
    # ----------------------------------------
    def get_user(self, item_id):
        """
        Fetches user data based on item_id from the CandidateData collection and returns a User instance.
        """
        endpoint = "items/query"
        data = {
            "dataCollectionId": "CandidateData",  # New collection name
            "query": {
                "filter": {
                    "_id": item_id
                },
                "limit": 1
            }
        }

        try:
            result = self._make_request("POST", endpoint, data)

            if result and 'dataItems' in result and len(result['dataItems']) > 0:
                user_data = result['dataItems'][0].get('data', {})

                return User(
                    item_id=item_id,
                    user_id=user_data.get('userId'),
                    cv_path=user_data.get('cv'),  # This now contains the document from CMS
                    uses=user_data.get('uses'),
                    job_titles=user_data.get('jobTitles')
                )
            else:
                current_app.logger.error(f"User not found with item_id: {item_id}")
                return None

        except Exception as e:
            current_app.logger.error(f"Error fetching user: {str(e)}")
            return None

    def update_user(self, item_id, **fields_to_update):
        """
        Updates specified fields for a user within the RunningInterviews collection.

        If no fields are provided, updates using the user data stored in the session.

        :param item_id: The ID of the item to update.
        :param fields_to_update: A dictionary of fields to update with their new values (optional).
        :return: Success or error message.
        """

        user_data = session['user_data']
        # Update user data if there are fields to update
        if fields_to_update:
            user_data.update(fields_to_update)

            # Ensure the session is updated if the data originally came from the session
            if session.get('user_data') and session['user_data'].get('item_id') == item_id:
                session['user_data'] = user_data

        else:
            current_app.logger.info(f"No fields to update. Using just session data.")
            user_data = session.get('user_data')
            if not user_data or user_data.get('item_id') != item_id:
                return "User data not found in session or item_id mismatch."

        session.modified = True

        # Use a temporary dictionary to modify the data, because the _id field is read-only it will not do anything, but thats ok.
        user_data_swap = user_data.copy()
        user_data_swap['_id'] = user_data_swap.pop('item_id', item_id)

        # Prepare the data for updating in the database
        endpoint = f"items/{item_id}"
        data = {
            "dataCollectionId": self.interview_collection_id,
            "dataItem": {
                "data": user_data_swap
            }
        }

        try:
            # Send a single request to update the item in the database
            result = self._make_request("PUT", endpoint, data)
            if result and 'dataItem' in result:
                return f"User data updated successfully for item ID: {item_id}"
            else:
                return f"Failed to update user data. Response: {result}"
        except Exception as e:
            return f"Error updating user data: {str(e)}"

    # ----------------------------------------
    # Coach Interactions Management
    # ----------------------------------------
    def update_coach_counter(self, item_id, new_coach_counter):
        """
        Updates the 'coachInteractions' field for a specific item.

        :param item_id: The ID of the item to update.
        :param new_coach_interactions: The new value for the 'coachInteractions' field.
                                    Should be a string containing the coach interactions.
        :return: Success or error message.
        """
        return self.update_item(item_id, 'coachCounter', new_coach_counter)

    # ----------------------------------------
    # Coach Interactions Management
    # ----------------------------------------
    def update_job_title(self, item_id, new_job_title):
        current_app.logger.info(f"Updating job title for item {item_id} to {new_job_title}")
        """
        Updates the 'coachInteractions' field for a specific item.

        :param item_id: The ID of the item to update.
        :param new_coach_interactions: The new value for the 'coachInteractions' field.
                                    Should be a string containing the coach interactions.
        :return: Success or error message.
        """
        return self.update_item(item_id, 'jobTitles', new_job_title)

    def update_use_count(self, item_id):
        """
        Increments the 'uses' count by 1 for an item within the RunningInterviews collection.
        """
        # Step 1: Fetch the existing item data
        existing_data = self.get_entry(item_id)
        if not existing_data:
            return f"Item with ID {item_id} not found. Cannot increment 'uses' field."

        # Step 2: Increment the 'uses' field
        field_name = "uses"
        current_value = existing_data.get(field_name, 0)  # Default to 0 if field doesn't exist
        new_value = current_value + 1
        existing_data[field_name] = new_value

        # Step 3: Send the complete data back to update the item
        endpoint = f"items/{item_id}"
        data = {
            "dataCollectionId": self.candidateData_collection_id,
            "dataItem": {
                "data": existing_data
            }
        }
        try:
            result = self._make_request("PUT", endpoint, data)
            if result and 'dataItem' in result:
                return f"'uses' field incremented to {new_value} successfully for item ID: {item_id}"
            else:
                return f"Failed to increment 'uses' field. Response: {result}"
        except Exception as e:
            return f"Error incrementing 'uses' field: {str(e)}"
    # ----------------------------------------
    # Pull Prompt
    # In the coach, we pull from the "Agents" collection. That is we pull the agent rules and then later combine it with
    # the transcript.
    # ----------------------------------------
    def get_prompt(self, interviewTitle):
        """
        Retrieves a prompt based on the job title and run from the Interviews collection.

        :param job_title: The title of the job to query.
        :param run: The run number to construct the level string.
        :return: The prompt for the given job title and run level.
        """

        #level_string = f"Level {run}" if run != 99 else "Demo"

        endpoint = "items/query"
        data = {
            "dataCollectionId": self.template_collection_id,
            "query": {
                "filter": {
                    "interviewTitle": interviewTitle,
                },
                "fields": ["prompt"],
                "limit": 1
            }
        }
        try:
            response = self._make_request("POST", endpoint, data)
            if response and 'dataItems' in response and len(response['dataItems']) > 0:
                prompt = response['dataItems'][0].get('data', {}).get('prompt')
                return prompt
            else:
                print(f"No prompt found for {interviewTitle}")
                return None
        except Exception as e:
            print(f"Error getting prompt: {str(e)}")
            return None

    # ----------------------------------------
    # Pull avatar_selector.json
    # ----------------------------------------
    def get_avatar_selector(self):
        """
        Retrieves 'avatarSelector' JSON content directly from the Wix database.
        """
        endpoint = "items/query"
        data = {
            "dataCollectionId": self.avatar_selector_id,
            "query": {
                "fields": ["avatarSelector"]
            }
        }
        try:
            response = self._make_request("POST", endpoint, data)

            if 'dataItems' in response and len(response['dataItems']) > 0:
                avatar_selector_content = response['dataItems'][0].get('data', {}).get('avatarSelector')
                if avatar_selector_content:
                    try:
                        # Parse the JSON content
                        avatar_selector_json = json.loads(avatar_selector_content)
                        return avatar_selector_json
                    except json.JSONDecodeError as json_error:
                        current_app.logger.error(f"Error parsing avatar selector JSON: {str(json_error)}")
                        return None
                else:
                    current_app.logger.warn(f"No avatarSelector content found for item")
                    return None
            else:
                current_app.logger.warn(f"No avatar selector found in response: {response}")
                return None
        except Exception as e:
            current_app.logger.error(f"Error getting avatar selector: {str(e)}")
            return None


    # ----------------------------------------
    # Transcript Management
    # ----------------------------------------
    def update_transcripts(self, item_id, file_or_path):
        """
        Updates the 'transcripts' field for a specific item with JSON content from a file.

        :param item_id: The ID of the item to update.
        :param file_or_path: Either a file path or an open file object.
        :return: Success or error message.
        """
        try:
            if isinstance(file_or_path, str):
                # It's a file path
                if not os.path.exists(file_or_path):
                    return f"Error: File not found at {file_or_path}"
                with open(file_or_path, 'r') as f:
                    json_content = f.read()
            elif hasattr(file_or_path, 'read'):
                # It's a file xobject
                json_content = file_or_path.read()
                if isinstance(json_content, bytes):
                    json_content = json_content.decode('utf-8')
            else:
                return "Error: Invalid input. Expected file path or file object."

            return self.update_item(item_id, 'transcripts', json_content)
        except Exception as e:
            return f"Error updating transcripts: {str(e)}"

    def remove_transcripts(self, item_id):
        """
        Removes the 'transcripts' field for a specific item by setting it to None.

        :param item_id: The ID of the item to update.
        :return: Success or error message.
        """
        return self.remove_item(item_id, 'transcripts')

    # ----------------------------------------
    # Question Counter Management
    # ----------------------------------------
    def update_question_counter(self, item_id, new_question_counter):
        """
        Updates the 'questionCounter' field for a specific item.

        :param item_id: The ID of the item to update.
        :param new_question_counter: The new value for the 'questionCounter' field.
        :return: Success or error message.
        """
        return self.update_item(item_id, 'questionCounter', new_question_counter)

    def remove_question_counter(self, item_id):
        """
        Removes the 'questionCounter' field for a specific item by setting it to None.

        :param item_id: The ID of the item to update.
        :return: Success or error message.
        """
        return self.remove_item(item_id, 'questionCounter')

    # ----------------------------------------
    # Interaction Number Management
    # ----------------------------------------
    def update_interaction_number(self, item_id, new_interaction_number):
        """
        Updates the 'interactionNumber' field for a specific item.

        :param item_id: The ID of the item to update.
        :param new_interaction_number: The new value for the 'interactionNumber' field.
        :return: Success or error message.
        """
        return self.update_item(item_id, 'interactionNumber', new_interaction_number)

    def remove_interaction_number(self, item_id):
        """
        Removes the 'interactionNumber' field for a specific item by setting it to None.

        :param item_id: The ID of the item to update.
        :return: Success or error message.
        """
        return self.remove_item(item_id, 'interactionNumber')

    # ----------------------------------------
    # Is Active Boolean Management
    # ----------------------------------------
    def update_is_active(self, item_id, is_active):
        """
        Updates the 'isActive' boolean field for a specific item.

        :param item_id: The ID of the item to update.
        :param is_active: The new boolean value for the 'isActive' field.
        :return: Success or error message.
        """
        return self.update_item(item_id, 'isActive', is_active)

    # ----------------------------------------
    # Run Number Management
    # ----------------------------------------
    def update_run(self, item_id, new_run):
        """
        Updates the 'run' field for a specific item.

        :param item_id: The ID of the item to update.
        :param new_run: The new value for the 'run' field.
        :return: Success or error message.
        """
        return self.update_item(item_id, 'run', new_run)

    def remove_run(self, item_id):
        """
        Removes the 'run' field for a specific item by setting it to None.

        :param item_id: The ID of the item to update.
        :return: Success or error message.
        """
        return self.remove_item(item_id, 'run')

    # ----------------------------------------
    # Start Date Management
    # ----------------------------------------
    def update_start_date(self, item_id, new_start_date):
        """
        Updates the 'startDate' field for a specific item.

        :param item_id: The ID of the item to update.
        :param new_start_date: The new value for the 'startDate' field.
        :return: Success or error message.
        """
        return self.update_item(item_id, 'startDate', new_start_date)

    # ----------------------------------------
    # File Link Tree Management
    # ----------------------------------------
    def update_file_link_tree(self, item_id, file_or_path):
        """
        Updates the 'fileLinkTree' field for a specific item with JSON content from a file.

        :param item_id: The ID of the item to update.
        :param file_or_path: Either a file path or an open file object.
        :return: Success or error message.
        """
        try:
            if isinstance(file_or_path, str):
                # It's a file path
                if not os.path.exists(file_or_path):
                    return f"Error: File not found at {file_or_path}"
                with open(file_or_path, 'r') as f:
                    json_content = f.read()
            elif hasattr(file_or_path, 'read'):
                # It's a file object
                json_content = file_or_path.read()
                if isinstance(json_content, bytes):
                    json_content = json_content.decode('utf-8')
            else:
                return "Error: Invalid input. Expected file path or file object."

            return self.update_item(item_id, 'fileLinkTree', json_content)
        except Exception as e:
            return f"Error updating file link tree: {str(e)}"

    def remove_file_link_tree(self, item_id):
        """
        Removes the 'fileLinkTree' field for a specific item by setting it to None.

        :param item_id: The ID of the item to update.
        :return: Success or error message.
        """
        return self.remove_item(item_id, 'fileLinkTree')


    # ----------------------------------------
    # user metrics management
    # ----------------------------------------
    def update_user_metrics(self, session_metrics):
        """
        Updates the 'metrics' collection with user metrics from the session.
        """
        if not session_metrics or 'user_ID' not in session_metrics:
            return "Error: Invalid metrics data or missing user_ID"

        user_id = session_metrics['user_ID']
        metrics_collection_id = 'metrics'

        # First, query to check if the user already has metrics
        endpoint = "items/query"
        query_data = {
            "dataCollectionId": metrics_collection_id,
            "query": {
                "filter": {
                    "user_ID": user_id
                },
                "limit": 1
            }
        }

        try:
            current_app.logger.info(f"Checking for existing metrics for user_ID: {user_id}")
            result = self._make_request("POST", endpoint, query_data)

            # If user metrics exist, update them
            if result and 'dataItems' in result and len(result['dataItems']) > 0:
                # The document ID is in 'id', not '_id'
                document_id = result['dataItems'][0].get('id')
                current_app.logger.info(f"Found existing metrics with document ID: {document_id}")

                # Get the existing metrics from the nested data object
                existing_metrics = result['dataItems'][0].get('data', {})
                updated_metrics = existing_metrics.copy()

                # Update all numeric fields by adding session values
                for key, value in session_metrics.items():
                    if key == 'user_ID':
                        continue  # Skip the user_ID field

                    if key in updated_metrics and isinstance(value, (int, float)):
                        updated_metrics[key] = updated_metrics.get(key, 0) + value
                    else:
                        updated_metrics[key] = value

                # Update the item using the document ID
                update_endpoint = f"items/{document_id}"
                update_data = {
                    "dataCollectionId": metrics_collection_id,
                    "dataItem": {
                        "data": updated_metrics
                    }
                }

                result = self._make_request("PUT", update_endpoint, update_data)
                if result and 'dataItem' in result:
                    current_app.logger.info(f"Updated metrics for user_ID: {user_id}")
                    return f"Metrics updated successfully for user_ID: {user_id}"
                else:
                    current_app.logger.error(f"Failed to update metrics. Response: {result}")
                    return f"Failed to update metrics. Response: {result}"

            # If no metrics exist, create a new entry
            else:
                current_app.logger.info(f"No existing metrics found for user_ID: {user_id}. Creating new entry.")

                # Create a new item
                create_endpoint = "items"
                create_data = {
                    "dataCollectionId": metrics_collection_id,
                    "dataItem": {
                        "data": session_metrics
                    }
                }

                result = self._make_request("POST", create_endpoint, create_data)
                if result and 'dataItem' in result:
                    current_app.logger.info(f"Created new metrics for user_ID: {user_id}")
                    return f"Metrics created successfully for user_ID: {user_id}"
                else:
                    current_app.logger.error(f"Failed to create metrics. Response: {result}")
                    return f"Failed to create metrics. Response: {result}"

        except Exception as e:
            current_app.logger.error(f"Error updating user metrics: {str(e)}")
            return f"Error updating user metrics: {str(e)}"
