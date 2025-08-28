# Quick Diff with JSONL export (Steps 1 & 2)
# - Compare two texts/files using difflib
# - Compute similarity metrics
# - Produce a structured diff record (schema) with hunks + heuristics
# - Save/append to JSONL and/or download JSON
#
# No extra dependencies.

import difflib, json, re, time, uuid
import streamlit as st
import streamlit.components.v1 as components
from typing import List, Dict, Any

def render_about_sidebar():
    about_html = """
    <style>
      .about-box{
        background: #0f172a0d; /* subtle slate tint */
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 14px 14px 6px 14px;
        font-size: 0.94rem;
        line-height: 1.35rem;
      }
      .about-box h2{
        font-size: 1.05rem; margin: 0 0 8px 0; font-weight: 700;
      }
      .about-box h3{
        font-size: 0.98rem; margin: 14px 0 6px 0; font-weight: 700;
      }
      .pill{
        display:inline-block; padding:2px 8px; border-radius:999px;
        background:#eef2ff; color:#3730a3; font-size:0.75rem; margin-right:6px;
        border:1px solid #c7d2fe;
      }
      .code{
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:2px 6px;
      }
      ul{margin:6px 0 6px 20px;}
      li{margin:4px 0;}
      .dim{color:#475569; font-size:0.85rem;}
      .kv{margin:0 0 2px 0}
      .kv b{display:inline-block; min-width:122px;}
      .note{background:#fff7ed; border:1px solid #fed7aa; padding:8px 10px; border-radius:8px; font-size:0.88rem;}
    </style>

    <div class="about-box">
      <h2>🔎 About: Quick Diff → JSONL</h2>
      <span class="pill">difflib</span>
      <span class="pill">Unified Diff</span>
      <span class="pill">HTML Side-by-Side</span>
      <span class="pill">LLM-ready JSON</span>

      <p>
        Compare two texts/files, see diffs, compute similarity scores, and export a structured
        <span class="code">JSON</span> record (or append to <span class="code">JSONL</span>) for LLM review.
      </p>

      <h3>What you get</h3>
      <ul>
        <li><b>Unified diff</b> (like <span class="code">git diff</span>)</li>
        <li><b>HTML side-by-side</b> diff for visual review</li>
        <li><b>Similarity metrics</b> (character, line, token)</li>
        <li><b>LLM-ready JSON record</b> with <span class="code">stats</span>, <span class="code">unified_diff</span>, <span class="code">hunks</span>, <span class="code">heuristics</span></li>
      </ul>

      <h3>Parameters (your selections)</h3>
      <ul>
        <li class="kv"><b>Input mode:</b> <i>Paste text</i> or <i>Upload files</i>. Choose how you provide the two versions.</li>
        <li class="kv"><b>Context lines:</b> Number of unchanged lines shown around each change in the unified diff.</li>
        <li class="kv"><b>Ignore whitespace:</b> If enabled, trims leading/trailing spaces per line before computing diffs (reduces noise).</li>
        <li class="kv"><b>JSONL output path:</b> Where each change record is appended (one JSON object per line).</li>
        <li class="kv"><b>Download options:</b> Save the HTML diff and/or the single JSON record locally.</li>
      </ul>

      <div class="note">
        <b>Tip:</b> If your app includes input limits (e.g., max characters/lines), oversized pastes/uploads may be blocked or truncated.
      </div>

      <h3>Metrics (how they’re calculated)</h3>
      <ul>
        <li><b>Character similarity</b><br/>
          Uses <span class="code">difflib.SequenceMatcher(a, b).ratio()</span> over raw strings.<br/>
          Returns a value in <span class="code">[0,1]</span>. We also show <b>% different</b> ≈ <span class="code">(1 − similarity) × 100</span>.
        </li>
        <li><b>Line similarity</b><br/>
          Runs <span class="code">SequenceMatcher</span> on <span class="code">a.splitlines()</span> vs <span class="code">b.splitlines()</span> (line is the unit).<br/>
          More tolerant of within-line edits, but any line-level change still counts as different.
        </li>
        <li><b>Token (Jaccard) similarity</b><br/>
          Extracts unique lowercase word tokens via <span class="code">re.findall(r"\\w+")</span> and computes<br/>
          <span class="code">|A ∩ B| / |A ∪ B|</span>. Ignores order and frequency; measures vocabulary overlap.
        </li>
      </ul>

      <h3>Heuristics (quick signals)</h3>
      <ul>
        <li>Flags deletions of <span class="code">try:</span>, <span class="code">assert</span>, or logging lines</li>
        <li>Detects numeric assignment changes (e.g., <span class="code">max_retries = 5 → 2</span>) and direction</li>
        <li>Notes added/removed sensitive tokens like <span class="code">password</span></li>
      </ul>

      <h3>Workflow</h3>
      <ul>
        <li>Choose input mode → provide both versions</li>
        <li>Adjust parameters (context / whitespace)</li>
        <li>Compare to view diffs & scores</li>
        <li>Review the JSON record → Append to JSONL or download</li>
      </ul>

      <p class="dim">No data leaves this app unless you download or append. Use JSONL to accumulate a dataset for LLM-based review later.</p>
    </div>
    """
    import streamlit as st
    with st.sidebar:
        st.markdown(about_html, unsafe_allow_html=True)





