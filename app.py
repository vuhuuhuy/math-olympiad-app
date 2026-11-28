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

# --- OFFICIAL COMPETITION DATES ---
COMPETITION_SCHEDULE = {
    "AMC8": "29 Jan 2027",
    "SASMO6": "Apr 2027",
    "SASMO7": "Apr 2027",
    "Kangaroo": "Apr 2027"
}

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

    /* Set multiple choice options to 18px with matching weight and comfortable line height */
    div.stRadio label {
        align-items: center !important;
        margin-top: 4px !important;
        margin-bottom: 6px !important;
    }
    div.stRadio label p {
        font-size: 18px !important;
        font-weight: 400 !important;
        line-height: 2.2 !important;
    }
    
    /* Increase math formulas size */
    .katex {
        font-size: 1.3em !important;
    }

    /* Display options A, B, C, D, E horizontally with line wrapping and relaxed gap */
    section.main div[role="radiogroup"] {
        display: flex;
        flex-direction: row;
        flex-wrap: wrap;
        gap: 16px 28px !important;
    }

    /* Keep sidebar radio buttons vertically stacked */
    section[data-testid="stSidebar"] div[role="radiogroup"] {
        display: flex;
        flex-direction: column !important;
        gap: 6px !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- CACHED DATASET LOADER (AUTO-INVALIDATES ON FILE UPDATE) ---
@st.cache_data
def _load_dataset_json_cached(file_path, mtime):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
    return []

def load_dataset_json(file_path):
    if os.path.exists(file_path):
        mtime = os.path.getmtime(file_path)
        return _load_dataset_json_cached(file_path, mtime)
    return []

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
        q_str = str(q_id).strip()
        q_padded = f"{int(q_str):02d}" if q_str.isdigit() else q_str
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
@st.cache_data(ttl=10)
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

# --- STUDENT TOPIC MASTERY & PROGRESS TRACKING ---
PROGRESS_FILE = os.path.join(BASE_DIR, "student_progress.json")

def load_student_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading student progress: {e}")
    return {}

def save_student_progress(data):
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving student progress: {e}")

def record_question_attempts(user_email, attempts):
    if not user_email or not attempts:
        return
    data = load_student_progress()
    email_key = user_email.strip().lower()
    if email_key not in data:
        data[email_key] = []
    data[email_key].extend(attempts)
    save_student_progress(data)

def get_topic_analytics(user_email):
    STANDARD_CATEGORIES = [
        ("Algebra & Word Problems", "📊"),
        ("Geometry & Spatial", "📐"),
        ("Number Theory & Arithmetic", "🔢"),
        ("Counting & Probability", "🎲"),
        ("Logic & Patterns", "🧩")
    ]
    data = load_student_progress()
    email_key = user_email.strip().lower() if user_email else ""
    user_attempts = data.get(email_key, [])
    
    cat_stats = {}
    for name, icon in STANDARD_CATEGORIES:
        cat_stats[name] = {
            "name": name,
            "icon": icon,
            "attempted": 0,
            "correct": 0,
            "hint_correct": 0,
            "total_score": 0.0,
            "accuracy": 0.0,
            "status": "No Data Yet",
            "color": "#6c757d"
        }
    
    for att in user_attempts:
        cat = att.get("category", "Algebra & Word Problems")
        if cat not in cat_stats:
            cat_stats[cat] = {
                "name": cat,
                "icon": "📌",
                "attempted": 0,
                "correct": 0,
                "hint_correct": 0,
                "total_score": 0.0,
                "accuracy": 0.0,
                "status": "No Data Yet",
                "color": "#6c757d"
            }
        cat_stats[cat]["attempted"] += 1
        if att.get("correct", False):
            cat_stats[cat]["correct"] += 1
            if att.get("hint_used", False):
                cat_stats[cat]["hint_correct"] += 1
        cat_stats[cat]["total_score"] += float(att.get("score", 0.0))

    for cat, stats in cat_stats.items():
        att_count = stats["attempted"]
        if att_count > 0:
            acc = (stats["correct"] / att_count) * 100.0
            stats["accuracy"] = round(acc, 1)
            if att_count < 3:
                stats["status"] = "Practicing 🆕"
                stats["color"] = "#17a2b8"
            elif acc >= 70.0:
                stats["status"] = "Strong 💪"
                stats["color"] = "#28a745"
            elif acc >= 50.0:
                stats["status"] = "Moderate 👍"
                stats["color"] = "#e67700"
            else:
                stats["status"] = "Focus Area ⚠️"
                stats["color"] = "#dc3545"

    return list(cat_stats.values())

def sample_balanced_questions(questions_pool, target_size, topic_filter):
    """Guarantees balanced coverage across all 5 Olympiad domains when practicing in mixed mode."""
    if not questions_pool or target_size <= 0:
        return []

    # If single topic is selected or target weakness mode, sample from the filtered pool
    if topic_filter != "All Topics (Mixed)":
        return random.sample(questions_pool, min(target_size, len(questions_pool)))

    buckets = {}
    for q in questions_pool:
        cat = q.get("category", "Algebra & Word Problems")
        buckets.setdefault(cat, []).append(q)

    if not buckets:
        return random.sample(questions_pool, min(target_size, len(questions_pool)))

    num_buckets = len(buckets)
    base_per_bucket = target_size // num_buckets
    remainder = target_size % num_buckets

    selected = []
    bucket_names = list(buckets.keys())
    random.shuffle(bucket_names)

    remaining_pool = []
    for idx, b_name in enumerate(bucket_names):
        b_questions = buckets[b_name]
        random.shuffle(b_questions)
        take_count = base_per_bucket + (1 if idx < remainder else 0)
        actual_take = min(take_count, len(b_questions))
        selected.extend(b_questions[:actual_take])
        remaining_pool.extend(b_questions[actual_take:])

    # If some categories had fewer questions, backfill from remaining pool
    if len(selected) < target_size and remaining_pool:
        needed = target_size - len(selected)
        extra = random.sample(remaining_pool, min(needed, len(remaining_pool)))
        selected.extend(extra)

    # Shuffle the final question list so topics appear interleaved and varied
    random.shuffle(selected)
    return selected

def log_result_to_sheets(test_type, score_str, user_email, duration_str="N/A"):
    if not GOOGLE_SHEET_WEB_APP_URL or "DÁN_URL" in GOOGLE_SHEET_WEB_APP_URL:
        return
    now_local = datetime.now(LOCAL_TZ)
    # Prefix with single quote to prevent Google Sheets auto-converting "10/25" into a Date
    safe_score_str = f"'{score_str}" if not score_str.startswith("'") else score_str
    payload = {
        "action": "log_score",
        "date": now_local.strftime("%Y-%m-%d %H:%M:%S"),
        "email": user_email,
        "type": test_type,
        "results": safe_score_str,
        "duration": duration_str
    }
    session = get_api_session()
    try:
        session.post(GOOGLE_SHEET_WEB_APP_URL, json=payload, timeout=20)
        fetch_user_history.clear()
    except Exception as e:
        print("Error logging score:", e)

@st.cache_data(ttl=60, show_spinner=False)
def fetch_user_history(user_email):
    if not GOOGLE_SHEET_WEB_APP_URL or "DÁN_URL" in GOOGLE_SHEET_WEB_APP_URL:
        return []
    session = get_api_session()
    try:
        response = session.get(f"{GOOGLE_SHEET_WEB_APP_URL}?type=history", timeout=20)
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
        print(f"⚠️ Cloud connection error: {e}")
    return []

# --- SIDEBAR: TOP TIMER PLACEHOLDER ---
sidebar_timer_placeholder = st.sidebar.empty()

# --- CONTINUOUS LIVE MOCK TIMER FRAGMENT ---
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
            st.rerun(scope="app")

# --- CONTINUOUS LIVE PRACTICE TIMER FRAGMENT (COUNT UP) ---
@st.fragment(run_every="1s")
def render_practice_timer():
    if st.session_state.get("practice_start_time") is not None and not st.session_state.get("practice_submitted", False):
        time_elapsed = int(time.time() - st.session_state.practice_start_time)
        mins, secs = divmod(time_elapsed, 60)
        
        sidebar_timer_placeholder.markdown(
            f"""
            <div style='background-color: #f8f9fa; border: 1px solid #dcdfe6; padding: 8px 12px; border-radius: 8px; text-align: center; margin-top: 0px; margin-bottom: 20px;'>
                <div style='font-size: 15px; font-weight: 600; color: #262730; margin-bottom: 2px;'>⏱️ Time Elapsed</div>
                <div style='font-size: 34px; font-weight: 800; color: #28a745; line-height: 1.1;'>{mins:02d}:{secs:02d}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

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

next_exam_date = COMPETITION_SCHEDULE.get(selected_competition, "2027")
st.sidebar.markdown(
    f"""
    <div style='background-color: #fff9db; border: 1px solid #ffe066; padding: 7px 12px; border-radius: 8px; margin-top: 4px; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;'>
        <span style='font-size: 14px; color: #495057; font-weight: 600;'>📅 Next Exam:</span>
        <span style='font-size: 15px; color: #d9480f; font-weight: 700; background-color: #ffffff; padding: 2px 8px; border-radius: 5px; border: 1px solid #ffd43b;'>{next_exam_date}</span>
    </div>
    """,
    unsafe_allow_html=True
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
if "practice_session_id" not in st.session_state:
    st.session_state.practice_session_id = 1

if "current_comp" not in st.session_state or st.session_state.current_comp != selected_competition:
    st.session_state.current_comp = selected_competition
    st.session_state.practice_questions = []
    st.session_state.practice_submitted = False
    st.session_state.practice_answers = {}
    st.session_state.logged_practice = False
    st.session_state.reshuffle_count = 0
    st.session_state.show_reshuffle_confirm = False
    st.session_state.practice_session_id = st.session_state.get("practice_session_id", 0) + 1

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

    topic_options = [
        "All Topics (Mixed)",
        "🎯 Focus on Weakest Topics",
        "📐 Geometry & Spatial",
        "🔢 Number Theory & Arithmetic",
        "📊 Algebra & Word Problems",
        "🎲 Counting & Probability",
        "🧩 Logic & Patterns"
    ]
    st.sidebar.markdown("**Select Practice Topic:**")
    default_topic_idx = 0
    if st.session_state.get("target_weakness_mode", False):
        default_topic_idx = 1
        st.session_state.target_weakness_mode = False

    selected_topic_filter = st.sidebar.selectbox(
        "Practice Topic:",
        topic_options,
        index=default_topic_idx,
        label_visibility="collapsed"
    )

    # Reset practice questions if topic filter changed
    if "current_topic_filter" not in st.session_state or st.session_state.current_topic_filter != selected_topic_filter:
        st.session_state.current_topic_filter = selected_topic_filter
        st.session_state.practice_questions = []
        st.session_state.practice_submitted = False
        st.session_state.practice_answers = {}
        st.session_state.practice_hints_used = {}
        st.session_state.logged_practice = False
        st.session_state.reshuffle_count = 0
        st.session_state.show_reshuffle_confirm = False
        st.session_state.practice_session_id = st.session_state.get("practice_session_id", 0) + 1

elif app_mode == "📝 Mock Test":
    test_files = get_comp_files(selected_competition)
    st.sidebar.markdown("**Select test paper:**")
    if test_files:
        selected_file = st.sidebar.selectbox("Test Paper:", test_files, label_visibility="collapsed")
    else:
        st.sidebar.warning(f"No test papers found for {selected_competition}.")

# CLEAR TIMER PLACEHOLDER WHEN NOT ACTIVE
if app_mode == "📊 My History" or (app_mode == "🎲 Practice" and st.session_state.get("practice_submitted", False)) or (app_mode == "📝 Mock Test" and st.session_state.get("submitted", False)):
    sidebar_timer_placeholder.empty()

# --- SIDEBAR: 2027 COMPETITION CALENDAR CARD ---
st.sidebar.markdown(
    """
    <div style='background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 12px 14px; margin-top: 16px; margin-bottom: 8px;'>
        <div style='font-size: 16px; font-weight: 700; color: #343a40; margin-bottom: 8px;'>📌 2027 Olympiad Schedule</div>
        <div style='font-size: 16px; color: #495057; line-height: 1.7;'>
            • <strong>AMC8:</strong> 29 Jan 2027<br>
            • <strong>SASMO:</strong> Apr 2027<br>
            • <strong>Kangaroo:</strong> Apr 2027
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

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
    st.markdown(
        f"""
        <div style='display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-top: 4px; margin-bottom: 16px;'>
            <h1 style='font-size: 28px; font-weight: 700; margin: 0; padding: 0; line-height: 1.2; color: inherit;'>
                🎲 Practice Session — {selected_competition}
            </h1>
            <div style='background-color: #e7f5ff; border: 1px solid #a5d8ff; padding: 6px 16px; border-radius: 20px; font-size: 14px; font-weight: 600; color: #1971c2; display: inline-flex; align-items: center; gap: 6px; white-space: nowrap;'>
                <span>🗓️ Next Exam:</span>
                <strong style='color: #0c8599; font-size: 15px;'>{next_exam_date}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
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
        if "reshuffle_count" not in st.session_state:
            st.session_state.reshuffle_count = 0
        if "show_reshuffle_confirm" not in st.session_state:
            st.session_state.show_reshuffle_confirm = False

        MAX_RESHUFFLES = 2
        remaining_reshuffles = MAX_RESHUFFLES - st.session_state.reshuffle_count
        reshuffle_disabled = st.session_state.reshuffle_count >= MAX_RESHUFFLES or st.session_state.get("practice_submitted", False)

        if st.sidebar.button(
            f"🔀 Reshuffle Practice Set ({remaining_reshuffles}/{MAX_RESHUFFLES} left)",
            type="primary",
            disabled=reshuffle_disabled
        ):
            st.session_state.show_reshuffle_confirm = True

        do_reshuffle = False
        if st.session_state.show_reshuffle_confirm:
            st.warning(f"⚠️ **Are you sure you want to reshuffle the questions?**\n\nAny current choices or progress in this session will be reset. ({remaining_reshuffles} reshuffle(s) remaining)")
            col_conf_yes, col_conf_no = st.columns(2)
            with col_conf_yes:
                if st.button("✅ Yes, Reshuffle", type="primary", key="confirm_reshuffle_yes"):
                    st.session_state.reshuffle_count += 1
                    st.session_state.practice_session_id = st.session_state.get("practice_session_id", 1) + 1
                    st.session_state.show_reshuffle_confirm = False
                    do_reshuffle = True
            with col_conf_no:
                if st.button("❌ No, Keep Practicing", key="confirm_reshuffle_no"):
                    st.session_state.show_reshuffle_confirm = False
                    st.rerun()

        pooled_questions = []
        for file in comp_files:
            file_path = os.path.join(BASE_DIR, file)
            data = load_dataset_json(file_path)
            for item in data:
                item_copy = dict(item)
                item_copy["source_file"] = file
                pooled_questions.append(item_copy)

        # Apply topic filter
        if selected_topic_filter == "🎯 Focus on Weakest Topics":
            analytics = get_topic_analytics(user_email)
            weak_topics = [item["name"] for item in analytics if item["attempted"] > 0 and item["accuracy"] < 60.0]
            if not weak_topics:
                with_data = [item for item in analytics if item["attempted"] > 0]
                if with_data:
                    min_acc = min(item["accuracy"] for item in with_data)
                    weak_topics = [item["name"] for item in with_data if item["accuracy"] == min_acc]
            if weak_topics:
                filtered = [q for q in pooled_questions if q.get("category") in weak_topics]
                if filtered:
                    pooled_questions = filtered
                    st.info(f"🎯 **Targeted Weakness Mode**: Focusing practice questions on your weak areas: **{', '.join(weak_topics)}**.")
                else:
                    st.warning(f"No questions found for weak topics ({', '.join(weak_topics)}) in {selected_competition}. Using all topics.")
            else:
                st.info("💡 Complete a few practice sessions or mock tests first so the app can identify your specific weak areas. Serving a balanced set for now!")
        elif selected_topic_filter != "All Topics (Mixed)":
            clean_topic = selected_topic_filter.split(" ", 1)[-1].strip()
            filtered = [q for q in pooled_questions if q.get("category", "").lower() == clean_topic.lower()]
            if filtered:
                pooled_questions = filtered
                st.info(f"📌 **Topic Filter Active**: Practicing **{selected_topic_filter}** ({len(filtered)} questions available).")
            else:
                st.warning(f"No questions found for topic '{clean_topic}' in {selected_competition}. Using all available questions.")

        target_sample_size = min(num_q_select, len(pooled_questions)) if pooled_questions else 0
        needs_sampling = (
            do_reshuffle 
            or not st.session_state.practice_questions 
            or (not st.session_state.practice_submitted and len(st.session_state.practice_questions) != target_sample_size)
        )

        if selected_topic_filter == "All Topics (Mixed)" and target_sample_size >= 5:
            base_count = target_sample_size // 5
            st.caption(f"✨ **Balanced Topic Coverage**: Every set guarantees at least **{base_count} question(s)** from each of the 5 Olympiad domains.")

        if needs_sampling and pooled_questions:
            st.session_state.practice_questions = sample_balanced_questions(pooled_questions, target_sample_size, selected_topic_filter)
            st.session_state.practice_submitted = False
            st.session_state.practice_answers = {}
            st.session_state.logged_practice = False
            st.session_state.practice_start_time = time.time()
            if do_reshuffle:
                st.rerun()

        if st.session_state.practice_questions:
            # Backfill hints for any questions already stored in session_state from an earlier run
            for q in st.session_state.practice_questions:
                if not q.get("hint"):
                    src = q.get("source_file")
                    if src:
                        src_data = load_dataset_json(os.path.join(BASE_DIR, src))
                        for item in src_data:
                            if str(item.get("id")) == str(q.get("id")) and item.get("hint"):
                                q["hint"] = item["hint"]
                                break

            questions = st.session_state.practice_questions
            sess_id = st.session_state.get("practice_session_id", 1)

            if "practice_hints_used" not in st.session_state:
                st.session_state.practice_hints_used = {}

            def sync_practice_answers():
                for idx, q in enumerate(questions):
                    wk = f"practice_{selected_competition}_{idx}_{q['id']}_{sess_id}"
                    if wk in st.session_state and st.session_state[wk] is not None:
                        st.session_state.practice_answers[idx] = st.session_state[wk]
                    hk = f"hint_practice_{selected_competition}_{idx}_{q['id']}_{sess_id}"
                    if hk in st.session_state:
                        st.session_state.practice_hints_used[idx] = bool(st.session_state[hk])

            if not st.session_state.practice_submitted:
                col_sub1, _ = st.columns([2, 6])
                with col_sub1:
                    if st.button("📤 Submit Practice Set (Top)", type="primary", use_container_width=True, key="top_submit_practice"):
                        sync_practice_answers()
                        st.session_state.practice_submitted = True
                        st.rerun()
                st.markdown("---")

            if st.session_state.practice_submitted:
                scroll_to_top()
                sync_practice_answers()
                
                score = 0.0
                full_pts_count = 0
                hint_pts_count = 0
                wrong_count = 0

                for idx, q in enumerate(questions):
                    user_ans = st.session_state.practice_answers.get(idx)
                    correct_ans = q["answer"]
                    used_hint = st.session_state.practice_hints_used.get(idx, False)

                    if user_ans == correct_ans:
                        if used_hint:
                            score += 0.7
                            hint_pts_count += 1
                        else:
                            score += 1.0
                            full_pts_count += 1
                    else:
                        wrong_count += 1

                total = len(questions)
                pct = (score / total) * 100 if total > 0 else 0.0
                elapsed_secs = int(time.time() - st.session_state.practice_start_time)
                m, s = divmod(elapsed_secs, 60)
                time_str = f"{m} min {s} secs" if m > 0 else f"{s} secs"
                score_display = f"{score:.1f}" if score % 1 != 0 else f"{int(score)}"

                if not st.session_state.logged_practice:
                    log_result_to_sheets(f"Practice Mode - {selected_competition}", f"{score_display}/{total}", user_email, time_str)
                    # Record detailed question attempts for topic mastery
                    now_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")
                    attempts = []
                    for idx, q in enumerate(questions):
                        user_ans = st.session_state.practice_answers.get(idx)
                        correct_ans = q["answer"]
                        used_hint = st.session_state.practice_hints_used.get(idx, False)
                        is_corr = (user_ans == correct_ans)
                        pts = 0.7 if (is_corr and used_hint) else (1.0 if is_corr else 0.0)
                        attempts.append({
                            "timestamp": now_str,
                            "session_type": f"Practice ({selected_competition})",
                            "source_file": q.get("source_file", ""),
                            "q_id": q["id"],
                            "category": q.get("category", "Algebra & Word Problems"),
                            "correct": is_corr,
                            "score": pts,
                            "hint_used": used_hint
                        })
                    record_question_attempts(user_email, attempts)
                    st.session_state.logged_practice = True

                st.markdown(
                    f"""
                    <div style='background-color: #d4edda; color: #155724; padding: 14px 18px; border-radius: 8px; border-left: 5px solid #28a745; margin-bottom: 12px; overflow: hidden;'>
                        <h3 style='margin: 0; color: #155724; font-size: 20px; font-weight: 700;'>🎯 Practice Set Submitted Successfully!</h3>
                        <p style='margin: 6px 0 2px 0; font-size: 18px; font-weight: 600;'>
                            Your Score: <span style='color: #0b2e13; font-size: 20px;'>{score_display}/{total} ({pct:.1f}%)</span> in <strong>{time_str}</strong>.
                        </p>
                        <div style='font-size: 14px; color: #155724; margin-top: 4px;'>
                            🌟 <strong>Breakdown:</strong> {full_pts_count} solved independently (1.0 pt) • {hint_pts_count} solved with hint (0.7 pts, -30%) • {wrong_count} incorrect (0 pts)
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                if st.button("🔄 Start New Practice Session"):
                    st.session_state.practice_session_id = st.session_state.get("practice_session_id", 1) + 1
                    st.session_state.practice_questions = []
                    st.session_state.practice_submitted = False
                    st.session_state.practice_answers = {}
                    st.session_state.practice_hints_used = {}
                    st.session_state.logged_practice = False
                    st.session_state.practice_start_time = time.time()
                    st.session_state.reshuffle_count = 0
                    st.session_state.show_reshuffle_confirm = False
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
                    used_hint = st.session_state.practice_hints_used.get(idx, False)

                    q_cat = q.get("category", "General Math")
                    if user_ans == correct_ans:
                        if used_hint:
                            st.markdown(f"✅ **Question {idx + 1}** [{q_cat}]: **Correct with Hint** (Score: **0.7 / 1.0** pts, -30% deduction) — Your choice: {user_ans_str}")
                        else:
                            st.markdown(f"✅ **Question {idx + 1}** [{q_cat}]: **Correct** (Score: **1.0 / 1.0** pts) — Your choice: {user_ans_str}")
                    else:
                        hint_note = " (Hint was viewed)" if used_hint else ""
                        st.markdown(f"❌ **Question {idx + 1}** [{q_cat}]: **Incorrect** (Score: **0.0 / 1.0** pts{hint_note}) — Your choice: {user_ans_str} | Correct answer: **{correct_ans}**")

                    with st.expander(f"View Solution for Question {idx + 1}"):
                        img_path = get_image_path(folder_name, q_id)
                        if img_path:
                            st.image(img_path, width=img_w)
                        st.markdown(q["explanation"], unsafe_allow_html=True)
                    st.markdown("---")

            else:
                render_practice_timer()

                for idx, q in enumerate(questions):
                    q_id = q['id']
                    source_file = q.get("source_file", "")
                    folder_name = source_file.replace(".json", "") if source_file else ""
                    img_w = q.get("image_width", 300)
                    q_cat = q.get("category", "General Math")
                    
                    st.subheader(f"Question {idx + 1} (From {source_file})")
                    st.markdown(
                        f"""
                        <div style='margin-top: -6px; margin-bottom: 8px;'>
                            <span style='background-color: #f1f3f5; color: #495057; font-size: 13px; font-weight: 600; padding: 2px 10px; border-radius: 6px; border: 1px solid #dee2e6;'>
                                🏷️ Topic: {q_cat}
                            </span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    st.markdown(q["question"], unsafe_allow_html=True)
                    
                    img_path = get_image_path(folder_name, q_id)
                    if img_path:
                        st.image(img_path, width=img_w)

                    # --- HINT OPTION (-30% score penalty if correct) ---
                    hint_key = f"hint_practice_{selected_competition}_{idx}_{q_id}_{sess_id}"
                    hint_unlocked = st.session_state.get(hint_key, False)
                    hint_text = q.get("hint")

                    if not hint_unlocked:
                        if st.button("💡 Show Hint (-30% points if correct)", key=f"btn_{hint_key}"):
                            st.session_state[hint_key] = True
                            st.session_state.practice_hints_used[idx] = True
                            st.rerun()
                    else:
                        st.markdown(
                            """
                            <div style='background-color: #fff9db; border: 1px solid #ffd43b; border-left: 5px solid #fcc419; padding: 10px 14px; border-radius: 6px; margin-top: 6px; margin-bottom: 6px;'>
                                <div style='font-size: 15px; font-weight: 700; color: #7a5800;'>💡 Step-by-Step Guidance:</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        st.markdown(hint_text if hint_text else "Break down the problem step-by-step and identify what information is given.")
                        st.markdown(
                            """
                            <div style='background-color: #fff3cd; color: #856404; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: 600; display: inline-block; margin-bottom: 12px;'>
                                ⚠️ Hint viewed: A correct answer will earn 0.70 pts (30% deduction).
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                    ans = st.radio(
                        f"Choose answer for Q{idx+1}:", 
                        q["options"], 
                        key=f"practice_{selected_competition}_{idx}_{q_id}_{sess_id}", 
                        index=None,
                        label_visibility="collapsed"
                    )
                    st.session_state.practice_answers[idx] = ans
                    st.markdown("---")

                col_bot1, _ = st.columns([2, 6])
                with col_bot1:
                    if st.button("📤 Submit Practice Set (Bottom)", type="primary", use_container_width=True, key="bot_submit_practice"):
                        sync_practice_answers()
                        st.session_state.practice_submitted = True
                        st.rerun()
                st.markdown("---")

# ==========================================
# MOCK TEST MODE
# ==========================================
elif app_mode == "📝 Mock Test":
    st.markdown(
        f"""
        <div style='display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-top: 4px; margin-bottom: 16px;'>
            <h1 style='font-size: 28px; font-weight: 700; margin: 0; padding: 0; line-height: 1.2; color: inherit;'>
                ✍️ Mock Test: {selected_competition}
            </h1>
            <div style='background-color: #e7f5ff; border: 1px solid #a5d8ff; padding: 6px 16px; border-radius: 20px; font-size: 14px; font-weight: 600; color: #1971c2; display: inline-flex; align-items: center; gap: 6px; white-space: nowrap;'>
                <span>🗓️ Next Exam:</span>
                <strong style='color: #0c8599; font-size: 15px;'>{next_exam_date}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if not selected_file:
        st.warning(f"No test papers available for **{selected_competition}**.")
    else:
        if "mock_attempt_id" not in st.session_state:
            st.session_state.mock_attempt_id = 1
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
            st.session_state.mock_attempt_id = st.session_state.get("mock_attempt_id", 0) + 1

        file_path = os.path.join(BASE_DIR, selected_file)
        questions = load_dataset_json(file_path)

        year_match = re.search(r'\d{4}', selected_file)
        exam_year = year_match.group(0) if year_match else ""
        folder_name = selected_file.replace(".json", "")
        att_id = st.session_state.get("mock_attempt_id", 1)

        if "user_hints_used" not in st.session_state:
            st.session_state.user_hints_used = {}

        def sync_mock_answers():
            for q in questions:
                wk = f"q_{selected_file}_{q['id']}_{att_id}"
                if wk in st.session_state and st.session_state[wk] is not None:
                    st.session_state.user_answers[q['id']] = st.session_state[wk]
                hk = f"hint_mock_{selected_file}_{q['id']}_{att_id}"
                if hk in st.session_state:
                    st.session_state.user_hints_used[q['id']] = bool(st.session_state[hk])

        if questions:
            st.markdown("---")
            col_space1, col_submit, col_space2, col_retake = st.columns([4, 2, 2, 2])
            
            with col_submit:
                if not st.session_state.submitted:
                    if st.button("🔴 Submit Test (Top)", type="primary", use_container_width=True, key="top_submit_mock"):
                        sync_mock_answers()
                        st.session_state.submitted = True
                        st.rerun()
            
            with col_retake:
                if st.button("🔄 Restart Test", use_container_width=True, key="top_restart_mock"):
                    st.session_state.start_time = time.time()
                    st.session_state.submitted = False
                    st.session_state.user_answers = {}
                    st.session_state.user_hints_used = {}
                    st.session_state.logged_mock = False
                    st.session_state.mock_attempt_id = st.session_state.get("mock_attempt_id", 0) + 1
                    st.rerun()
            st.markdown("---")

            if st.session_state.submitted:
                scroll_to_top()
                sync_mock_answers()

                score = 0.0
                full_pts_count = 0
                hint_pts_count = 0
                wrong_count = 0

                for q in questions:
                    q_id = q['id']
                    user_ans = st.session_state.user_answers.get(q_id)
                    correct_ans = q["answer"]
                    used_hint = st.session_state.user_hints_used.get(q_id, False)

                    if user_ans == correct_ans:
                        if used_hint:
                            score += 0.7
                            hint_pts_count += 1
                        else:
                            score += 1.0
                            full_pts_count += 1
                    else:
                        wrong_count += 1

                total = len(questions)
                pct = (score / total) * 100 if total > 0 else 0.0
                elapsed_secs = int(time.time() - st.session_state.start_time)
                m, s = divmod(elapsed_secs, 60)
                time_str = f"{m} min {s} secs" if m > 0 else f"{s} secs"
                score_display = f"{score:.1f}" if score % 1 != 0 else f"{int(score)}"

                if not st.session_state.logged_mock:
                    log_result_to_sheets(f"Mock Test - {selected_competition} {exam_year}", f"{score_display}/{total}", user_email, time_str)
                    # Record detailed question attempts for topic mastery
                    now_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")
                    attempts = []
                    for q in questions:
                        q_id = q["id"]
                        user_ans = st.session_state.user_answers.get(q_id)
                        correct_ans = q["answer"]
                        used_hint = st.session_state.user_hints_used.get(q_id, False)
                        is_corr = (user_ans == correct_ans)
                        pts = 0.7 if (is_corr and used_hint) else (1.0 if is_corr else 0.0)
                        attempts.append({
                            "timestamp": now_str,
                            "session_type": f"Mock Test ({selected_competition} {exam_year})",
                            "source_file": selected_file,
                            "q_id": q_id,
                            "category": q.get("category", "Algebra & Word Problems"),
                            "correct": is_corr,
                            "score": pts,
                            "hint_used": used_hint
                        })
                    record_question_attempts(user_email, attempts)
                    st.session_state.logged_mock = True

                st.markdown(
                    f"""
                    <div style='background-color: #d4edda; color: #155724; padding: 14px 18px; border-radius: 8px; border-left: 5px solid #28a745; margin-bottom: 12px; overflow: hidden;'>
                        <h3 style='margin: 0; color: #155724; font-size: 20px; font-weight: 700;'>🎉 Test Submitted Successfully!</h3>
                        <p style='margin: 6px 0 2px 0; font-size: 18px; font-weight: 600;'>
                            Your Score: <span style='color: #0b2e13; font-size: 20px;'>{score_display}/{total} ({pct:.1f}%)</span> in <strong>{time_str}</strong>.
                        </p>
                        <div style='font-size: 14px; color: #155724; margin-top: 4px;'>
                            🌟 <strong>Breakdown:</strong> {full_pts_count} solved independently (1.0 pt) • {hint_pts_count} solved with hint (0.7 pts, -30%) • {wrong_count} incorrect (0 pts)
                        </div>
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
                    used_hint = st.session_state.user_hints_used.get(q_id, False)
                    q_cat = q.get("category", "General Math")
                    
                    if user_ans == correct_ans:
                        if used_hint:
                            st.markdown(f"✅ **Question {q_id}** [{q_cat}]: **Correct with Hint** (Score: **0.7 / 1.0** pts, -30% deduction) — Your choice: {user_ans_str}")
                        else:
                            st.markdown(f"✅ **Question {q_id}** [{q_cat}]: **Correct** (Score: **1.0 / 1.0** pts) — Your choice: {user_ans_str}")
                    else:
                        hint_note = " (Hint was viewed)" if used_hint else ""
                        st.markdown(f"❌ **Question {q_id}** [{q_cat}]: **Incorrect** (Score: **0.0 / 1.0** pts{hint_note}) — Your choice: {user_ans_str} | Correct answer: **{correct_ans}**")
                    
                    with st.expander(f"View Solution for Question {q_id}"):
                        img_path = get_image_path(folder_name, q_id)
                        if img_path:
                            st.image(img_path, width=img_w)
                        st.markdown(q["explanation"], unsafe_allow_html=True)
                    st.markdown("---")

            else:
                render_mock_timer()

                for q in questions:
                    q_id = q['id']
                    img_w = q.get("image_width", 300)
                    q_cat = q.get("category", "General Math")

                    st.subheader(f"Question {q_id}")
                    st.markdown(
                        f"""
                        <div style='margin-top: -6px; margin-bottom: 8px;'>
                            <span style='background-color: #f1f3f5; color: #495057; font-size: 13px; font-weight: 600; padding: 2px 10px; border-radius: 6px; border: 1px solid #dee2e6;'>
                                🏷️ Topic: {q_cat}
                            </span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    st.markdown(q["question"], unsafe_allow_html=True)
                    
                    img_path = get_image_path(folder_name, q_id)
                    if img_path:
                        st.image(img_path, width=img_w)

                    # --- HINT OPTION (-30% score penalty if correct) ---
                    hint_key = f"hint_mock_{selected_file}_{q_id}_{att_id}"
                    hint_unlocked = st.session_state.get(hint_key, False)
                    hint_text = q.get("hint")

                    if not hint_unlocked:
                        if st.button("💡 Show Hint (-30% points if correct)", key=f"btn_{hint_key}"):
                            st.session_state[hint_key] = True
                            st.session_state.user_hints_used[q_id] = True
                            st.rerun()
                    else:
                        st.markdown(
                            """
                            <div style='background-color: #fff9db; border: 1px solid #ffd43b; border-left: 5px solid #fcc419; padding: 10px 14px; border-radius: 6px; margin-top: 6px; margin-bottom: 6px;'>
                                <div style='font-size: 15px; font-weight: 700; color: #7a5800;'>💡 Step-by-Step Guidance:</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        st.markdown(hint_text if hint_text else "Break down the problem step-by-step and identify what information is given.")
                        st.markdown(
                            """
                            <div style='background-color: #fff3cd; color: #856404; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: 600; display: inline-block; margin-bottom: 12px;'>
                                ⚠️ Hint viewed: A correct answer will earn 0.70 pts (30% deduction).
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    
                    ans = st.radio(
                        f"Choose your answer for Question {q_id}:", 
                        q["options"], 
                        key=f"q_{selected_file}_{q_id}_{att_id}", 
                        index=None,
                        label_visibility="collapsed"
                    )
                    st.session_state.user_answers[q_id] = ans
                    st.markdown("---")

                col_bspace, col_bsubmit, col_bspace2 = st.columns([4, 2, 4])
                with col_bsubmit:
                    if st.button("🔴 Submit Test (Bottom)", type="primary", use_container_width=True, key="bot_submit_mock"):
                        sync_mock_answers()
                        st.session_state.submitted = True
                        st.rerun()
                st.markdown("---")

# ==========================================
# 3. MY HISTORY TAB
# ==========================================
elif app_mode == "📊 My History":
    col_htitle, col_hrefresh = st.columns([4, 1])
    with col_htitle:
        st.title("📊 Your Performance History")
    with col_hrefresh:
        if st.button("🔄 Refresh Data", use_container_width=True):
            fetch_user_history.clear()
            st.rerun()

    st.write(f"Showing practice and test history for email: **{user_email}**")
    
    # ==========================================
    # TOPIC MASTERY & STRENGTHS/WEAKNESSES DASHBOARD
    # ==========================================
    st.markdown("### 🎯 Strengths & Weaknesses (Topic Mastery)")
    analytics = get_topic_analytics(user_email)
    total_attempts = sum(cat["attempted"] for cat in analytics)

    if total_attempts == 0:
        st.info("ℹ️ Complete a few practice sessions or mock tests to begin tracking your personalized strengths and weaknesses breakdown here!")
    else:
        attempted_cats = [c for c in analytics if c["attempted"] > 0]
        weak_cats = [c for c in attempted_cats if c["accuracy"] < 50.0]
        moderate_cats = [c for c in attempted_cats if 50.0 <= c["accuracy"] < 70.0]
        strong_cats = [c for c in attempted_cats if c["accuracy"] >= 70.0]

        # Recommendation Card
        rec_html = "<div style='background-color: #f8f9fa; border: 1px solid #ced4da; border-radius: 8px; padding: 12px 16px; margin-bottom: 14px;'>"
        rec_html += "<div style='font-size: 15px; font-weight: 700; color: #343a40; margin-bottom: 4px;'>💡 Personalized Study Guidance:</div>"
        if weak_cats:
            weak_str = ", ".join([f"<strong>{c['name']}</strong> ({c['accuracy']}%)" for c in weak_cats])
            rec_html += f"<div style='font-size: 14px; color: #c92a2a; line-height: 1.5;'>⚠️ <strong>Needs Improvement:</strong> {weak_str} — Accuracy is lowest here. Focusing practice on these areas will yield the greatest score gains.</div>"
        if strong_cats:
            strong_str = ", ".join([f"<strong>{c['name']}</strong> ({c['accuracy']}%)" for c in strong_cats])
            rec_html += f"<div style='font-size: 14px; color: #2b8a3e; line-height: 1.5; margin-top: 4px;'>💪 <strong>Solid Strengths:</strong> {strong_str} — Great mastery! Keep reviewing periodically.</div>"
        if not weak_cats and not strong_cats:
            rec_html += "<div style='font-size: 14px; color: #495057; line-height: 1.5;'>Performance is currently balanced across topics. Continue practicing to push accuracy above 70%!</div>"
        rec_html += "</div>"
        st.markdown(rec_html, unsafe_allow_html=True)

        # 5 Topic Cards Grid
        cols = st.columns(len(analytics))
        for col, cat in zip(cols, analytics):
            with col:
                bg_col = "#eafaf1" if cat["accuracy"] >= 70 else ("#fef9e7" if cat["accuracy"] >= 50 else ("#fdf2f2" if cat["attempted"] > 0 else "#f8f9fa"))
                border_col = "#a3e4d7" if cat["accuracy"] >= 70 else ("#f9e79f" if cat["accuracy"] >= 50 else ("#f5b7b1" if cat["attempted"] > 0 else "#e9ecef"))
                text_col = "#1e8449" if cat["accuracy"] >= 70 else ("#b7950b" if cat["accuracy"] >= 50 else ("#c0392b" if cat["attempted"] > 0 else "#6c757d"))
                acc_display = f"{cat['accuracy']}%" if cat["attempted"] > 0 else "N/A"
                
                st.markdown(
                    f"""
                    <div style='background-color: {bg_col}; border: 1px solid {border_col}; border-radius: 8px; padding: 10px 8px; text-align: center; min-height: 145px; display: flex; flex-direction: column; justify-content: space-between;'>
                        <div>
                            <div style='font-size: 22px; line-height: 1.0;'>{cat['icon']}</div>
                            <div style='font-size: 12px; font-weight: 700; color: #343a40; margin-top: 2px; line-height: 1.2;'>{cat['name']}</div>
                        </div>
                        <div>
                            <div style='font-size: 24px; font-weight: 800; color: {text_col}; margin: 2px 0 2px 0;'>{acc_display}</div>
                            <div style='font-size: 11px; font-weight: 600; color: {text_col}; background-color: #ffffff; padding: 1px 6px; border-radius: 8px; border: 1px solid {border_col}; display: inline-block;'>{cat['status']}</div>
                        </div>
                        <div style='font-size: 11px; color: #6c757d; margin-top: 2px;'>
                            {cat['correct']}/{cat['attempted']} solved
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                progress_val = min(1.0, max(0.0, cat["accuracy"] / 100.0)) if cat["attempted"] > 0 else 0.0
                st.progress(progress_val)
    st.markdown("---")
    
    with st.spinner("Fetching your history from Google Sheets..."):
        history = fetch_user_history(user_email)

    if history:
        table_data = []
        chart_data = []
        valid_pcts = []

        for h in history:
            raw_date = str(h.get("date") or h.get("Date") or h.get("timestamp") or "").strip()
            raw_score = str(h.get("results") or h.get("Results") or h.get("score") or "").strip().lstrip("'")
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
                    clean_str = raw_date.split(".")[0]
                    if "Z" in raw_date or ("T" in raw_date and raw_date.endswith("Z")):
                        dt = datetime.fromisoformat(clean_str.replace("Z", "")).replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
                    elif "T" in clean_str:
                        dt = datetime.fromisoformat(clean_str)
                        if dt.tzinfo is not None:
                            dt = dt.astimezone(LOCAL_TZ)
                    else:
                        dt = datetime.strptime(clean_str, "%Y-%m-%d %H:%M:%S")
                        
                    formatted_date = dt.strftime("%d-%m-%y %H:%M")
                except Exception:
                    formatted_date = raw_date
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
                        valid_pcts.append(pct_number)
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

        # Calculate Average Accuracy for Last 10 Sessions
        last_10_pcts = valid_pcts[-10:] if valid_pcts else []
        avg_last_10 = (sum(last_10_pcts) / len(last_10_pcts)) if last_10_pcts else 0.0

        # Dynamic Status Colors for Box 1
        status_bg = "#d4edda" if avg_last_10 >= 60.0 else "#fff3cd"
        status_color = "#155724" if avg_last_10 >= 60.0 else "#856404"
        status_border = "#c3e6cb" if avg_last_10 >= 60.0 else "#ffeeba"

        # Display the 3 Summary Cards Side-by-Side
        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            st.markdown(
                f"""
                <div style='background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; padding: 10px 14px; border-radius: 8px; font-size: 16px; font-weight: 600; text-align: center; min-height: 48px; display: flex; align-items: center; justify-content: center;'>
                    📋 Found {len(history)} recorded session(s)!
                </div>
                """,
                unsafe_allow_html=True
            )

        with col2:
            st.markdown(
                f"""
                <div style='background-color: {status_bg}; color: {status_color}; border: 1px solid {status_border}; padding: 10px 14px; border-radius: 8px; font-size: 16px; font-weight: 600; text-align: center; min-height: 48px; display: flex; align-items: center; justify-content: center;'>
                    📊 Avg Accuracy (Last 10):&nbsp;<strong style='font-size: 18px;'>{avg_last_10:.1f}%</strong>
                </div>
                """,
                unsafe_allow_html=True
            )

        with col3:
            st.markdown(
                """
                <div style='background-color: #e3f2fd; color: #0d47a1; border: 1px solid #bbdefb; padding: 10px 14px; border-radius: 8px; font-size: 16px; font-weight: 600; text-align: center; min-height: 48px; display: flex; align-items: center; justify-content: center;'>
                    🎯 Target Accuracy:&nbsp;<strong style='font-size: 18px;'>60.0%</strong>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.markdown("<div style='margin-bottom: 16px;'></div>", unsafe_allow_html=True)

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