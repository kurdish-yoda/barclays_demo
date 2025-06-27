import pdfplumber
import logging
import tiktoken
import requests
import io

logging.getLogger("pdfminer").setLevel(logging.ERROR)

def count_tokens(text, model="gpt-4"):
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

def extract_raw_text_from_url(url):
    """
    Extract text from a PDF URL without saving to disk
    """
    # Stream the PDF from the URL
    response = requests.get(url)
    response.raise_for_status()  # Ensure we got a valid response

    # Create an in-memory binary stream
    pdf_file_object = io.BytesIO(response.content)

    # Process the PDF using the in-memory stream
    with pdfplumber.open(pdf_file_object) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() or ""

    token_count = count_tokens(text)
    return {
        "text": text,
        "token_count": token_count
    }
