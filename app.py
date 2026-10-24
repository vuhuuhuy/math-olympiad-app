import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import altair as alt
import json
import time
import os
import re
import random
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Math Olympiad App", layout="wide")

# --- ANCHOR AT THE VERY TOP FOR AUTO-SCROLLING ---
st.markdown("<div id='top'></div>", unsafe_allow_html=True)

# --- GOOGLE APPS SCRIPT WEB APP URL ---
GOOGLE_SHEET_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbxv5mU7px4_bOP2N9nAJ9Mlx2a58W4TSxSNSIq-iIk9aEuDoZn2JQmMP6z_Kbw3M8KkJw/exec"

# --- LOCAL TIMEZONE (Kuala Lumpur, UTC+8) ---
LOCAL_TZ = timezone(timedelta(hours=8))

# --- CUSTOM CSS FOR COMPACT & CLEAN LAYOUT ---
st.markdown(
    """
    <style>
    /* Main container top padding */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 1rem !important;
    }

    /* Pull sidebar content up to the very top edge */
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 0.5rem !important;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 0.5rem !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] {
        gap: 0.4rem !important;
    }

    /* Global font size setting */
    html, body, [class*="css"] {
        font-size: 18px !important;
    }

    /* Standardize main page headings */
    h1 {
        font-size: 22px !important;
        font-weight: 700 !important;
        margin-top: 0px !important;
        margin-bottom: 8px !important;
        padding-top: 0px !important;
    }

    /* Standardize subheaders (h3) */
    h3 {
        font-size: 20px !important;
        font-weight: 700 !important;
    }

    /* Make text input box ~15% taller */
    div[data-testid="stTextInput"] input {
        padding-top: 8px !important;
        padding-bottom: 8px !important;
        min-height: 44px !important;
        font-size: 18px !important;
    }

    /* Space below text input box */
    div[data-testid="stTextInput"] {
        margin-bottom: 8px !important;
    }

    /* Set multiple choice options to 18px with matching weight */
    div.stRadio label p {
        font-size: 18px !important;
        font-weight: 400 !important;
    }
    
    /* Increase math formulas size */
    .katex {
        font-size: 1.3em !important;
    }

    /* Display options A, B, C, D, E horizontally */
    div[role="radiogroup"] {
        display: flex;
        flex-direction: row;
        gap: 25px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- HELPER FUNCTION: RELIABLE ANCHOR SCROLL TO TOP ---
def scroll_to_top():
    components.html(
        """
        <script>
            try {
                window.parent.location.href = "#top";
            } catch (e) {
                console.log(e);
            }
        </script>
        """,
        height=0
    )

# --- HELPER FUNCTION: DYNAMIC IMAGE FINDER ---
def get_image_path(folder_name, q_id):
    if not folder_name:
        return None
    folder_path = os.path.join(BASE_DIR, "images", folder_name)
    if os.path.exists(folder_path):
        q_str = str(q_id)
        q_padded = f"{int(q_id):02d}" if q_str.isdigit() else q_str
        candidates = [f"q{q_str}", f"{q_str}", f"q{q_padded}", f"{q_padded}"]
        extensions = [".png", ".jpg", ".jpeg", ".webp"]
        for cand in candidates:
            for ext in extensions:
                p = os.path.join(folder_path, f"{cand}{ext}")
                if os.path.exists(p):
                    return p
    return None

# --- HELPER FUNCTION: GET COMPETITION FILES STRICTLY ---
def get_comp_files(comp_name):
    """Matches files strictly by removing non-alphanumeric characters."""
    clean_comp = re.sub(r'[^a-zA-Z0-9]', '', comp_name.lower())
    files = []
    if os.path.exists(BASE_DIR):
        for f in os.listdir(BASE_DIR):
            if f.endswith(".json") and f != "users.json":
                clean_f = re.sub(r'[^a-zA-Z0-9]', '', f.lower().replace(".json", ""))
                if clean_f.startswith(clean_comp):
                    files.append(f)
    return sorted(files, reverse=True)

# --- ROBUST API SESSION FOR SCORE LOGGING ONLY ---
def get_api_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

# --- AUTHENTICATION: READS USERS LOCALLY FROM USERS.JSON ---
def get_registered_emails():
    users_file = os.path.join(BASE_DIR, "users.json")
    if os.path.exists(users_file):
        try:
            with open(users_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                emails = []
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, str):
                            emails.append(item.strip().lower())
                        elif isinstance(item, dict):
                            for k in item.keys():
                                if "@" in str(k):
                                    emails.append(str(k).strip().lower())
                elif isinstance(data, dict):
                    for k in data.keys():
                        if "@" in str(k):
                            emails.append(str(k).strip().lower())
                return [e for e in emails if e]
        except Exception as e:
            print("Error reading users.json:", e)
    return []

def log_result_to_sheets(test_type, score_str, user_email, duration_str="N/A"):
    if not GOOGLE_SHEET_WEB_APP_URL or "DÁN_URL" in GOOGLE_SHEET_WEB_APP_URL:
        return
    now_local = datetime.now(LOCAL_TZ)
    payload = {
        "action": "log_score",
        "date": now_local.strftime("%Y-%m-%d %H:%M:%S"),
        "email": user_email,
        "type": test_type,
        "results": score_str,
        "duration": duration_str
    }
    session = get_api_session()
    try:
        session.post(GOOGLE_SHEET_WEB_APP_URL, json=payload, timeout=30)
    except Exception as e:
        print("Error logging score:", e)

def fetch_user_history(user_email):
    if not GOOGLE_SHEET_WEB_APP_URL or "DÁN_URL" in GOOGLE_SHEET_WEB_APP_URL:
        return []
    session = get_api_session()
    try:
        response = session.get(f"{GOOGLE_SHEET_WEB_APP_URL}?type=history", timeout=30)
        if response.status_code == 200:
            all_data = response.json()
            if isinstance(all_data, dict):
                all_data = all_data.get("data") or all_data.get("history") or all_data.get("results") or []

            filtered = []
            if isinstance(all_data, list):
                for row in all_data:
                    if isinstance(row, dict):
                        row_email = str(row.get("email") or row.get("Email") or row.get("EMAIL") or "").strip().lower()
                        if row_email == user_email.strip().lower():
                            filtered.append(row)
                    elif isinstance(row, list) and len(row) >= 4:
                        row_email = str(row[1]).strip().lower()
                        if row_email == user_email.strip().lower():
                            filtered.append({
                                "date": row[0],
                                "email": row[1],
                                "type": row[2],
                                "results": row[3],
                                "duration": row[4] if len(row) >= 5 else "N/A"
                            })
            return filtered
    except Exception as e:
        st.error(f"⚠️ Cloud connection error: {e}")
    return []

# --- SIDEBAR: TOP TIMER PLACEHOLDER ---
sidebar_timer_placeholder = st.sidebar.empty()

# --- CONTINUOUS LIVE TIMER FRAGMENT ---
@st.fragment(run_every="1s")
def render_mock_timer():
    if st.session_state.get("start_time") is not None and not st.session_state.get("submitted", False):
        time_elapsed = int(time.time() - st.session_state.start_time)
        time_left = max(0, 2400 - time_elapsed)
        mins, secs = divmod(time_left, 60)
        
        sidebar_timer_placeholder.markdown(
            f"""
            <div style='background-color: #f8f9fa; border: 1px solid #dcdfe6; padding: 8px 12px; border-radius: 8px; text-align: center; margin-top: 0px; margin-bottom: 20px;'>
                <div style='font-size: 15px; font-weight: 600; color: #262730; margin-bottom: 2px;'>⏱️ Time Remaining</div>
                <div style='font-size: 34px; font-weight: 800; color: #d9534f; line-height: 1.1;'>{mins:02d}:{secs:02d}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        if time_left == 0:
            st.session_state.submitted = True
            st.rerun()

# --- SIDEBAR HEADER & EMAIL VALIDATION ---
st.sidebar.markdown(
    """
    <div style='text-align: center; margin-bottom: 8px;'>
        <div style='font-size: 28px; line-height: 1.0;'>🏆</div>
        <div style='font-size: 20px; font-weight: 700; color: #262730; margin-top: 2px;'>Math Olympiad App</div>
    </div>
    """,
    unsafe_allow_html=True
)

saved_email = st.query_params.get("email", "").strip().lower()
user_email = st.sidebar.text_input("📧 Enter your Gmail:", value=saved_email).strip().lower()

if user_email and user_email.endswith("@gmail.com"):
    st.query_params["email"] = user_email

valid_access = False

if user_email:
    if not user_email.endswith("@gmail.com"):
        st.sidebar.error("⚠️ Only valid @gmail.com addresses are allowed!")
    else:
        registered_list = get_registered_emails()
        if user_email in registered_list:
            valid_access = True
            st.sidebar.markdown(
                """
                <div style='background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; padding: 8px 12px; border-radius: 8px; font-size: 18px; font-weight: 600; min-height: 44px; display: flex; align-items: center; margin-bottom: 8px;'>
                    ✅ Verified User
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            st.sidebar.error("❌ Access Denied: Email not registered in users.json!")
            st.sidebar.info("Please ask the administrator to add your email to users.json on GitHub.")

st.sidebar.markdown("---")

# ==========================================
# 1. SELECT COMPETITION
# ==========================================
st.sidebar.markdown("### 1. Select Competition")
selected_competition = st.sidebar.selectbox(
    "Choose Competition:",
    ["AMC8", "SASMO6", "SASMO7", "Kangaroo"],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")

# ==========================================
# 2. SELECT MODE & SUB-OPTIONS
# ==========================================
st.sidebar.markdown("### 2. Select Mode")
app_mode = st.sidebar.radio(
    "Choose Mode:",
    ["🎲 Practice", "📝 Mock Test", "📊 My History"],
    label_visibility="collapsed"
)

num_q_select = 10
selected_file = None

# RESET PRACTICE SESSION WHEN COMPETITION IS CHANGED
if "current_comp" not in st.session_state or st.session_state.current_comp != selected_competition:
    st.session_state.current_comp = selected_competition
    st.session_state.practice_questions = []
    st.session_state.practice_submitted = False
    st.session_state.practice_answers = {}
    st.session_state.logged_practice = False

if app_mode == "🎲 Practice":
    st.sidebar.markdown("**Select number of questions:**")
    num_q_select = st.sidebar.slider(
        "Questions Count:", 
        min_value=5, 
        max_value=25, 
        value=10, 
        step=1, 
        label_visibility="collapsed"
    )

elif app_mode == "📝 Mock Test":
    test_files = get_comp_files(selected_competition)
    st.sidebar.markdown("**Select test paper:**")
    if test_files:
        selected_file = st.sidebar.selectbox("Test Paper:", test_files, label_visibility="collapsed")
    else:
        st.sidebar.warning(f"No test papers found for {selected_competition}.")

if app_mode != "📝 Mock Test" or st.session_state.get("submitted", False):
    sidebar_timer_placeholder.empty()

# --- SECURITY GATE: STOP APP IF NOT VALID ---
if not valid_access:
    st.title("🔒 Access Restricted")
    st.warning("Please enter a valid, **registered @gmail.com** address in the sidebar and verify your access to use the Math Olympiad App.")
    st.stop()

# ==========================================
# MAIN APP BODY
# ==========================================

# --- INSPIRATIONAL BANNER ---
st.markdown(
    f"""
    <div style='background-color: #e3f2fd; padding: 12px 16px; border-radius: 8px; border-left: 5px solid #2196F3; margin-bottom: 10px; overflow: hidden;'>
        <p style='color: #0d47a1; font-size: 16px; font-weight: 600; margin: 0; text-align: center;'>
            🚀 Welcome ({user_email}) to Math Olympiad App. Keep exploring, keep growing! 🌟
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div style='text-align: right; color: gray; font-size: 12px; margin-top: -6px; margin-bottom: 8px;'>
        <em>Created by Vu Huu Huy for family & friends learning</em>
    </div>
    """,
    unsafe_allow_html=True
)

# ==========================================
# PRACTICE MODE
# ==========================================
if app_mode == "🎲 Practice":
    st.title(f"🎲 Practice Session — {selected_competition}")
    comp_files = get_comp_files(selected_competition)

    if not comp_files:
        st.warning(f"No question datasets available for **{selected_competition}**.")
    else:
        if "practice_questions" not in st.session_state:
            st.session_state.practice_questions = []
        if "practice_submitted" not in st.session_state:
            st.session_state.practice_submitted = False
        if "practice_answers" not in st.session_state:
            st.session_state.practice_answers = {}
        if "logged_practice" not in st.session_state:
            st.session_state.logged_practice = False
        if "practice_start_time" not in st.session_state:
            st.session_state.practice_start_time = time.time()

        generate_clicked = st.sidebar.button("🔀 Reshuffle Practice Set", type="primary")
        
        if generate_clicked or not st.session_state.practice_questions or len(st.session_state.practice_questions) != num_q_select:
            pooled_questions = []
            for file in comp_files:
                file_path = os.path.join(BASE_DIR, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for item in data:
                            item["source_file"] = file
                            pooled_questions.append(item)
                except Exception:
                    pass

            if pooled_questions:
                sample_size = min(num_q_select, len(pooled_questions))
                st.session_state.practice_questions = random.sample(pooled_questions, sample_size)
                st.session_state.practice_submitted = False
                st.session_state.practice_answers = {}
                st.session_state.logged_practice = False
                st.session_state.practice_start_time = time.time()
                if generate_clicked:
                    st.rerun()

        if st.session_state.practice_questions:
            questions = st.session_state.practice_questions

            if not st.session_state.practice_submitted:
                col_sub1, _ = st.columns([2, 6])
                with col_sub1:
                    if st.button("📤 Submit Practice Set (Top)", type="primary", use_container_width=True, key="top_submit_practice"):
                        st.session_state.practice_submitted = True
                        st.rerun()
                st.markdown("---")

            if st.session_state.practice_submitted:
                scroll_to_top()
                
                score = sum(
                    1 for idx, q in enumerate(questions)
                    if st.session_state.practice_answers.get(idx) == q["answer"]
                )
                total = len(questions)

                pct = (score / total) * 100 if total > 0 else 0.0
                elapsed_secs = int(time.time() - st.session_state.practice_start_time)
                m, s = divmod(elapsed_secs, 60)
                time_str = f"{m} min {s} secs" if m > 0 else f"{s} secs"

                if not st.session_state.logged_practice:
                    log_result_to_sheets(f"Practice Mode - {selected_competition}", f"{score}/{total}", user_email, time_str)
                    st.session_state.logged_practice = True

                st.markdown(
                    f"""
                    <div style='background-color: #d4edda; color: #155724; padding: 12px 16px; border-radius: 8px; border-left: 5px solid #28a745; margin-bottom: 12px; overflow: hidden;'>
                        <h3 style='margin: 0; color: #155724; font-size: 20px; font-weight: 700;'>🎯 Practice Set Submitted Successfully!</h3>
                        <p style='margin: 4px 0 0 0; font-size: 18px; font-weight: 600;'>
                            Your Score: <span style='color: #0b2e13; font-size: 19px;'>{score}/{total} ({pct:.1f}%)</span> correct answers in <strong>{time_str}</strong>.
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                if st.button("🔄 Start New Practice Session"):
                    st.session_state.practice_questions = []
                    st.session_state.practice_submitted = False
                    st.session_state.practice_answers = {}
                    st.session_state.logged_practice = False
                    st.session_state.practice_start_time = time.time()
                    st.rerun()

                st.markdown("### 📝 Detailed Review")
                for idx, q in enumerate(questions):
                    user_ans = st.session_state.practice_answers.get(idx)
                    user_ans_str = user_ans if user_ans is not None else "Not answered"
                    correct_ans = q["answer"]
                    q_id = q['id']
                    source_file = q.get("source_file", "")
                    folder_name = source_file.replace(".json", "") if source_file else ""
                    img_w = q.get("image_width", 300)

                    if user_ans == correct_ans:
                        st.markdown(f"✅ **Question {idx + 1}: Correct** (Your choice: {user_ans_str})")
                    else:
                        st.markdown(f"❌ **Question {idx + 1}: Incorrect** (Your choice: {user_ans_str} | Correct answer: **{correct_ans}**)")

                    with st.expander(f"View Solution for Question {idx + 1}"):
                        img_path = get_image_path(folder_name, q_id)
                        if img_path:
                            st.image(img_path, width=img_w)
                        st.write(q["explanation"])
                    st.markdown("---")

            else:
                for idx, q in enumerate(questions):
                    q_id = q['id']
                    source_file = q.get("source_file", "")
                    folder_name = source_file.replace(".json", "") if source_file else ""
                    img_w = q.get("image_width", 300)
                    
                    st.subheader(f"Question {idx + 1} (From {source_file})")
                    st.markdown(q["question"], unsafe_allow_html=True)
                    
                    img_path = get_image_path(folder_name, q_id)
                    if img_path:
                        st.image(img_path, width=img_w)

                    ans = st.radio(
                        f"Choose answer for Q{idx+1}:", 
                        q["options"], 
                        key=f"practice_{selected_competition}_{idx}_{q_id}", 
                        index=None,
                        label_visibility="collapsed"
                    )
                    st.session_state.practice_answers[idx] = ans
                    st.markdown("---")

                col_bot1, _ = st.columns([2, 6])
                with col_bot1:
                    if st.button("📤 Submit Practice Set (Bottom)", type="primary", use_container_width=True, key="bot_submit_practice"):
                        st.session_state.practice_submitted = True
                        st.rerun()
                st.markdown("---")

# ==========================================
# MOCK TEST MODE
# ==========================================
elif app_mode == "📝 Mock Test":
    st.title(f"✍️ Mock Test: {selected_competition}")

    if not selected_file:
        st.warning(f"No test papers available for **{selected_competition}**.")
    else:
        if "current_test_file" not in st.session_state:
            st.session_state.current_test_file = None
        if "start_time" not in st.session_state:
            st.session_state.start_time = None
        if "user_answers" not in st.session_state:
            st.session_state.user_answers = {}
        if "submitted" not in st.session_state:
            st.session_state.submitted = False
        if "logged_mock" not in st.session_state:
            st.session_state.logged_mock = False

        if st.session_state.current_test_file != selected_file or st.session_state.start_time is None:
            st.session_state.current_test_file = selected_file
            st.session_state.start_time = time.time()
            st.session_state.submitted = False
            st.session_state.user_answers = {}
            st.session_state.logged_mock = False

        file_path = os.path.join(BASE_DIR, selected_file)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                questions = json.load(f)
        except Exception as e:
            st.error(f"Error loading test file: {e}")
            questions = []

        year_match = re.search(r'\d{4}', selected_file)
        exam_year = year_match.group(0) if year_match else ""
        folder_name = selected_file.replace(".json", "")

        if questions:
            st.markdown("---")
            col_space1, col_submit, col_space2, col_retake = st.columns([4, 2, 2, 2])
            
            with col_submit:
                if not st.session_state.submitted:
                    if st.button("🔴 Submit Test (Top)", type="primary", use_container_width=True, key="top_submit_mock"):
                        st.session_state.submitted = True
                        st.rerun()
            
            with col_retake:
                if st.button("🔄 Restart Test", use_container_width=True, key="top_restart_mock"):
                    st.session_state.start_time = time.time()
                    st.session_state.submitted = False
                    st.session_state.user_answers = {}
                    st.session_state.logged_mock = False
                    st.rerun()
            st.markdown("---")

            if st.session_state.submitted:
                scroll_to_top()

                score = sum(
                    1 for q in questions
                    if st.session_state.user_answers.get(q['id']) == q["answer"]
                )
                total = len(questions)

                pct = (score / total) * 100 if total > 0 else 0.0
                elapsed_secs = int(time.time() - st.session_state.start_time)
                m, s = divmod(elapsed_secs, 60)
                time_str = f"{m} min {s} secs" if m > 0 else f"{s} secs"

                if not st.session_state.logged_mock:
                    log_result_to_sheets(f"Mock Test - {selected_competition} {exam_year}", f"{score}/{total}", user_email, time_str)
                    st.session_state.logged_mock = True

                st.markdown(
                    f"""
                    <div style='background-color: #d4edda; color: #155724; padding: 12px 16px; border-radius: 8px; border-left: 5px solid #28a745; margin-bottom: 12px; overflow: hidden;'>
                        <h3 style='margin: 0; color: #155724; font-size: 20px; font-weight: 700;'>🎉 Test Submitted Successfully!</h3>
                        <p style='margin: 4px 0 0 0; font-size: 18px; font-weight: 600;'>
                            Your Score: <span style='color: #0b2e13; font-size: 19px;'>{score}/{total} ({pct:.1f}%)</span> correct answers in <strong>{time_str}</strong>.
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                st.markdown("### 📝 Detailed Review & Solutions")
                for q in questions:
                    q_id = q['id']
                    user_ans = st.session_state.user_answers.get(q_id)
                    user_ans_str = user_ans if user_ans is not None else "Not answered"
                    correct_ans = q["answer"]
                    img_w = q.get("image_width", 300)
                    
                    if user_ans == correct_ans:
                        st.markdown(f"✅ **Question {q_id}: Correct** (Your choice: {user_ans_str})")
                    else:
                        st.markdown(f"❌ **Question {q_id}: Incorrect** (Your choice: {user_ans_str} | Correct answer: **{correct_ans}**)")
                    
                    with st.expander(f"View Solution for Question {q_id}"):
                        img_path = get_image_path(folder_name, q_id)
                        if img_path:
                            st.image(img_path, width=img_w)
                        st.write(q["explanation"])
                    st.markdown("---")

            else:
                render_mock_timer()

                for q in questions:
                    q_id = q['id']
                    img_w = q.get("image_width", 300)

                    st.subheader(f"Question {q_id}")
                    st.markdown(q["question"], unsafe_allow_html=True)
                    
                    img_path = get_image_path(folder_name, q_id)
                    if img_path:
                        st.image(img_path, width=img_w)
                    
                    ans = st.radio(
                        f"Choose your answer for Question {q_id}:", 
                        q["options"], 
                        key=f"q_{selected_file}_{q_id}", 
                        index=None,
                        label_visibility="collapsed"
                    )
                    st.session_state.user_answers[q_id] = ans
                    st.markdown("---")

                col_bspace, col_bsubmit, col_bspace2 = st.columns([4, 2, 4])
                with col_bsubmit:
                    if st.button("🔴 Submit Test (Bottom)", type="primary", use_container_width=True, key="bot_submit_mock"):
                        st.session_state.submitted = True
                        st.rerun()
                st.markdown("---")

# ==========================================
# 3. MY HISTORY TAB
# ==========================================
elif app_mode == "📊 My History":
    st.title("📊 Your Performance History")
    st.write(f"Showing practice and test history for email: **{user_email}**")
    
    with st.spinner("Fetching your history from Google Sheets..."):
        history = fetch_user_history(user_email)

    if history:
        st.success(f"Found {len(history)} recorded session(s)!")
        table_data = []
        chart_data = []

        for h in history:
            raw_date = str(h.get("date") or h.get("Date") or h.get("timestamp") or "").strip()
            raw_score = str(h.get("results") or h.get("Results") or h.get("score") or "").strip()
            raw_type = str(h.get("type") or h.get("Type") or "").strip()
            raw_duration = str(h.get("duration") or h.get("Duration") or h.get("Attempt duration") or "N/A").strip()
            if not raw_duration:
                raw_duration = "N/A"

            if "T" in raw_score or ("-" in raw_score and ":" in raw_score):
                try:
                    clean_ts = raw_score.replace("Z", "").split(".")[0]
                    dt_score = datetime.fromisoformat(clean_ts)
                    if dt_score.hour >= 12:
                        dt_score += timedelta(hours=12)
                    raw_score = f"{dt_score.month}/{dt_score.day}"
                except Exception:
                    pass

            formatted_date = raw_date
            if raw_date:
                try:
                    clean_str = raw_date.split(".")[0].replace("Z", "")
                    if "T" in clean_str:
                        dt = datetime.fromisoformat(clean_str)
                    else:
                        dt = datetime.strptime(clean_str, "%Y-%m-%d %H:%M:%S")
                    
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
                    else:
                        dt = dt.astimezone(LOCAL_TZ)
                        
                    formatted_date = dt.strftime("%d-%m-%y %H:%M")
                except Exception:
                    formatted_date = raw_date

            percentage_str = "N/A"
            pct_number = None
            if "/" in raw_score:
                try:
                    parts = raw_score.split("/")
                    correct = float(parts[0])
                    total = float(parts[1])
                    if total > 0:
                        pct_number = (correct / total) * 100
                        percentage_str = f"{pct_number:.1f}%"
                except Exception:
                    pass

            table_data.append({
                "Date & Time": formatted_date if formatted_date else "N/A",
                "Mode / Test Paper": raw_type if raw_type else "Practice Mode",
                "Score": raw_score if raw_score else "N/A",
                "Accuracy (%)": percentage_str,
                "Attempt duration": raw_duration
            })

            if pct_number is not None and formatted_date:
                chart_data.append({
                    "Date & Time": formatted_date,
                    "Accuracy (%)": round(pct_number, 1)
                })

        if chart_data:
            st.subheader("📈 Progress Trend Over Time")
            df_chart = pd.DataFrame(chart_data)
            
            chart = alt.Chart(df_chart).mark_line(point=alt.OverlayMarkDef(size=60, filled=True, color='blue')).encode(
                x=alt.X('Date & Time:N', sort=None, title='Date & Time',
                        axis=alt.Axis(labelAngle=-30, labelFontSize=13, titleFontSize=14)),
                y=alt.Y('Accuracy (%):Q', scale=alt.Scale(domain=[0, 100]), title='Accuracy (%)',
                        axis=alt.Axis(labelFontSize=13, titleFontSize=14)),
                tooltip=['Date & Time', 'Accuracy (%)']
            ).properties(height=350)
            
            st.altair_chart(chart, use_container_width=True)

        st.subheader("📋 Session Records")
        st.table(table_data)
    else:
        st.info("No history found for this email yet. Complete a test and click Submit to record your progress over time!")