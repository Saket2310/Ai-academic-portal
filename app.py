# app.py
import streamlit as st
from pathlib import Path
import tempfile, uuid, os, json

# utils (ensure these files exist as per previous instructions)
from utils.gemini_utils import configure_gemini, gemini_generate
from utils.extract_text import extract_text_from_path
from utils.parser import parse_questions
from utils.grader import grade_mcq_by_ai, grade_short_answer_by_ai
from utils.crossword import build_crossword_from_text, grade_crossword_submission

# Configure Gemini (reads GEMINI_API_KEY from env or .env)
configure_gemini()

# Assignments folder
ASSIGN_FOLDER = Path("assignments")
# If a file named 'assignments' exists, remove it or rename it before running.
if ASSIGN_FOLDER.exists() and not ASSIGN_FOLDER.is_dir():
    # If it's a file (not folder), rename it out of the way
    try:
        ASSIGN_FOLDER.rename("assignments_bak")
    except Exception:
        pass
ASSIGN_FOLDER.mkdir(exist_ok=True)

st.set_page_config(page_title="Igris - Academic Portal", layout="wide")
st.title("Igris — Academic Portal")

tabs = st.tabs(["Teacher", "Student", "Assignments"])

##### TEACHER TAB #####
with tabs[0]:
    st.header("Teacher — Generate Assignment")
    uploaded = st.file_uploader("Upload PDF / DOCX / PPTX", type=['pdf','docx','pptx'])
    q_type = st.selectbox("Question type", ["MCQ", "True/False", "Short Answer", "Numerical", "Coding", "Crossword"], index=0)
    num_q = st.number_input("Number of questions / words", min_value=1, max_value=30, value=8)
    difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=1)
    batch_name = st.text_input("Assign to batch (name)", value="DS-2022-2023-B1")

    if uploaded:
        st.write("Uploaded file:", uploaded.name)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=uploaded.name)
        tmp.write(uploaded.getvalue())
        tmp.flush()
        tmp_path = tmp.name

        if st.button("Generate Questions / Crossword"):
            with st.spinner("Extracting text and generating..."):
                extracted_text = extract_text_from_path(tmp_path)
                if q_type == "Crossword":
                    cw = build_crossword_from_text(extracted_text, num_words=num_q, grid_size=15)
                    st.session_state['latest_crossword'] = cw
                    st.success("Crossword generated — preview below.")
                    st.markdown("### Clues")
                    for w in cw["words"]:
                        st.write(f"- **{w}**: {cw['clues'].get(w,'')}")
                    st.markdown("### Grid preview")
                    st.code("\n".join(cw["grid"]), language=None)
                else:
                    prompt = f"""
You are Igris. Generate exactly {num_q} {q_type} questions of {difficulty} difficulty from the context below.
Return plain readable questions only, each formatted as:
1. Question text
A) option A
B) option B
C) option C
D) option D
Correct: B

Context:
{extracted_text[:3500]}
"""
                    raw = gemini_generate(prompt)
                    st.session_state['latest_raw'] = raw
                    st.success("Questions generated — preview below.")
                    st.code(raw, language=None)

        # cleanup tmp file (optional)
        # os.remove(tmp_path)

    # Save & assign
    if st.session_state.get('latest_crossword') or st.session_state.get('latest_raw'):
        if st.button("Save & Assign to Batch"):
            aid = uuid.uuid4().hex
            if st.session_state.get('latest_crossword'):
                obj = {
                    "meta": {
                        "id": aid,
                        "batch": batch_name,
                        "q_type": "Crossword",
                        "num_q": num_q,
                        "difficulty": difficulty,
                        "source_file": uploaded.name if uploaded else None
                    },
                    "crossword": st.session_state['latest_crossword']
                }
                out_path = ASSIGN_FOLDER / f"assignment_{aid}.crossword.json"
                out_path.write_text(json.dumps(obj, indent=2), encoding="utf-8")
                st.success(f"Crossword assignment saved: {out_path.name}")
            else:
                # save normal text assignment + meta
                txt_path = ASSIGN_FOLDER / f"assignment_{aid}.txt"
                meta_path = ASSIGN_FOLDER / f"assignment_{aid}.meta.json"
                meta = {
                    "id": aid,
                    "batch": batch_name,
                    "q_type": q_type,
                    "num_q": num_q,
                    "difficulty": difficulty,
                    "source_file": uploaded.name if uploaded else None
                }
                txt_path.write_text(st.session_state['latest_raw'], encoding="utf-8")
                meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
                st.success(f"Assignment saved: {txt_path.name}")

