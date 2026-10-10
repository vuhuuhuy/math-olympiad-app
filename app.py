import streamlit as st
import json
import time
import os
import re
import random

st.set_page_config(page_title="Math Olympiad App", layout="wide")

# --- CUSTOM CSS ---
st.markdown(
    """
    <style>
    /* Tăng kích thước toàn bộ chữ trong ứng dụng thêm khoảng 10% để bảo vệ mắt */
    html, body, [class*="css"] {
        font-size: 17px !important;
    }

    /* Ép tăng kích thước chữ cho các lựa chọn đáp án */
    div.stRadio label p {
        font-size: 18px !important;
        font-weight: 500 !important;
    }
    
    /* Tăng kích thước các công thức toán học/phân số */
    .katex {
        font-size: 1.4em !important;
    }

    /* Đưa các lựa chọn A, B, C, D, E hiển thị trên một hàng ngang */
    div[role="radiogroup"] {
        display: flex;
        flex-direction: row;
        gap: 25px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div style='text-align: right; color: gray; font-size: 13px; margin-bottom: -20px;'>
        <em>Created by Vu Huu Huy for kids' learning</em>
    </div>
    """,
    unsafe_allow_html=True
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🏆 Math Olympiad App")
app_mode = st.sidebar.radio("Select Mode:", ["📝 Mock Test", "🎲 Practice Mode"])

# ==========================================
# MOCK TEST MODE
# ==========================================
if app_mode == "📝 Mock Test":
    exam_type = st.sidebar.selectbox("Select Competition:", ["AMC 8", "SASMO", "Kangaroo"])

    keyword = exam_type.lower().replace(" ", "")
    keyword_alt = exam_type.lower().split()[0]

    test_files = [
        f for f in os.listdir(BASE_DIR) 
        if f.endswith(".json") and (keyword in f.lower().replace("-", "") or keyword_alt in f.lower())
    ]

    if not test_files:
        st.sidebar.warning(f"No test files (.json) found for {exam_type} yet.")
        selected_file = None
    else:
        selected_file = st.sidebar.selectbox("Select Test Paper:", test_files)

    st.title(f"✍️ Mock Test: {exam_type}")

    if "start_time" not in st.session_state:
        st.session_state.start_time = None
    if "user_answers" not in st.session_state:
        st.session_state.user_answers = {}
    if "submitted" not in st.session_state:
        st.session_state.submitted = False

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
            if not st.session_state.start_time:
                if st.button("🚀 Start Test (40 Mins)"):
                    st.session_state.start_time = time.time()
                    st.session_state.submitted = False
                    st.session_state.user_answers = {}
                    st.rerun()

            # --- NÚT ĐIỀU KHIỂN TRÊN ĐẦU ---
            if st.session_state.start_time:
                st.markdown("---")
                col_space1, col_submit, col_space2, col_retake = st.columns([4, 2, 2, 2])
                
                with col_submit:
                    if not st.session_state.submitted:
                        if st.button("🔴 Submit Test", type="primary", use_container_width=True):
                            st.session_state.submitted = True
                            st.rerun()
                
                with col_retake:
                    if st.button("🔄 Retake Test", use_container_width=True):
                        st.session_state.start_time = None
                        st.session_state.submitted = False
                        st.session_state.user_answers = {}
                        st.rerun()
                st.markdown("---")
            # -----------------------------

            if st.session_state.start_time and not st.session_state.submitted:
                time_elapsed = int(time.time() - st.session_state.start_time)
                time_left = max(0, 2400 - time_elapsed)
                mins, secs = divmod(time_left, 60)
                
                timer_placeholder = st.sidebar.empty()
                timer_placeholder.metric(label="⏱️ Time Remaining", value=f"{mins:02d}:{secs:02d}")

                if time_left == 0:
                    st.warning("⏰ Time is up!")
                    st.session_state.submitted = True
                    st.rerun()

                for q in questions:
                    q_id = q['id']
                    st.subheader(f"Question {q_id}")
                    
                    st.markdown(q["question"], unsafe_allow_html=True)
                    
                    image_found = False
                    if exam_year:
                        path_by_year = os.path.join(BASE_DIR, "images", exam_year, f"q{q_id}.png")
                        if os.path.exists(path_by_year):
                            st.image(path_by_year, width=380)
                            image_found = True
                    
                    if not image_found:
                        path_general = os.path.join(BASE_DIR, "images", f"q{q_id}.png")
                        if os.path.exists(path_general):
                            st.image(path_general, width=380)
                    
                    ans = st.radio(
                        f"Choose your answer for Question {q_id}:", 
                        q["options"], 
                        key=f"q_{selected_file}_{q_id}", 
                        index=None,
                        label_visibility="collapsed"
                    )
                    st.session_state.user_answers[q_id] = ans
                    st.markdown("---")

                time.sleep(1)
                st.rerun()

            if st.session_state.submitted:
                score = 0
                total = len(questions)
                
                for q in questions:
                    if st.session_state.user_answers.get(q['id']) == q["answer"]:
                        score += 1

                st.success(f"🎉 Test submitted! Your Score: **{score}/{total}** correct answers.")

                st.markdown("### 📝 Detailed Review & Solutions")
                for q in questions:
                    q_id = q['id']
                    user_ans = st.session_state.user_answers.get(q_id, "Not answered")
                    correct_ans = q["answer"]
                    
                    if user_ans == correct_ans:
                        st.markdown(f"✅ **Question {q_id}: Correct** (Your choice: {user_ans})")
                    else:
                        st.markdown(f"❌ **Question {q_id}: Incorrect** (Your choice: {user_ans} | Correct answer: **{correct_ans}**)")
                    
                    with st.expander(f"View Solution for Question {q_id}"):
                        if exam_year:
                            p_year = os.path.join(BASE_DIR, "images", exam_year, f"q{q_id}.png")
                            if os.path.exists(p_year):
                                st.image(p_year, width=300)
                        st.write(q["explanation"])
                    st.markdown("---")

# ==========================================
# PRACTICE MODE (RANDOM QUESTIONS)
# ==========================================
elif app_mode == "🎲 Practice Mode":
    st.title("🎲 Random Practice Session")
    st.write("Practice random questions collected across all available past test papers.")

    all_json_files = [f for f in os.listdir(BASE_DIR) if f.endswith(".json")]

    if not all_json_files:
        st.warning("No test data files found in directory.")
    else:
        num_q_select = st.sidebar.slider("Select Number of Questions:", min_value=5, max_value=25, value=10, step=5)

        if "practice_questions" not in st.session_state:
            st.session_state.practice_questions = []
        if "practice_submitted" not in st.session_state:
            st.session_state.practice_submitted = False
        if "practice_answers" not in st.session_state:
            st.session_state.practice_answers = {}

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
                st.rerun()
            else:
                st.error("Could not load any questions from JSON files.")

        if st.session_state.practice_questions:
            questions = st.session_state.practice_questions

            for idx, q in enumerate(questions):
                q_id = q['id']
                source_file = q.get("source_file", "")
                exam_year = q.get("exam_year", "")
                
                st.subheader(f"Question {idx + 1} (From {source_file})")
                st.markdown(q["question"], unsafe_allow_html=True)
                
                if exam_year:
                    img_path = os.path.join(BASE_DIR, "images", exam_year, f"q{q_id}.png")
                    if os.path.exists(img_path):
                        st.image(img_path, width=380)

                ans = st.radio(
                    f"Choose answer for Q{idx+1}:", 
                    q["options"], 
                    key=f"practice_{idx}_{q_id}", 
                    index=None,
                    label_visibility="collapsed"
                )
                st.session_state.practice_answers[idx] = ans
                st.markdown("---")

            if not st.session_state.practice_submitted:
                if st.button("📤 Submit Practice Set", type="primary"):
                    st.session_state.practice_submitted = True
                    st.rerun()

            if st.session_state.practice_submitted:
                score = 0
                total = len(questions)

                for idx, q in enumerate(questions):
                    if st.session_state.practice_answers.get(idx) == q["answer"]:
                        score += 1

                st.success(f"🎯 Practice Results: **{score}/{total}** correct answers.")

                st.markdown("### 📝 Detailed Review")
                for idx, q in enumerate(questions):
                    user_ans = st.session_state.practice_answers.get(idx, "Not answered")
                    correct_ans = q["answer"]
                    q_id = q['id']
                    exam_year = q.get("exam_year", "")

                    if user_ans == correct_ans:
                        st.markdown(f"✅ **Question {idx + 1}: Correct** (Your choice: {user_ans})")
                    else:
                        st.markdown(f"❌ **Question {idx + 1}: Incorrect** (Your choice: {user_ans} | Correct answer: **{correct_ans}**)")

                    with st.expander(f"View Solution for Question {idx + 1}"):
                        if exam_year:
                            p_year = os.path.join(BASE_DIR, "images", exam_year, f"q{q_id}.png")
                            if os.path.exists(p_year):
                                st.image(p_year, width=300)
                        st.write(q["explanation"])
                    st.markdown("---")
        else:
            st.info("👈 Click **'Generate New Practice Set'** in the sidebar to start practicing!")