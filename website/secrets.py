from flask import Blueprint, jsonify, current_app
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from flask_login import login_required


# Create the blueprint
secrets = Blueprint('secrets', __name__)

# Key Vault URL
key_vault_url = "https://mindorahkeys.vault.azure.net/"

# Create a credential object
credential = DefaultAzureCredential()

# Create a secret client
secret_client = SecretClient(vault_url=key_vault_url, credential=credential)

def get_secret(secret_name):
    try:
        return secret_client.get_secret(secret_name).value
    except Exception as e:
        current_app.logger.error(f"Error retrieving secret {secret_name}: {e}")
        return None

# Add the routes to the blueprint
@secrets.route('/<secret_name>')
@login_required
def get_azure_secret(secret_name):
    allowed_secrets = {'KEY1-SPEECH', 'SPEECH-LOCATION'}
    
    if secret_name not in allowed_secrets:
        return jsonify({'error': 'Invalid secret name'}), 403
        
    secret_value = get_secret(secret_name)
    if secret_value:
        return jsonify({'value': secret_value})
    return jsonify({'error': 'Secret not found'}), 404