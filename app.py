import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import time
import os
import re
import random
import requests
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Math Olympiad App", layout="wide")

# --- ANCHOR AT THE VERY TOP FOR AUTO-SCROLLING ---
st.markdown("<div id='top'></div>", unsafe_allow_html=True)

# --- GOOGLE APPS SCRIPT WEB APP URL CONFIGURATION ---
GOOGLE_SHEET_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbxNQxi8rjasBOS3bt0MRG6JwblKKaPGM9pmIKW_k9LBaCyIipakxBxC9uss2KOXNlkWeg/exec"

# --- CUSTOM CSS FOR COMPACT & CLEAN LAYOUT ---
st.markdown(
    """
    <style>
    /* Comfortable top padding so top banners are never clipped */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 1rem !important;
    }

    /* Global font size setting */
    html, body, [class*="css"] {
        font-size: 18px !important;
    }

    /* Standardize main page headings to match sidebar size */
    h1 {
        font-size: 22px !important;
        font-weight: 700 !important;
        margin-top: 0px !important;
        margin-bottom: 8px !important;
        padding-top: 0px !important;
    }

    /* Make text input box ~15% taller */
    div[data-testid="stTextInput"] input {
        padding-top: 10px !important;
        padding-bottom: 10px !important;
        min-height: 44px !important;
        font-size: 18px !important;
    }

    /* Space below text input box */
    div[data-testid="stTextInput"] {
        margin-bottom: 16px !important;
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

# --- HELPER FUNCTIONS FOR BACKEND API ---
@st.cache_data(ttl=60)
def get_registered_emails():
    if not GOOGLE_SHEET_WEB_APP_URL or "DÁN_URL" in GOOGLE_SHEET_WEB_APP_URL:
        return []
    try:
        response = requests.get(f"{GOOGLE_SHEET_WEB_APP_URL}?type=users", timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print("Error fetching users:", e)
    return []

def register_new_email(email):
    payload = {"action": "register", "email": email}
    try:
        res = requests.post(GOOGLE_SHEET_WEB_APP_URL, json=payload, timeout=15)
        st.cache_data.clear()
        return res.json().get("status")
    except Exception as e:
        print("Error registering email:", e)
        return "error"

def log_result_to_sheets(test_type, score_str, user_email):
    now_local = datetime.now().astimezone()
    payload = {
        "action": "log_score",
        "date": now_local.strftime("%Y-%m-%d %H:%M:%S"),
        "email": user_email,
        "type": test_type,
        "results": score_str
    }
    try:
        requests.post(GOOGLE_SHEET_WEB_APP_URL, json=payload, timeout=15)
    except Exception as e:
        print("Error logging score:", e)

def fetch_user_history(user_email):
    try:
        response = requests.get(f"{GOOGLE_SHEET_WEB_APP_URL}?type=history", timeout=15)
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
                                "results": row[3]
                            })
            return filtered
    except Exception as e:
        st.error(f"⚠️ Cloud connection error: {e}")
    return []

# --- SIDEBAR: TOP TIMER PLACEHOLDER ---
sidebar_timer_placeholder = st.sidebar.empty()

# --- SIDEBAR NAVIGATION (CENTERED CUP EMOJI ABOVE APP TITLE) ---
st.sidebar.markdown(
    """
    <div style='text-align: center; margin-bottom: 16px;'>
        <div style='font-size: 32px; line-height: 1.2;'>🏆</div>
        <div style='font-size: 22px; font-weight: 700; color: #262730; margin-top: 4px;'>Math Olympiad App</div>
    </div>
    """,
    unsafe_allow_html=True
)

user_email = st.sidebar.text_input("📧 Enter your Gmail:", value="").strip().lower()

# --- STRICT EMAIL VALIDATION & REGISTRATION FLOW ---
valid_access = False

if user_email:
    if not user_email.endswith("@gmail.com"):
        st.sidebar.error("⚠️ Only valid @gmail.com addresses are allowed!")
    else:
        registered_list = get_registered_emails()
        
        if user_email in registered_list:
            valid_access = True
            st.sidebar.success("✅ Verified User")
        else:
            st.sidebar.error("❌ Access Denied: Email not registered!")
            st.sidebar.info("If this is your first time, click below to register:")
            if st.sidebar.button("📝 Register This Email Now"):
                status = register_new_email(user_email)
                if status == "success":
                    st.sidebar.success("🎉 Registered successfully! Please refresh the page.")
                    time.sleep(1)
                    st.rerun()
                elif status == "exists":
                    st.sidebar.info("ℹ️ Email already exists. Try refreshing.")
                else:
                    st.sidebar.error("❌ Registration failed. Try again.")

# Sidebar navigation options
app_mode = st.sidebar.radio("Select Mode:", ["🎲 Practice Mode", "📝 Mock Test", "📊 My History"])

# --- SECURITY GATE: STOP APP IF NOT VALID ---
if not valid_access:
    st.title("🔒 Access Restricted")
    st.warning("Please enter a valid, **registered @gmail.com** address in the sidebar and verify your access to use the Math Olympiad App.")
    st.stop()

# ==========================================
# IF VALIDATED, RENDER MAIN APP BELOW
# ==========================================

# --- INSPIRATIONAL BANNER (UNCIPPED FULL BOX) ---
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
# PRACTICE MODE (RANDOM QUESTIONS)
# ==========================================
if app_mode == "🎲 Practice Mode":
    st.title("🎲 Random Practice Session")
    st.write("Practice random questions collected across all available past test papers.")

    all_json_files = [f for f in os.listdir(BASE_DIR) if f.endswith(".json")]

    if not all_json_files:
        st.warning("No test data files found in directory.")
    else:
        num_q_select = st.sidebar.slider("Select Number of Questions:", min_value=5, max_value=25, value=10, step=1)

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

        if st.sidebar.button("🔀 Generate New Practice Set", type="primary"):
            pooled_questions = []
            for file in all_json_files:
                file_path = os.path.join(BASE_DIR, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        year_match = re.search(r'\d{4}', file)
                        exam_year = year_match.group(0) if year_match else ""
                        for item in data:
                            item["source_file"] = file
                            item["exam_year"] = exam_year
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
                st.rerun()

        if st.session_state.practice_questions:
            questions = st.session_state.practice_questions

            # --- TOP SUBMIT BUTTON ---
            if not st.session_state.practice_submitted:
                col_sub1, _ = st.columns([2, 6])
                with col_sub1:
                    if st.button("📤 Submit Practice Set (Top)", type="primary", use_container_width=True, key="top_submit_practice"):
                        st.session_state.practice_submitted = True
                        st.rerun()
                st.markdown("---")

            # --- IF SUBMITTED: SCROLL TO TOP & SHOW COMPACT RESULTS BANNER ---
            if st.session_state.practice_submitted:
                scroll_to_top()
                
                score = 0
                total = len(questions)

                for idx, q in enumerate(questions):
                    user_ans = st.session_state.practice_answers.get(idx)
                    if user_ans is not None and user_ans == q["answer"]:
                        score += 1

                if not st.session_state.logged_practice:
                    log_result_to_sheets("Practice Mode", f"{score}/{total}", user_email)
                    st.session_state.logged_practice = True

                pct = (score / total) * 100 if total > 0 else 0.0
                
                elapsed_secs = int(time.time() - st.session_state.practice_start_time)
                m, s = divmod(elapsed_secs, 60)
                time_str = f"{m} min {s} secs" if m > 0 else f"{s} secs"

                # Compact, space-optimized results banner
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
                    st.rerun()

                st.markdown("### 📝 Detailed Review")
                for idx, q in enumerate(questions):
                    user_ans = st.session_state.practice_answers.get(idx)
                    user_ans_str = user_ans if user_ans is not None else "Not answered"
                    correct_ans = q["answer"]
                    q_id = q['id']
                    exam_year = q.get("exam_year", "")
                    img_w = q.get("image_width", 300)

                    if user_ans == correct_ans:
                        st.markdown(f"✅ **Question {idx + 1}: Correct** (Your choice: {user_ans_str})")
                    else:
                        st.markdown(f"❌ **Question {idx + 1}: Incorrect** (Your choice: {user_ans_str} | Correct answer: **{correct_ans}**)")

                    with st.expander(f"View Solution for Question {idx + 1}"):
                        p_year = os.path.join(BASE_DIR, "images", exam_year, f"q{q_id}.png") if exam_year else ""
                        if p_year and os.path.exists(p_year):
                            st.image(p_year, width=img_w)
                        st.write(q["explanation"])
                    st.markdown("---")

            # --- IF NOT SUBMITTED YET: DISPLAY QUESTIONS ---
            else:
                for idx, q in enumerate(questions):
                    q_id = q['id']
                    source_file = q.get("source_file", "")
                    exam_year = q.get("exam_year", "")
                    img_w = q.get("image_width", 300)
                    
                    st.subheader(f"Question {idx + 1} (From {source_file})")
                    st.markdown(q["question"], unsafe_allow_html=True)
                    
                    img_path = os.path.join(BASE_DIR, "images", exam_year, f"q{q_id}.png") if exam_year else ""
                    if os.path.exists(img_path):
                        st.image(img_path, width=img_w)

                    ans = st.radio(
                        f"Choose answer for Q{idx+1}:", 
                        q["options"], 
                        key=f"practice_{idx}_{q_id}", 
                        index=None,
                        label_visibility="collapsed"
                    )
                    st.session_state.practice_answers[idx] = ans
                    st.markdown("---")

                # --- BOTTOM SUBMIT BUTTON ---
                col_bot1, _ = st.columns([2, 6])
                with col_bot1:
                    if st.button("📤 Submit Practice Set (Bottom)", type="primary", use_container_width=True, key="bot_submit_practice"):
                        st.session_state.practice_submitted = True
                        st.rerun()
                st.markdown("---")
        else:
            st.info("👈 Click **'Generate New Practice Set'** in the sidebar to start practicing!")

# ==========================================
# MOCK TEST MODE
# ==========================================
elif app_mode == "📝 Mock Test":
    exam_type = st.sidebar.selectbox("Select Competition:", ["AMC 8", "SASMO", "Kangaroo"])

    keyword = exam_type.lower().replace(" ", "")
    keyword_alt = exam_type.lower().split()[0]

    test_files = [
        f for f in os.listdir(BASE_DIR) 
        if f.endswith(".json") and (keyword in f.lower().replace("-", "") or keyword_alt in f.lower())
    ]

    selected_file = st.sidebar.selectbox("Select Test Paper:", test_files) if test_files else None

    st.title(f"✍️ Mock Test: {exam_type}")

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

    if selected_file and st.session_state.current_test_file != selected_file:
        st.session_state.current_test_file = selected_file
        st.session_state.start_time = time.time()
        st.session_state.submitted = False
        st.session_state.user_answers = {}
        st.session_state.logged_mock = False

    if selected_file:
        file_path = os.path.join(BASE_DIR, selected_file)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                questions = json.load(f)
        except Exception as e:
            st.error(f"Error loading test file: {e}")
            questions = []

        year_match = re.search(r'\d{4}', selected_file)
        exam_year = year_match.group(0) if year_match else ""

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

            # --- IF SUBMITTED: SCROLL TO TOP & SHOW COMPACT RESULTS BANNER ---
            if st.session_state.submitted:
                scroll_to_top()

                score = 0
                total = len(questions)
                
                for q in questions:
                    user_ans = st.session_state.user_answers.get(q['id'])
                    if user_ans is not None and user_ans == q["answer"]:
                        score += 1

                if not st.session_state.logged_mock:
                    log_result_to_sheets(f"Mock Test - {exam_type} {exam_year}", f"{score}/{total}", user_email)
                    st.session_state.logged_mock = True

                pct = (score / total) * 100 if total > 0 else 0.0
                
                elapsed_secs = int(time.time() - st.session_state.start_time)
                m, s = divmod(elapsed_secs, 60)
                time_str = f"{m} min {s} secs" if m > 0 else f"{s} secs"

                # Compact, space-optimized results banner
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
                        p_year = os.path.join(BASE_DIR, "images", exam_year, f"q{q_id}.png") if exam_year else ""
                        if p_year and os.path.exists(p_year):
                            st.image(p_year, width=img_w)
                        st.write(q["explanation"])
                    st.markdown("---")

            # --- IF NOT SUBMITTED YET: DISPLAY TIMER & QUESTIONS ---
            else:
                time_elapsed = int(time.time() - st.session_state.start_time)
                time_left = max(0, 2400 - time_elapsed)
                mins, secs = divmod(time_left, 60)
                
                sidebar_timer_placeholder.metric(label="⏱️ Time Remaining", value=f"{mins:02d}:{secs:02d}")

                if time_left == 0:
                    st.warning("⏰ Time is up!")
                    st.session_state.submitted = True
                    st.rerun()

                for q in questions:
                    q_id = q['id']
                    img_w = q.get("image_width", 300)
                    st.subheader(f"Question {q_id}")
                    st.markdown(q["question"], unsafe_allow_html=True)
                    
                    img_path = os.path.join(BASE_DIR, "images", exam_year, f"q{q_id}.png") if exam_year else ""
                    if not img_path or not os.path.exists(img_path):
                        img_path = os.path.join(BASE_DIR, "images", f"q{q_id}.png")
                    
                    if os.path.exists(img_path):
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
# MY HISTORY TAB
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
                    clean_ts = raw_date.replace("Z", "+00:00")
                    if "T" in clean_ts:
                        dt = datetime.fromisoformat(clean_ts)
                    else:
                        clean_str = raw_date.split(".")[0]
                        dt = datetime.strptime(clean_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    
                    local_dt = dt.astimezone()
                    formatted_date = local_dt.strftime("%d-%m-%y %H:%M")
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
                "Accuracy (%)": percentage_str
            })

            # Collect data for the progress chart
            if pct_number is not None and formatted_date:
                chart_data.append({
                    "Date & Time": formatted_date,
                    "Accuracy (%)": round(pct_number, 1)
                })

        # --- RENDER PROGRESS CHART ---
        if chart_data:
            st.subheader("📈 Progress Trend Over Time")
            df_chart = pd.DataFrame(chart_data)
            st.line_chart(df_chart, x="Date & Time", y="Accuracy (%)")

        # --- RENDER DETAILED TABLE ---
        st.subheader("📋 Session Records")
        st.table(table_data)
    else:
        st.info("No history found for this email yet. Complete a test and click Submit to record your progress over time!")