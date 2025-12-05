# utils/crossword.py
import random
import json
from typing import List, Tuple, Dict
from .gemini_utils import gemini_generate

def ask_gemini_for_words_and_clues(extracted_text: str, num_words: int = 10) -> List[Tuple[str, str]]:
    """
    Ask Gemini to extract important words and short clues from the extracted_text.
    Returns a list of (word, clue) pairs. Words are uppercase and contain only A-Z.
    """
    prompt = f"""
You are Igris. From the text below, extract the {num_words} most important single-word terms (one-word each)
useful for a classroom crossword. For each word return a short clue (one sentence).
Return output as lines in the format: WORD|Clue

Text:
{extracted_text[:4500]}
"""
    out = gemini_generate(prompt)
    pairs = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = None
        for sep in ["|", ":", "-", "—"]:
            if sep in line:
                parts = [p.strip() for p in line.split(sep, 1)]
                break
        if not parts:
            sp = line.split(maxsplit=1)
            if len(sp) == 2:
                parts = [sp[0].strip(), sp[1].strip()]
            else:
                continue
        word = parts[0].upper()
        word = "".join([ch for ch in word if ch.isalpha()])[:15]
        clue = parts[1].strip()
        if len(word) >= 3 and clue:
            pairs.append((word, clue))
        if len(pairs) >= num_words:
            break
    return pairs

def create_empty_grid(size=15):
    return [["" for _ in range(size)] for _ in range(size)]

def place_word(grid, word, row, col, direction):
    n = len(word)
    size = len(grid)
    if direction == "across":
        if col + n > size:
            return False
        for i,ch in enumerate(word):
            cur = grid[row][col+i]
            if cur not in ("", ch):
                return False
        for i,ch in enumerate(word):
            grid[row][col+i] = ch
        return True
    else:  # down
        if row + n > size:
            return False
        for i,ch in enumerate(word):
            cur = grid[row+i][col]
            if cur not in ("", ch):
                return False
        for i,ch in enumerate(word):
            grid[row+i][col] = ch
        return True

def try_place_words(words: List[str], size=15, shuffle=True) -> Dict:
    if shuffle:
        words = sorted(words, key=lambda w: -len(w))
    grid = create_empty_grid(size)
    placed = []
    unused = []

    if words:
        first = words[0]
        r = size // 2
        c = max(0, (size - len(first)) // 2)
        if place_word(grid, first, r, c, "across"):
            placed.append({"word": first, "row": r, "col": c, "dir": "across"})
        else:
            ok = False
            for _ in range(200):
                rr = random.randrange(size)
                cc = random.randrange(size)
                if place_word(grid, first, rr, cc, random.choice(["across","down"])):
                    placed.append({"word": first, "row": rr, "col": cc, "dir": "across"})
                    ok = True
                    break
            if not ok:
                unused.append(first)

    for w in words[1:]:
        placed_flag = False
        for attempt in range(200):
            if not placed:
                break
            pw = random.choice(placed)
            base_word = pw["word"]
            possible_matches = []
            for i,ch1 in enumerate(base_word):
                for j,ch2 in enumerate(w):
                    if ch1 == ch2:
                        possible_matches.append((i,j))
            if not possible_matches:
                row = random.randrange(size)
                col = random.randrange(size)
                dirc = random.choice(["across","down"])
                if place_word(grid,w,row,col,dirc):
                    placed.append({"word": w, "row": row, "col": col, "dir": dirc})
                    placed_flag = True
                    break
                continue
            i,j = random.choice(possible_matches)
            base_row = pw["row"]
            base_col = pw["col"]
            if pw["dir"] == "across":
                target_row = base_row - j
                target_col = base_col + i
                if 0 <= target_row and target_row + len(w) <= size and 0 <= target_col < size:
                    ok = True
                    for k,ch in enumerate(w):
                        cur = grid[target_row + k][target_col]
                        if cur not in ("", ch):
                            ok = False
                            break
                    if ok:
                        for k,ch in enumerate(w):
                            grid[target_row + k][target_col] = ch
                        placed.append({"word": w, "row": target_row, "col": target_col, "dir": "down"})
                        placed_flag = True
                        break
            else:
                target_row = base_row + i
                target_col = base_col - j
                if 0 <= target_col and target_col + len(w) <= size and 0 <= target_row < size:
                    ok = True
                    for k,ch in enumerate(w):
                        cur = grid[target_row][target_col + k]
                        if cur not in ("", ch):
                            ok = False
                            break
                    if ok:
                        for k,ch in enumerate(w):
                            grid[target_row][target_col + k] = ch
                        placed.append({"word": w, "row": target_row, "col": target_col, "dir": "across"})
                        placed_flag = True
                        break
        if not placed_flag:
            for _ in range(200):
                rr = random.randrange(size)
                cc = random.randrange(size)
                dirc = random.choice(["across","down"])
                if place_word(grid,w,rr,cc,dirc):
                    placed.append({"word": w, "row": rr, "col": cc, "dir": dirc})
                    placed_flag = True
                    break
        if not placed_flag:
            unused.append(w)

    for r in range(size):
        for c in range(size):
            if grid[r][c] == "":
                grid[r][c] = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    grid_lines = ["".join(row) for row in grid]
    return {"grid": grid_lines, "placed": placed, "unused": unused}

def build_crossword_from_text(extracted_text: str, num_words:int = 10, grid_size:int=15):
    pairs = ask_gemini_for_words_and_clues(extracted_text, num_words=num_words)
    if not pairs or len(pairs) < min(3, num_words):
        words = []
        import re
        toks = re.findall(r'\b[A-Za-z]{4,}\b', extracted_text)
        freq = {}
        for t in toks:
            tt = t.upper()
            freq[tt] = freq.get(tt,0)+1
        words_sorted = sorted(freq.items(), key=lambda x:-x[1])
        for w,_ in words_sorted[:num_words]:
            words.append((w, "Definition not available"))
        pairs = [(w,c) for w,c in pairs] + [(w,"Definition not available") for w in words if (w, "Definition not available") not in pairs]
        pairs = pairs[:num_words]

    words = [w for w,c in pairs]
    clues = {w: c for w,c in pairs}
    placement = try_place_words(words, size=grid_size)
    result = {
        "words": words,
        "clues": clues,
        "grid": placement["grid"],
        "placed": placement["placed"],
        "unused": placement["unused"],
        "size": grid_size
    }
    return result

def grade_crossword_submission(solution_grid_lines: List[str], student_grid_lines: List[str]) -> Dict:
    rows = len(solution_grid_lines)
    cols = len(solution_grid_lines[0]) if rows>0 else 0
    total = rows * cols
    correct = 0
    for r in range(rows):
        sol_row = solution_grid_lines[r]
        stu_row = student_grid_lines[r] if r < len(student_grid_lines) else ""
        for c in range(cols):
            sol_ch = sol_row[c] if c < len(sol_row) else ""
            stu_ch = stu_row[c] if c < len(stu_row) else ""
            if sol_ch.upper() == (stu_ch or "").upper():
                correct += 1
    score = correct / total if total>0 else 0.0
    return {"total_cells": total, "correct_cells": correct, "score_fraction": score}
