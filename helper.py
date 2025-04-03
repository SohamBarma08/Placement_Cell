import google.generativeai as genai
import fitz  # PyMuPDF for PDF text extraction
import nltk
from nltk.tokenize import word_tokenize
from nltk.tag import pos_tag
from sentence_transformers import SentenceTransformer, util

#  Download required NLTK models (only runs once)
nltk.download('punkt')
nltk.download('averaged_perceptron_tagger')
nltk.download('stopwords')
nltk.download('punkt_tab')
nltk.download('averaged_perceptron_tagger_eng')

# Load SBERT Model for similarity scoring
model = SentenceTransformer("all-MiniLM-L6-v2")

def configure_genai(api_key):
    """Configure the Generative AI API with error handling."""
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        raise Exception(f"Failed to configure Generative AI: {str(e)}")
    

### ** PDF Text Extraction**
def extract_pdf_text(pdf_file):
    """Extract text from a PDF using PyMuPDF with improved handling."""
    try:
        doc = fitz.open("pdf", pdf_file.read())  # Open from file stream
        text = "".join(page.get_text("text") for page in doc if page.get_text("text"))

        if not text.strip():
            print("⚠️ Extracted text is empty! The PDF might be an image or corrupted.")
        
        return text.strip()  # Return clean text

    except Exception as e:
        print("Error extracting text from PDF:", e)
        return ""


### ** Skill Extraction Using NLTK**
def extract_skills_nltk(text):
    """Extracts relevant skills using NLTK, filtering out generic words."""
    words = word_tokenize(text)
    tagged_words = pos_tag(words)

    # Extract nouns (skills are usually nouns)
    skills = [
        word.lower() for word, pos in tagged_words
        if pos in ["NN", "NNS", "NNP", "NNPS"]  # Keep nouns
        and word.isalpha()  # Remove punctuation/numbers
        and len(word) > 1  # Remove single characters
    ]

    # Remove stopwords & generic words
    stopwords = set(nltk.corpus.stopwords.words("english"))
    generic_words = {"software", "build", "create", "team", "company", "project", "develop"}
    
    skills = {word for word in skills if word not in stopwords and word not in generic_words}
    return list(skills)


### ** Skill Extraction Using Google Gemini AI**
def extract_skills_gemini(text):
    """Uses Google Gemini AI to extract skills and keywords from the text."""
    prompt = f"Extract all job-relevant skills, technologies, and certifications from this text:\n\n{text}"
    
    try:
        response = genai.GenerativeModel("gemini-1.5-pro-latest").generate_content(prompt)
        return response.text.split(", ") if response else []
    
    except Exception as e:
        if "429" in str(e):
            print(" Gemini API quota exceeded. Falling back to NLTK.")
            return extract_skills_nltk(text)
        
        print("Error using Gemini AI:", e)
        return []


### ** Semantic Similarity Score Using SBERT**
def get_similarity_score(resume_text, job_desc):
    """Compute advanced semantic similarity using SBERT."""
    embeddings = model.encode([resume_text, job_desc], convert_to_tensor=True)
    similarity = util.pytorch_cos_sim(embeddings[0], embeddings[1])

    return float(similarity.item()) * 100  # Convert to percentage


### ** ATS Scoring Algorithm**
def calculate_ats_score(resume_text, job_desc, use_gemini=True):
    """Compute ATS Score using Gemini AI (primary) and NLTK (fallback)."""
    similarity = get_similarity_score(resume_text, job_desc)

    gemini_skills, gemini_keywords = set(), set()
    if use_gemini:
        gemini_skills = set(extract_skills_gemini(resume_text))
        gemini_keywords = set(extract_skills_gemini(job_desc))

    
    nltk_skills, nltk_keywords = set(), set()
    if not gemini_skills or not gemini_keywords:
        print(" Gemini API failed or returned no skills. Using NLTK instead.")
        nltk_skills = set(extract_skills_nltk(resume_text))
        nltk_keywords = set(extract_skills_nltk(job_desc))

    resume_skills = gemini_skills if gemini_skills else nltk_skills
    job_keywords = gemini_keywords if gemini_keywords else nltk_keywords

    #  Convert to lowercase for better matching
    resume_skills = {skill.lower() for skill in resume_skills}
    job_keywords = {skill.lower() for skill in job_keywords}

    missing_keywords = list(job_keywords - resume_skills)

    #  Categorize skills based on importance
    critical_skills = {"python", "java", "sql", "machine learning", "deep learning", "cloud"}
    general_skills = job_keywords - critical_skills

    #  Count missing critical & general skills
    missing_critical = len(set(missing_keywords) & critical_skills)
    missing_general = len(set(missing_keywords) & general_skills)

    #  Weighting System
    skill_match_score = (1 - len(missing_keywords) / max(1, len(job_keywords))) * 50  # 50% weight
    similarity_score = similarity * 0.4  # 40% weight
    experience_bonus = 5 if "experience" in resume_skills else 0
    certification_bonus = 10 if "certified" or "certification" or "achievements" in resume_skills else 5

    #  Apply Penalties for Missing Skills
    # penalty = (missing_critical * 3) + (missing_general * 1)

    final_score = skill_match_score + similarity_score + experience_bonus + certification_bonus #- penalty

    #  Ensure score is within 0-100
    final_score = max(0, min(100, final_score))

    print("🔹 Final ATS Score:", final_score)

    return round(final_score, 2), missing_keywords