# ------------------ Utilities: metrics, diff, parsing, heuristics ------------------

def similarity_scores(a: str, b: str):
    sm_char = difflib.SequenceMatcher(None, a, b, autojunk=True).ratio()
    sm_line = difflib.SequenceMatcher(None, a.splitlines(), b.splitlines(), autojunk=True).ratio()
    toks_a = set(re.findall(r"\w+", a.lower()))
    toks_b = set(re.findall(r"\w+", b.lower()))
    jacc = (len(toks_a & toks_b) / len(toks_a | toks_b)) if (toks_a or toks_b) else 1.0
    return sm_char, sm_line, jacc

def to_lines(s: str, strip_ws: bool) -> List[str]:
    if strip_ws:
        return [line.strip() + "\n" for line in s.splitlines()]
    return [line + ("\n" if not line.endswith("\n") else "") for line in s.splitlines()]

def unified_diff_text(left_lines: List[str], right_lines: List[str], left_name: str, right_name: str, n_context: int = 3) -> str:
    return "\n".join(difflib.unified_diff(
        left_lines, right_lines, fromfile=left_name, tofile=right_name, n=n_context, lineterm=""
    )) or "(no differences)"

def html_side_by_side(left_lines: List[str], right_lines: List[str], left_name: str, right_name: str) -> str:
    # HtmlDiff builds a full HTML document
    _ = difflib.SequenceMatcher(None, "".join(left_lines), "".join(right_lines), autojunk=True)
    return difflib.HtmlDiff(wrapcolumn=80).make_file(left_lines, right_lines, left_name, right_name)

