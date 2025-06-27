import json
from openai import AzureOpenAI
from .secrets import get_secret

DEPLOYMENT_NAME = "o4-mini"

cv_extraction_tool = {
    "type": "function",
    "function": {
        "name": "extract_cv_information",
        "description": "Extracts relevant professional experience, skills, and summary from CV text for interview preparation.",
        "parameters": {
            "type": "object",
            "properties": {
                "is_valid_cv": {
                    "type": "boolean",
                    "description": "Indicates whether the provided text appears to be a CV/resume."
                },
                "candidate_name": {
                    "type": "string",
                    "description": "The full name of the candidate, if available."
                },
                "summary": {
                    "type": "string",
                    "description": "The professional summary or objective statement from the CV, if present."
                },
                "professional_experience": {
                    "type": "array",
                    "description": "A list of the candidate's previous or current roles.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "job_title": {"type": "string", "description": "The title of the role"},
                            "company": {"type": "string", "description": "The name of the company"},
                            "duration": {"type": "string", "description": "The dates or duration worked"},
                            "level": {"type": "string", "description": "Inferred seniority level"},
                            "key_responsibilities_or_achievements": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Key responsibilities or achievements"
                            }
                        },
                        "required": ["job_title", "company"]
                    }
                },
                "skills": {
                    "type": "array",
                    "description": "A list of key technical or soft skills mentioned in the CV.",
                    "items": {"type": "string"}
                }
            },
            "required": ["is_valid_cv"]
        }
    }
}

def process_cv_with_ai(cv_text):
    client = AzureOpenAI(
        api_key=get_secret('KEY1-AI-US'),
        api_version="2025-04-01-preview",
        azure_endpoint=get_secret('AI-ENDPOINT-US')
    )

    messages = [
        {"role": "system", "content": """You are an expert assistant specializing in extracting structured information from curriculum vitae (CVs).

First, determine if the provided text is actually a CV/resume. A valid CV/resume typically includes:
- Professional experience with job titles and companies
- Skills section or skills mentioned throughout
- Educational background (usually)
- Contact information or personal details
- Possibly a professional summary or objective

If the text doesn't appear to be a CV/resume, set is_valid_cv to false and don't extract any information.
If it is a valid CV, set is_valid_cv to true and extract the requested information."""},
        {"role": "user", "content": f"Please analyze the following text and determine if it's a CV/resume. If it is, extract the professional experience and skills:\n\n{cv_text}"}
    ]

    response = client.chat.completions.create(
        model=DEPLOYMENT_NAME,
        messages=messages,
        tools=[cv_extraction_tool],
        tool_choice={"type": "function", "function": {"name": "extract_cv_information"}}
    )

    tool_calls = response.choices[0].message.tool_calls
    if not tool_calls:
        raise ValueError("AI did not return structured data")

    extracted_data = json.loads(tool_calls[0].function.arguments)

    # Check if it's a valid CV
    if not extracted_data.get("is_valid_cv", False):
        return {"is_valid_cv": False, "message": "<-- IS NOT CV -->"}

    return extracted_data
