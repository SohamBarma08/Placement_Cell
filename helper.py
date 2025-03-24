import google.generativeai as genai
import PyPDF2 as pdf
import json
import re

def list_available_models():
    """List all available models from Google Generative AI."""
    try:
        models = genai.list_models()
        for model in models:
            print(f"Model ID: {model['model_id']}, Description: {model.get('description', 'No description')}")
    except Exception as e:
        print(f"Error listing models: {str(e)}")


def configure_genai(api_key):
    """Configure the Generative AI API with error handling."""
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        raise Exception(f"Failed to configure Generative AI: {str(e)}")
    

def get_gemini_response(prompt):
    """Generate a response using Gemini with enhanced error handling and response validation."""
    try:
        model = genai.GenerativeModel('models/gemini-1.5-pro-latest')
        response = model.generate_content(prompt)
        
        # Ensure response is not empty
        if not response or not response.text:
            raise Exception("Empty response received from Gemini")
            
        response_text = response.text.strip()
        print("Raw Gemini Response:", response_text[:500])  # Log the raw response for debugging

        # Attempt to parse response as JSON directly
        try:
            response_json = json.loads(response_text)
            return json.dumps(response_json)  # Convert dictionary to JSON string
        except json.JSONDecodeError:
            # Attempt to extract valid JSON using regex pattern
            json_pattern = r'\{(?:[^{}]|(?:\{.*\}))*\}'  # Supports nested JSON structures
            match = re.search(json_pattern, response_text, re.DOTALL)
            
            if match:
                json_text = match.group()
                try:
                    response_json = json.loads(json_text)
                    return json.dumps(response_json)  # Convert dictionary to JSON string
                except json.JSONDecodeError:
                    raise Exception("Failed to parse extracted JSON content")
            else:
                raise Exception("No valid JSON structure found in the response")
                
    except Exception as e:
        raise Exception(f"Error generating response: {str(e)}")



def extract_pdf_text(uploaded_file):
    """Extract text from a PDF file with enhanced error handling."""
    try:
        reader = pdf.PdfReader(uploaded_file)
        if len(reader.pages) == 0:
            raise Exception("PDF file is empty")
            
        text = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)
                
        if not text:
            raise Exception("No text could be extracted from the PDF")
            
        return " ".join(text)
        
    except Exception as e:
        raise Exception(f"Error extracting PDF text: {str(e)}")


def prepare_prompt(resume_text, job_description):
    """Prepare the input prompt focusing on job description and treating resume as a fresher's resume."""
    if not resume_text or not job_description:
        raise ValueError("Resume text and job description cannot be empty")
        
    prompt_template = """
    Act as an expert ATS (Applicant Tracking System) specialist with deep expertise in:
    - Screening and evaluating resumes, particularly freshers' resumes with limited work experience.
    - Assessing alignment with job descriptions based on required skills, qualifications, and educational background.
    - Providing constructive feedback on areas of improvement for better job matching.

    The resume provided below is from a fresher applicant. Analyze it against the job description with moderate difficulty criteria.
    Focus more on the alignment of educational background, skills, relevant coursework, internships, and projects.

    Resume (Fresher):
    {resume_text}
    
    Job Description:
    {job_description}
    
    Provide a response in the following JSON format ONLY:
    {{
        "JD Match": "percentage between 0-100",
        "MissingKeywords": ["keyword1", "keyword2", ...],
        "Profile Summary": "Detailed analysis of the match and specific improvement suggestions"
    }}
    """
    
    return prompt_template.format(
        resume_text=resume_text.strip(),
        job_description=job_description.strip()
    )