def parse_unified_diff(unified: str) -> List[Dict[str, Any]]:
    """
    Minimal unified diff parser → hunks with ops (del/add/ctx).
    """
    hunks = []
    lines = unified.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("@@ "):
            m = re.match(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@", line)
            if not m:
                i += 1
                continue
            old_start = int(m.group(1))
            old_len = int(m.group(2) or "1")
            new_start = int(m.group(3))
            new_len = int(m.group(4) or "1")
            i += 1
            ops = []
            old_buf, new_buf = [], []
            while i < len(lines) and not lines[i].startswith("@@ "):
                l = lines[i]
                if l.startswith('-'):
                    ops.append({"op": "del", "text": l[1:]})
                    old_buf.append(l[1:])
                elif l.startswith('+'):
                    ops.append({"op": "add", "text": l[1:]})
                    new_buf.append(l[1:])
                elif l.startswith(' '):
                    ops.append({"op": "ctx", "text": l[1:]})
                    old_buf.append(l[1:]); new_buf.append(l[1:])
                elif l.startswith("\\ No newline at end of file"):
                    pass
                i += 1
                if i >= len(lines) or (i < len(lines) and lines[i].startswith("@@ ")):
                    break
            hunks.append({
                "old_start": old_start, "old_len": old_len,
                "new_start": new_start, "new_len": new_len,
                "ops": ops,
                "old_snippet": "\n".join(old_buf),
                "new_snippet": "\n".join(new_buf),
            })
        else:
            i += 1
    return hunks

_NUMERIC_ASSIGN_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(-?\d+(\.\d+)?)\s*(#.*)?$")

def simple_heuristics(hunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    risk_flags = []
    numeric_changes = []
    removed_keywords, added_keywords = [], []

    for h in hunks:
        for op in h["ops"]:
            t = op["text"]
            if op["op"] == "del" and "try:" in t:
                risk_flags.append("removed_try_block")
            if op["op"] == "del" and "assert " in t:
                risk_flags.append("removed_assert")
            if op["op"] == "del" and re.search(r"\blog\b|\blogger\b", t):
                risk_flags.append("removed_logging")
            if op["op"] == "add" and re.search(r"\btodo\b|\bfixme\b", t.lower()):
                risk_flags.append("todo_added")

        # numeric parameter changes: foo = 5 → foo = 2
        dels = [op["text"] for op in h["ops"] if op["op"] == "del"]
        adds = [op["text"] for op in h["ops"] if op["op"] == "add"]
        for d in dels:
            md = _NUMERIC_ASSIGN_RE.match(d)
            if md:
                key, old_val = md.group(1), float(md.group(2))
                for a in adds:
                    ma = _NUMERIC_ASSIGN_RE.match(a)
                    if ma and ma.group(1) == key:
                        new_val = float(ma.group(2))
                        numeric_changes.append({"key": key, "old": old_val, "new": new_val})
                        if new_val < old_val:
                            risk_flags.append(f"reduced_{key}")
                        elif new_val > old_val:
                            risk_flags.append(f"increased_{key}")

        removed_keywords += [op["text"] for op in h["ops"] if op["op"] == "del" and "password" in op["text"].lower()]
        added_keywords   += [op["text"] for op in h["ops"] if op["op"] == "add" and "password" in op["text"].lower()]

    return {
        "risk_flags": sorted(set(risk_flags)),
        "numeric_changes": numeric_changes,
        "removed_keywords": removed_keywords,
        "added_keywords": added_keywords
    }

def make_change_record(left_text: str, right_text: str, left_name="left.txt", right_name="right.txt", n_context=3, strip_ws=False):
    left_lines  = to_lines(left_text, strip_ws)
    right_lines = to_lines(right_text, strip_ws)

    uni = unified_diff_text(left_lines, right_lines, left_name, right_name, n_context=n_context)
    hunks = parse_unified_diff(uni)
    sm_char, sm_line, jacc = similarity_scores(left_text, right_text)

    rec = {
        "id": f"{time.strftime('%Y-%m-%dT%H:%M:%SZ')}_{uuid.uuid4().hex[:6]}",
        "source": {"left_name": left_name, "right_name": right_name},
        "stats": {
            "lines_left": len(left_lines), "lines_right": len(right_lines),
            "char_similarity": round(sm_char, 4),
            "line_similarity": round(sm_line, 4),
            "token_jaccard": round(jacc, 4),
            "percent_different_estimate": round((1 - sm_char) * 100, 2)
        },
        "unified_diff": uni,
        "hunks": hunks,
        "heuristics": simple_heuristics(hunks),
    }
    return rec

def save_jsonl(records: List[Dict[str, Any]], path: str):
    with open(path, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

# ------------------ Streamlit UI ------------------

st.set_page_config(page_title="Quick Diff + JSONL", layout="wide")
render_about_sidebar()
st.title("🔍 Quick Diff → JSONL (LLM-ready)")

mode = st.radio("Input mode", ["Paste text", "Upload files"], horizontal=True)

def read_bytes_as_text(b: bytes) -> str:
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode("utf-8", errors="ignore")

# inputs
left_text = right_text = ""
left_name, right_name = "left.txt", "right.txt"

if mode == "Paste text":
    # Prefill samples
    sample_left = (
        'def greet(name):\n'
        '    print("Hello " + name)\n'
        '\n'
        'greet("Alice")\n'
    )
    sample_right = (
        'def greet(name, time_of_day="morning"):\n'
        '    print(f"Good {time_of_day}, {name}!")\n'
        '\n'
        'greet("Alice", "evening")\n'
    )
    c1, c2 = st.columns(2)
    with c1:
        left_text = st.text_area("Left (original)", value=sample_left, height=260)
    with c2:
        right_text = st.text_area("Right (modified)", value=sample_right, height=260)
else:
    c1, c2 = st.columns(2)
    with c1:
        left_file = st.file_uploader("Left file (original)", type=None, key="left")
    with c2:
        right_file = st.file_uploader("Right file (modified)", type=None, key="right")
    if left_file:
        left_text = read_bytes_as_text(left_file.read())
        left_name = left_file.name
    if right_file:
        right_text = read_bytes_as_text(right_file.read())
        right_name = right_file.name

with st.expander("Diff options", expanded=False):
    n_context = st.slider("Context lines (for unified diff)", 0, 10, 3)
    strip_ws = st.checkbox("Ignore leading/trailing whitespace", value=False)

go = st.button("Compare & Build JSON", type="primary")

if go:
    if not left_text or not right_text:
        st.warning("Please provide text on both sides (or upload two files) before comparing.")
    else:
        # Metrics
        sm_char, sm_line, jacc = similarity_scores(left_text, right_text)
        colA, colB, colC = st.columns(3)
        with colA:
            st.metric("Character similarity", f"{sm_char*100:.2f}%", delta=f"-{(1-sm_char)*100:.2f}% different")
        with colB:
            st.metric("Line similarity", f"{sm_line*100:.2f}%", delta=f"-{(1-sm_line)*100:.2f}% different")
        with colC:
            st.metric("Token (Jaccard) similarity", f"{jacc*100:.2f}%", delta=f"-{(1-jacc)*100:.2f}% different")

        # Unified diff + HTML
        left_lines  = to_lines(left_text, strip_ws)
        right_lines = to_lines(right_text, strip_ws)
        st.subheader("📄 Unified diff")
        uni = unified_diff_text(left_lines, right_lines, left_name, right_name, n_context=n_context)
        st.code(uni, language="diff")

        st.subheader("🪞 Side-by-side HTML diff")
        html = html_side_by_side(left_lines, right_lines, left_name, right_name)
        components.html(html, height=500, scrolling=True)
        st.download_button("Download HTML diff", data=html.encode("utf-8"), file_name="diff_report.html", mime="text/html")

        # Build record (Step 1) and show JSON preview
        st.subheader("🧾 LLM-ready change record (JSON)")
        rec = make_change_record(left_text, right_text, left_name, right_name, n_context=n_context, strip_ws=strip_ws)
        pretty = json.dumps(rec, indent=2, ensure_ascii=False)
        st.code(pretty, language="json")

        # Save/append to JSONL (Step 2)
        st.subheader("💾 Save as JSONL")
        col1, col2 = st.columns([2,1])
        with col1:
            path = st.text_input("JSONL output path", value="changes.jsonl")
        with col2:
            append_now = st.button("Append to JSONL")
        if append_now:
            try:
                save_jsonl([rec], path)
                st.success(f"Appended record to {path}")
            except Exception as e:
                st.error(f"Failed to save JSONL: {e}")

        # Also allow downloading this single JSON record
        st.download_button(
            "Download this JSON record",
            data=pretty.encode("utf-8"),
            file_name=f"{rec['id']}.json",
            mime="application/json",
            use_container_width=True
        )

# Small tip
st.caption("Tip: Append multiple comparisons into one JSONL file (one JSON object per line) to build a review dataset.")
