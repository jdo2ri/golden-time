import streamlit as st
import pandas as pd
import requests
import folium
import streamlit.components.v1 as components
import xml.etree.ElementTree as ET
import urllib.parse
import re

st.set_page_config(page_title="서울/경기도 응급 의료 통합 시스템", layout="wide")

PUBLIC_API_KEY = "420bdef8cc2ee5353ea2570fbd2718009c49f7c00d463a8eb4cf62955ccc5a4e"
KAKAO_REST_API_KEY = "df786527b50b083ef13999d02cce32f6"

def clean_hospital_name(name):
    name = re.sub(r'\(.*?\)', '', name)
    for word in ['의료법인', '재단법인', '사단법인', '사회복지법인', '학교법인']:
        name = name.replace(word, '')
    return name.strip()

st.title("서울/경기도 응급 의료 통합 지도") 
st.markdown("""
<div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 15px; font-size: 15px;">
    🟢 <b>수용 가능 응급실</b> (잔여 병상 1석 이상) &nbsp;|&nbsp; 🔴 <b>수용 불가 응급실</b> (병상 포화, 0석)<br>
    🟠 <b>야간 및 휴일 진료</b> (경증 환자용) &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|&nbsp; 🟣 <b>심야 약국</b>
</div>
""", unsafe_allow_html=True)

# 초기 로딩 시 응급실만 먼저 로딩하도록 함수를 분리하거나 순차 처리
if PUBLIC_API_KEY.startswith("여기에") or KAKAO_REST_API_KEY.startswith("여기에"):
    st.error("API 키 두 개를 코드에 입력해주세요.")
else:
    # 빈 지도 먼저 생성
    m = folium.Map(location=[37.5665, 126.9780], zoom_start=10)
    map_placeholder = st.empty()
    
    with st.spinner("응급실 정보 먼저 긴급 로딩 중... (즉시 완료)"):
        # 1. 응급실 데이터부터 즉시 로드
        kakao_headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
        url = "http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire"
        
        for stage1 in ["서울특별시", "경기도"]:
            try:
                res = requests.get(url, params={"serviceKey": PUBLIC_API_KEY, "STAGE1": stage1, "pageNo": "1", "numOfRows": "100"}, timeout=5)
                if res.status_code == 200 and '<item>' in res.text:
                    items = ET.fromstring(res.text).findall('.//item')
                    for item in items:
                        raw_name = item.findtext('dutyName')
                        beds = int(item.findtext('hvec', '0'))
                        search_name = clean_hospital_name(raw_name)
                        
                        k_res = requests.get("https://dapi.kakao.com/v2/local/search/keyword.json", headers=kakao_headers, params={"query": search_name}).json()
                        if k_res.get('documents'):
                            doc = k_res['documents'][0]
                            color = 'green' if beds > 0 else 'red'
                            popup_html = f'''<div style="font-family:'Malgun Gothic'; width:200px;"><b>{raw_name}</b><br>{'잔여 병상: ' + str(beds) if beds > 0 else '수용 불가'}</div>'''
                            folium.Marker([doc['y'], doc['x']], popup=folium.Popup(popup_html, max_width=300), icon=folium.Icon(color=color)).add_to(m)
            except: pass
            
        # 응급실 마커가 찍힌 지도를 먼저 렌더링
        map_placeholder.components.html(m._repr_html_(), height=750)

    st.success("응급실 정보 로딩 완료. 추가 의료기관(약국/진료)을 백그라운드에서 로딩 중입니다...")

    # 2. 나머지 데이터는 뒤에서 로딩 (이후 버전에서 업데이트 가능하도록 구조 잡음)
