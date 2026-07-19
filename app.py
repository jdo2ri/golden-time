import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
import urllib.parse as urlparse
import time

st.set_page_config(page_title="Barrier Learn", layout="wide")

# ---------------------------------------------------------
# 데이터 저장소 초기화
# ---------------------------------------------------------
if 'page' not in st.session_state:
    st.session_state.page = 'main'
if 'saved_lectures' not in st.session_state:
    st.session_state.saved_lectures = {}
if 'start_time' not in st.session_state:
    st.session_state.start_time = 0
if 'comments' not in st.session_state:
    st.session_state.comments = {} 
if 'quiz_count' not in st.session_state:
    st.session_state.quiz_count = 1

def get_video_id(url):
    try:
        if "youtu.be" in url:
            return url.split("/")[-1].split("?")[0]
        elif "youtube.com" in url:
            parsed = urlparse.urlparse(url)
            return urlparse.parse_qs(parsed.query)['v'][0]
    except:
        return None
    return None

def fetch_real_subtitles(video_id):
    try:
        yt_api = YouTubeTranscriptApi()
        try:
            transcript = yt_api.list(video_id).find_transcript(['ko']).fetch()
        except:
            transcript = yt_api.fetch(video_id)

        subs = []
        for entry in transcript:
            start_val = entry.start if hasattr(entry, 'start') else entry['start']
            text_val = entry.text if hasattr(entry, 'text') else entry['text']
            start_sec = int(start_val)
            mins = start_sec // 60
            secs = start_sec % 60
            time_str = f"{mins:02d}:{secs:02d}"
            subs.append({"time": time_str, "seconds": start_sec, "text": text_val})
        return subs
    except Exception as e:
        return str(e)

# 깔끔하게 정리된 댓글창 함수
def render_comments(lecture_title, role):
    st.write("---")
    st.subheader("실시간 질문 및 소통 댓글창")
    
    if lecture_title not in st.session_state.comments:
        st.session_state.comments[lecture_title] = []
        
    with st.container(border=True):
        st.markdown("**새 댓글 작성**")
        col_name, col_text, col_btn = st.columns([2, 6, 1])
        with col_name:
            c_author = st.text_input("이름", placeholder="이름 입력", key=f"author_new_{role}", label_visibility="collapsed")
        with col_text:
            c_text = st.text_input("댓글 내용", placeholder="질문이나 의견을 남겨주세요", key=f"text_new_{role}", label_visibility="collapsed")
        with col_btn:
            if st.button("등록", key=f"btn_new_{role}", use_container_width=True):
                if c_author and c_text:
                    st.session_state.comments[lecture_title].append({
                        "id": str(time.time()),
                        "role": role,
                        "author": c_author,
                        "text": c_text,
                        "replies": []
                    })
                    st.rerun()

    st.markdown("**댓글 목록**")
    if not st.session_state.comments[lecture_title]:
        st.info("아직 작성된 댓글이 없습니다.")
        
    for c in st.session_state.comments[lecture_title]:
        with st.container(border=True):
            header_text = f"교사 ({c['author']})" if c['role'] == '교사' else f"학생 ({c['author']})"
            col_msg, col_del = st.columns([9, 1])
            with col_msg:
                st.markdown(f"**{header_text}**: {c['text']}")
            with col_del:
                if role == '교사':
                    if st.button("삭제", key=f"del_{c['id']}", use_container_width=True):
                        st.session_state.comments[lecture_title].remove(c)
                        st.rerun()
            
            if c['replies']:
                for r in c['replies']:
                    r_header = f"교사 ({r['author']})" if r['role'] == '교사' else f"학생 ({r['author']})"
                    r_col_msg, r_col_del = st.columns([9, 1])
                    with r_col_msg:
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp; └ **{r_header}**: {r['text']}")
                    with r_col_del:
                        if role == '교사':
                            if st.button("삭제", key=f"del_rep_{c['id']}_{r['id']}", help="답글 삭제"):
                                c['replies'].remove(r)
                                st.rerun()

            with st.expander("답글 달기"):
                r_col1, r_col2, r_col3 = st.columns([2, 6, 1])
                with r_col1:
                    r_auth = st.text_input("이름", key=f"r_auth_{c['id']}_{role}", label_visibility="collapsed", placeholder="이름")
                with r_col2:
                    r_txt = st.text_input("답글 내용", key=f"r_txt_{c['id']}_{role}", label_visibility="collapsed", placeholder="답글 내용")
                with r_col3:
                    if st.button("등록", key=f"r_btn_{c['id']}_{role}"):
                        if r_auth and r_txt:
                            c['replies'].append({
                                "id": str(time.time()),
                                "role": role,
                                "author": r_auth,
                                "text": r_txt
                            })
                            st.rerun()

