import re

def normalize_inline_options(text: str) -> str:
    """
    Clean up generator output so options (A) B) C) D)) are on their own lines,
    strip noisy headers, and normalize whitespace.
    """
    if not text:
        return ""

    # Remove leading boilerplate like "Here are 10 MCQ questions"
    text = re.sub(r"(?i)here are.*?questions.*?:", "", text)
    # Remove explicit "(Correct: ...)" fragments to avoid duplication in parsing
    text = re.sub(r"\(Correct:.*?\)", "", text, flags=re.S)

    # Make sure A) B) C) D) start on their own line
    text = re.sub(r"(?<!\n)\s+([A-D]\))", r"\n\1", text)
    text = re.sub(r"([^\n])([A-D]\))", r"\1\n\2", text)

    # Normalize whitespace per line
    lines = text.splitlines()
    cleaned = [re.sub(r"[ \t]+", " ", ln).strip() for ln in lines]
    return "\n".join(cleaned).strip()

def split_question_blocks(text: str) -> list:
    """
    Split the plain text into blocks, each beginning with '1. ', '2. ', etc.
    Returns a list of text blocks.
    """
    text = normalize_inline_options(text)
    pattern = re.compile(r"(?s)(?:^|\n)\s*(\d+\.\s.*?)\s*(?=\n\s*\d+\.|\Z)")
    matches = pattern.findall("\n" + text)
    if matches:
        return [m.strip() for m in matches if m.strip()]
    # fallback: split on double newlines
    return [blk.strip() for blk in text.split("\n\n") if blk.strip()]

def extract_question_and_options(block: str) -> tuple:
    """
    Given a text block, extract the question text and a list of options (if any).
    Returns (question_text, options_list_or_None).
    """
    parts = re.split(r'\n(?=[A-D]\))', block, maxsplit=1)
    question_line = parts[0].strip()
    question_text = re.sub(r'^\d+\.\s*', '', question_line).strip()

    options = []
    if len(parts) > 1:
        opts_block = parts[1].strip()
        opt_lines = re.findall(r'([A-D]\)\s*.*)', opts_block)
        if not opt_lines:
            segs = re.split(r'(?=[A-D]\))', opts_block)
            opt_lines = [s.strip() for s in segs if s.strip()]
        for ol in opt_lines:
            m = re.match(r'^([A-D]\))\s*(.*)', ol, flags=re.S)
            if m:
                letter = m.group(1)
                body = re.sub(r'\s+', ' ', m.group(2).strip())
                options.append(f"{letter} {body}")
    return question_text, options or None

def parse_questions(plain_text: str) -> list:
    """
    Parse raw plain-text quiz into a structured list of questions:
    [{id, question, options}].
    """
    blocks = split_question_blocks(plain_text)
    parsed = []
    for i, blk in enumerate(blocks, start=1):
        q_text, opts = extract_question_and_options(blk)
        parsed.append({
            "id": f"q{i}",
            "question": q_text,
            "options": opts
        })
    return parsed
