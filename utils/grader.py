import re
import json
from .gemini_utils import gemini_generate

def grade_mcq_by_ai(question_text: str, options: list, student_choice: str) -> float:
    """
    Use Gemini to determine if a selected option is correct.
    Returns 1.0 for correct, 0.0 for incorrect.
    """
    prompt = f"""
You are a strict grader. Given a question, listed options, and a student's chosen option,
answer only the single word CORRECT or INCORRECT.

Question:
{question_text}

Options:
{chr(10).join(options)}

Student answer:
{student_choice}
"""
    out = gemini_generate(prompt)
    return 1.0 if "CORRECT" in out.upper() else 0.0

def grade_short_answer_by_ai(model_answer: str, student_answer: str, max_marks: float = 1.0) -> float:
    """
    Ask Gemini to return a JSON: {"score": number}
    Fallback to simple heuristic if parsing fails.
    """
    prompt = f"""
You are a grader. Given a model answer and student answer, return EXACTLY one JSON object:
{{"score": number_between_0_and_{max_marks}}}

Model answer:
{model_answer}

Student answer:
{student_answer}
"""
    raw = gemini_generate(prompt)
    try:
        parsed = json.loads(raw)
        score = float(parsed.get("score", 0.0))
        return max(0.0, min(score, max_marks))
    except Exception:
        # fallback heuristic: overlap of keywords
        key_terms = re.findall(r'\b\w+\b', (model_answer or "").lower())
        if not key_terms:
            return 0.0
        matches = sum(1 for k in set(key_terms) if k in (student_answer or "").lower())
        return round((matches / max(1, len(set(key_terms)))) * max_marks, 3)