# ---------------------------------------------------------
# 1. 첫 화면 (메인)
# ---------------------------------------------------------
if st.session_state.page == 'main':
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center;'>Barrier Learn</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>다문화 가정을 위한 배리어프리 교육 플랫폼</p>", unsafe_allow_html=True)
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns([1, 2, 2, 1])
    with col2:
        if st.button("교사용 입장", use_container_width=True):
            st.session_state.page = 'teacher'
            st.rerun()
    with col3:
        if st.button("학생용 입장", use_container_width=True):
            st.session_state.page = 'student'
            st.rerun()

# ---------------------------------------------------------
# 2. 교사용 화면
# ---------------------------------------------------------
elif st.session_state.page == 'teacher':
    if st.button("뒤로 가기"):
        st.session_state.page = 'main'
        st.session_state.start_time = 0
        st.rerun()
        
    st.subheader("[교사용] 강의 영상 업로드 및 교육 자료 생성")
    st.write("---")
    
    lecture_title = st.text_input("강의 제목", placeholder="예: 중학교 3학년 국어 - 시적 화자")
    url_input = st.text_input("유튜브 링크", placeholder="링크를 첨부해주세요")
    
    if url_input and lecture_title:
        video_id = get_video_id(url_input)
        
        if not video_id:
            st.error("올바른 유튜브 링크를 입력해주세요.")
        else:
            video_col, edit_col = st.columns([1, 1])
            
            with video_col:
                st.markdown("**영상 확인**")
                st.video(url_input, start_time=st.session_state.start_time)
                
                st.markdown("<br>**이해를 돕기 위한 언어 정리**", unsafe_allow_html=True)
                explanation_text = st.text_area("개념 설명이나 어려운 단어 뜻을 입력해주세요.", placeholder="예: 시적 화자란 시에서 말하는 사람을 뜻합니다.", height=100, label_visibility="collapsed")
                
            with edit_col:
                st.markdown("**자막 검수** (수정한 자막만 학생에게 제공됨)")
                
                if 'current_subs' not in st.session_state or st.session_state.get('current_vid') != video_id:
                    with st.spinner('자막을 불러오는 중입니다...'):
                        result = fetch_real_subtitles(video_id)
                        if isinstance(result, list):
                            st.session_state.current_subs = result
                            st.session_state.current_vid = video_id
                        else:
                            st.error(f"자막을 불러올 수 없습니다. ({result})")
                            st.session_state.current_subs = []
                
                edited_subtitles = []
                if st.session_state.current_subs:
                    with st.container(height=300):
                        for idx, sub in enumerate(st.session_state.current_subs):
                            col_btn, col_text = st.columns([2, 5])
                            with col_btn:
                                if st.button(f"{sub['time']}", key=f"btn_{idx}", use_container_width=True):
                                    st.session_state.start_time = sub['seconds']
                                    st.rerun()
                            with col_text:
                                new_text = st.text_input("수정", value=sub['text'], label_visibility="collapsed", key=f"edit_{idx}")
                                is_edited = (new_text.strip() != sub['text'].strip())
                                edited_subtitles.append({
                                    "time": sub['time'], "seconds": sub['seconds'], 
                                    "edited_text": new_text, "is_edited": is_edited
                                })
                
                st.markdown("<br>**확인 퀴즈 (O/X) 출제**", unsafe_allow_html=True)
                
                with st.container(height=300):
                    for i in range(st.session_state.quiz_count):
                        st.markdown(f"**문제 {i+1}**")
                        st.text_input(f"질문 {i+1}", key=f"q_text_{i}", placeholder="질문을 입력하세요", label_visibility="collapsed")
                        st.radio(f"정답 {i+1}", ["O", "X"], key=f"q_ans_{i}", horizontal=True, label_visibility="collapsed")
                        st.text_area(f"해설 {i+1}", key=f"q_exp_{i}", placeholder="해설을 입력하세요", height=68, label_visibility="collapsed")
                        st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
                
                if st.button("문제 추가하기", use_container_width=True):
                    st.session_state.quiz_count += 1
                    st.rerun()
                
                st.write("")
                if st.button("수정 완료 및 전체 업로드", use_container_width=True, type="primary"):
                    quiz_list = []
                    for i in range(st.session_state.quiz_count):
                        q_val = st.session_state.get(f"q_text_{i}", "")
                        a_val = st.session_state.get(f"q_ans_{i}", "O")
                        e_val = st.session_state.get(f"q_exp_{i}", "")
                        if q_val.strip(): 
                            quiz_list.append({"질문": q_val, "정답(O/X)": a_val, "해설": e_val})
                    
                    st.session_state.saved_lectures[lecture_title] = {
                        "url": url_input,
                        "subtitles": edited_subtitles,
                        "explanation_text": explanation_text,
                        "quiz": quiz_list
                    }
                    st.success("학생용 화면에 업로드되었습니다.")

    if st.session_state.saved_lectures:
        st.write("---")
        comment_lecture = st.selectbox("댓글을 확인할 강의를 선택하세요", ["(선택)"] + list(st.session_state.saved_lectures.keys()))
        if comment_lecture != "(선택)":
            render_comments(comment_lecture, role="교사")

