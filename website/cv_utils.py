import logging

# Configure logging levels for verbose libraries
logging.getLogger("pdfminer").setLevel(logging.ERROR)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

import requests
import pdfplumber
import logging
import tiktoken
import io
import bleach
import defusedxml
from html import escape
from .secrets import get_secret

# Activate defusedxml to protect against XML vulnerabilities
defusedxml.defuse_stdlib()

def count_tokens(text, model="gpt-4"):
    """
    Count tokens in text for a specific model.

    Args:
        text: The text to count tokens for
        model: The model to use for tokenization (default: gpt-4)

    Returns:
        Number of tokens
    """
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

def sanitize_text(text):
    """
    Sanitize the extracted text using bleach library.

    Args:
        text: The extracted text from PDF

    Returns:
        Sanitized text
    """
    if not text:
        return ""

    # First escape HTML entities
    text = escape(text)

    # Clean with bleach - removing all HTML tags and potentially harmful content
    # We're stripping all tags for maximum security
    cleaned_text = bleach.clean(text, tags=[], strip=True)

    return cleaned_text

def extract_raw_text_from_url(url):
    """
    Extract text from a PDF URL without saving to disk.

    Args:
        url: The URL to the PDF file

    Returns:
        Dictionary with text content and token count
    """
    # Stream the PDF from the URL
    response = requests.get(url)
    response.raise_for_status()  # Ensure we got a valid response

    # Create an in-memory binary stream
    pdf_file_object = io.BytesIO(response.content)

    # Process the PDF using the in-memory stream
    try:
        with pdfplumber.open(pdf_file_object) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text += page_text

        # Sanitize the text to remove potentially harmful content
        sanitized_text = sanitize_text(text)

        token_count = count_tokens(sanitized_text)
        return {
            "text": sanitized_text,
            "token_count": token_count
        }
    except Exception as e:
        logging.error(f"Error extracting text from PDF: {str(e)}")
        raise ValueError("Error processing your PDF. Please ensure it's a valid document.")

def get_file_url_from_wix_document(document_uri, api_key=None, site_id=None):
    """
    Converts a Wix document URI to an accessible URL.

    Args:
        document_uri: The Wix document URI
        api_key: Optional Wix API key (will be fetched from secrets if not provided)
        site_id: Optional Wix site ID (will be fetched from secrets if not provided)

    Returns:
        An accessible URL to the document
    """
    # Get API credentials if not provided
    if not api_key:
        api_key = get_secret('WIX-API-KEY')
    if not site_id:
        site_id = get_secret('WIX-SITE-ID')

    if not api_key or not site_id:
        logging.error("Could not retrieve WIX-API-KEY or WIX-SITE-ID from secrets.")
        return None

    # Parse the URI
    parts = document_uri.replace('wix:document://', '').split('/')

    if len(parts) >= 2:
        document_id = parts[1]
    else:
        logging.error(f"Invalid document URI format: {document_uri}")
        return None

    # Try different API endpoints
    # 1. Try the site-media API first
    url = f"https://www.wixapis.com/site-media/v1/files/{document_id}"
    headers = {
        'Authorization': api_key,
        'wix-site-id': site_id
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        result = response.json()
        if 'file' in result and 'url' in result['file']:
            return result['file']['url']

    except Exception as e:
        logging.warning(f"First API attempt failed: {str(e)}")

    # 2. Try the documents API
    url = "https://www.wixapis.com/documents/v1/documents/download"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': api_key,
        'wix-site-id': site_id
    }

    data = {
        "documentId": document_id
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()

        result = response.json()
        if 'downloadUrl' in result:
            return result['downloadUrl']

    except Exception as e:
        logging.warning(f"Second API attempt failed: {str(e)}")

    # 3. Try the file download URL API
    try:
        file_url = f"https://www.wixapis.com/site-media/v1/files/{document_id}/download-url"
        response = requests.get(file_url, headers={
            'Authorization': api_key,
            'wix-site-id': site_id
        })
        response.raise_for_status()

        result = response.json()
        if 'downloadUrl' in result:
            return result['downloadUrl']

    except Exception as e:
        logging.warning(f"Third API attempt failed: {str(e)}")

    logging.error("All API attempts failed to get a download URL")
    return None

def fetch_wix_cv_data(user_id):
    """
    Fetches a user's CV document URI from the Wix CMS.

    Args:
        user_id: The user ID to fetch the CV for

    Returns:
        The CV document URI or None if not found
    """
    # Get API credentials
    api_key = get_secret('WIX-API-KEY')
    site_id = get_secret('WIX-SITE-ID')

    if not api_key or not site_id:
        logging.error("Could not retrieve WIX-API-KEY or WIX-SITE-ID from secrets.")
        return None

    # Set up the API request
    url = "https://www.wixapis.com/wix-data/v2/items/query"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': api_key,
        'wix-site-id': site_id
    }

    data = {
        "dataCollectionId": "CandidateData",
        "query": {
            "filter": {
                "userId": user_id
            },
            "fields": ["cv"],
            "limit": 1
        }
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()

        result = response.json()

        if result and 'dataItems' in result and len(result['dataItems']) > 0:
            cv_data = result['dataItems'][0].get('data', {}).get('cv')
            return cv_data
        else:
            logging.warning(f"CV not found for user ID: {user_id}")
            return None

    except Exception as e:
        logging.error(f"Error fetching CV: {str(e)}")
        return None

def get_cv_text(user_id):
    """
    Main function to get CV text for a user.

    This function:
    1. Fetches the CV document URI from Wix
    2. Converts it to an accessible URL
    3. Extracts text from the PDF

    Args:
        user_id: The user ID to get CV text for

    Returns:
        Dictionary with text and token count if successful, None otherwise
    """
    # Get API credentials for reuse
    api_key = get_secret('WIX-API-KEY')
    site_id = get_secret('WIX-SITE-ID')

    # Step 1: Fetch the document URI
    document_uri = fetch_wix_cv_data(user_id)

    if not document_uri:
        logging.error(f"Could not fetch document URI for user {user_id}")
        return None

    # Step 2: Check if it's a Wix document URI and convert to URL
    if isinstance(document_uri, str) and document_uri.startswith('wix:document://'):
        file_url = get_file_url_from_wix_document(document_uri, api_key, site_id)

        if not file_url:
            logging.error("Failed to get an accessible URL for the document")
            return None

        # Step 3: Extract text from the PDF with security measures
        try:
            pdf_data = extract_raw_text_from_url(file_url)
            return pdf_data
        except Exception as e:
            logging.error(f"Error extracting text from PDF: {str(e)}")
            return None
    else:
        logging.error(f"Unexpected CV data format: {document_uri}")
        return None