##### STUDENT TAB #####
with tabs[1]:
    st.header("Student — Take Assignment")
    files = sorted(list(ASSIGN_FOLDER.glob("assignment_*.txt")) + list(ASSIGN_FOLDER.glob("assignment_*.crossword.json")), key=lambda p: p.stat().st_mtime, reverse=True)
    choices = [p.name for p in files]
    chosen = st.selectbox("Select assignment", choices) if choices else None

    if chosen and st.button("Load Assignment"):
        path = ASSIGN_FOLDER / chosen
        if chosen.endswith(".crossword.json"):
            obj = json.loads(path.read_text(encoding="utf-8"))
            st.session_state['crossword_obj'] = obj
            st.session_state['quiz_type'] = "Crossword"
            # initialize student grid if not present
            size = obj['crossword'].get("size", len(obj['crossword']['grid']))
            if 'student_grid' not in st.session_state or len(st.session_state.get('student_grid', [])) != size:
                st.session_state['student_grid'] = ["".join(["" for _ in range(size)]) for _ in range(size)]
        else:
            content = path.read_text(encoding="utf-8")
            st.session_state['quiz_text'] = content
            st.session_state['parsed'] = parse_questions(content)
            st.session_state['quiz_type'] = "Regular"

    if st.session_state.get('quiz_type') == "Regular" and st.session_state.get('parsed'):
        parsed = st.session_state['parsed']
        st.write(f"Loaded {len(parsed)} questions.")
        answers = {}
        for i, q in enumerate(parsed):
            st.markdown(f"**{i+1}. {q['question']}**")
            if q.get('options'):
                choice = st.radio("", q['options'], key=f"q_{i}")
                answers[q['id']] = choice
            else:
                txt = st.text_input("Your answer", key=f"txt_{i}")
                answers[q['id']] = txt
            st.write("")

        if st.button("Submit & Grade"):
            total_marks = 0.0
            obtained = 0.0
            for q in parsed:
                qid = q['id']
                max_marks = 1.0
                total_marks += max_marks
                resp = answers.get(qid, "")
                if q.get('options'):
                    score = grade_mcq_by_ai(q['question'], q['options'], resp)
                else:
                    score = grade_short_answer_by_ai("model answer not provided", resp, max_marks=1.0)
                obtained += score
            st.success(f"Score: {obtained}/{total_marks}")
            rid = uuid.uuid4().hex
            res_path = ASSIGN_FOLDER / f"result_{rid}.json"
            result_obj = {"id": rid, "assignment": chosen, "score": obtained, "total": total_marks}
            res_path.write_text(json.dumps(result_obj, indent=2), encoding="utf-8")
            st.write("Result saved.")

    if st.session_state.get('quiz_type') == "Crossword" and st.session_state.get('crossword_obj'):
        cwobj = st.session_state['crossword_obj']['crossword']
        size = cwobj.get("size", len(cwobj["grid"]))
        grid = cwobj["grid"]

        st.markdown("#### Clues")
        for w in cwobj["words"]:
            st.write(f"- **{w}**: {cwobj['clues'].get(w,'')}")

        st.markdown("#### Fill crossword (enter letters):")
        student_grid = st.session_state['student_grid']
        # Render grid as inputs
        for r in range(size):
            cols = st.columns(size)
            row_chars = list(student_grid[r]) if student_grid[r] else [""]*size
            for c in range(size):
                val = row_chars[c] if c < len(row_chars) else ""
                v = cols[c].text_input("", value=val, max_chars=1, key=f"cell_{r}_{c}")
                row_chars[c] = (v or "").upper()
            st.session_state['student_grid'][r] = "".join(row_chars)

        if st.button("Submit Crossword"):
            student_lines = st.session_state['student_grid']
            sol_lines = cwobj['grid']
            result = grade_crossword_submission(sol_lines, student_lines)
            st.success(f"Crossword score: {result['correct_cells']}/{result['total_cells']} ({result['score_fraction']*100:.1f}%)")
            rid = uuid.uuid4().hex
            res_path = ASSIGN_FOLDER / f"result_{rid}.json"
            result_obj = {"id": rid, "assignment": chosen, "score": result['score_fraction'], "correct_cells": result['correct_cells'], "total_cells": result['total_cells']}
            res_path.write_text(json.dumps(result_obj, indent=2), encoding="utf-8")
            st.write("Result saved.")

##### ASSIGNMENTS TAB #####
with tabs[2]:
    st.header("Assignments & Results")
    files = sorted(list(ASSIGN_FOLDER.glob("assignment_*.meta.json")) + list(ASSIGN_FOLDER.glob("assignment_*.crossword.json")), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        st.info("No assignments saved yet.")
    else:
        for meta_file in files:
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                meta = {"id": meta_file.stem}
            aid = meta.get("id", meta_file.stem)
            # determine display name for crossword vs regular
            display_name = meta_file.name
            st.markdown(f"**{display_name}** — batch: {meta.get('batch')}, type: {meta.get('q_type')}, difficulty: {meta.get('difficulty')}")
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button(f"View {aid}", key=f"view_{aid}"):
                    # find the matching assignment file
                    # for crossword meta, content may be inside the same file; try to display
                    candidate_txt = ASSIGN_FOLDER / f"assignment_{aid}.txt"
                    candidate_cw = ASSIGN_FOLDER / f"assignment_{aid}.crossword.json"
                    if candidate_txt.exists():
                        content = candidate_txt.read_text(encoding="utf-8")
                        st.text_area("Assignment content", content, height=300)
                    elif candidate_cw.exists():
                        cont = candidate_cw.read_text(encoding="utf-8")
                        st.text_area("Assignment content (crossword json)", cont, height=300)
            with col2:
                if st.button(f"Download {aid}", key=f"dl_{aid}"):
                    candidate_txt = ASSIGN_FOLDER / f"assignment_{aid}.txt"
                    candidate_cw = ASSIGN_FOLDER / f"assignment_{aid}.crossword.json"
                    if candidate_txt.exists():
                        st.download_button(label="Download assignment", data=candidate_txt.read_text(encoding="utf-8"), file_name=candidate_txt.name)
                    elif candidate_cw.exists():
                        st.download_button(label="Download assignment", data=candidate_cw.read_text(encoding="utf-8"), file_name=candidate_cw.name)