# ---------------------------------------------------------
# 3. 학생용 화면
# ---------------------------------------------------------
elif st.session_state.page == 'student':
    if st.button("뒤로 가기"):
        st.session_state.page = 'main'
        st.session_state.start_time = 0
        st.rerun()
        
    st.subheader("[학생용] 학습 강의실")
    st.write("---")
    
    lecture_list = ["(선택)"] + list(st.session_state.saved_lectures.keys())
    lecture = st.selectbox("학습할 강의를 선택해주세요", lecture_list)
    
    if lecture != "(선택)":
        st.write("---")
        lecture_data = st.session_state.saved_lectures[lecture]
        
        video_col, text_col = st.columns([1, 1])
        
        with video_col:
            st.video(lecture_data["url"], start_time=st.session_state.start_time) 
            
            st.markdown("<br>**이해를 돕기 위한 언어 정리**", unsafe_allow_html=True)
            if lecture_data.get("explanation_text"):
                st.info(lecture_data["explanation_text"])
            else:
                st.write("등록된 설명이 없습니다.")
                
        with text_col:
            st.markdown("**맞춤형 자막 정리 노트**")
            with st.container(height=250):
                student_subs = [s for s in lecture_data["subtitles"] if s["is_edited"]]
                if not student_subs:
                    st.warning("선생님이 추가로 수정한 자막이 없습니다.")
                else:
                    for idx, sub in enumerate(student_subs):
                        col_btn, col_txt = st.columns([2, 5])
                        with col_btn:
                            if st.button(f"{sub['time']}", key=f"stu_btn_{idx}", use_container_width=True):
                                st.session_state.start_time = sub['seconds']
                                st.rerun()
                        with col_txt:
                            st.markdown(f"{sub['edited_text']}")
            
            st.markdown("<br>**배운 내용 확인 퀴즈 (O/X)**", unsafe_allow_html=True)
            quiz_data = lecture_data.get("quiz", [])
            
            if not quiz_data:
                st.write("등록된 퀴즈가 없습니다.")
            else:
                with st.form("quiz_form"):
                    user_answers = []
                    for i, q in enumerate(quiz_data):
                        st.write(f"**Q{i+1}. {q['질문']}**")
                        ans = st.radio("선택", ["O", "X"], key=f"stu_q_{i}", horizontal=True, label_visibility="collapsed")
                        user_answers.append(ans)
                        st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
                    
                    submitted = st.form_submit_button("채점하기", use_container_width=True)
                    
                if submitted:
                    score = sum(1 for i, q in enumerate(quiz_data) if user_answers[i] == q['정답(O/X)'])
                    st.success(f"점수: {score} / {len(quiz_data)}")
                    
                    for i, q in enumerate(quiz_data):
                        if user_answers[i] == q['정답(O/X)']:
                            st.info(f"Q{i+1} 정답! (정답: {q['정답(O/X)']}) \n\n 해설: {q['해설']}")
                        else:
                            st.error(f"Q{i+1} 오답! (정답: {q['정답(O/X)']}) \n\n 해설: {q['해설']}")

        render_comments(lecture, role="학생")
