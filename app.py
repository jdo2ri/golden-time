import streamlit as st
import pandas as pd
import requests
import folium
import streamlit.components.v1 as components
import xml.etree.ElementTree as ET
import urllib.parse
import re

st.set_page_config(page_title="서울/경기도 응급 의료 통합 시스템", layout="wide")

# [필수] API 키 세팅
PUBLIC_API_KEY = "420bdef8cc2ee5353ea2570fbd2718009c49f7c00d463a8eb4cf62955ccc5a4e"
KAKAO_REST_API_KEY = "df786527b50b083ef13999d02cce32f6"

# 데이터 정제
def clean_hospital_name(name):
    name = re.sub(r'\(.*?\)', '', name)
    for word in ['의료법인', '재단법인', '사단법인', '사회복지법인', '학교법인']:
        name = name.replace(word, '')
    return name.strip()

st.title("서울/경기도 응급 의료 통합 지도") 
if st.button(" 새로고침"):
    st.cache_data.clear()
    st.rerun()
st.markdown("""
<div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 15px; font-size: 15px;">
    🟢 수용 가능 응급실 (잔여 병상 1석 이상) | 🔴 수용 불가 응급실 (병상 포화, 0석)<br>
    🟠 야간 및 휴일 진료 | 🟣 심야 약국
</div>
""", unsafe_allow_html=True)

# 딱 한 번만 불러오고 12시간 동안 절대 안 변함 (속도 최적화 끝판왕)
@st.cache_data(ttl=43200)
def get_all_data(pub_key, kakao_key):
    markers = []
    headers = {"Authorization": f"KakaoAK {kakao_key}"}
    
    # 1. 응급실 데이터 (서울/경기 전체)
    url = "http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire"
    for area in ["서울특별시", "경기도"]:
        try:
            res = requests.get(url, params={"serviceKey": pub_key, "STAGE1": area, "pageNo": "1", "numOfRows": "200"}, timeout=10)
            if res.status_code == 200 and '<item>' in res.text:
                for item in ET.fromstring(res.text).findall('.//item'):
                    name = clean_hospital_name(item.findtext('dutyName'))
                    beds = int(item.findtext('hvec', '0'))
                    beds = max(0, beds)
                    
                    k_res = requests.get("https://dapi.kakao.com/v2/local/search/keyword.json", headers=headers, params={"query": name}).json()
                    if k_res.get('documents'):
                        doc = k_res['documents'][0]
                        markers.append({'lat': doc['y'], 'lon': doc['x'], 'name': name, 'color': 'green' if beds > 0 else 'red', 'type': '응급실', 'info': f"잔여 병상: {beds}석"})
        except: pass
    
    # 2. 진료/약국 (핵심만 빠르게 검색)
    queries = ["서울 야간진료", "경기 야간진료", "서울 심야약국", "경기 심야약국"]
    for q in queries:
        k_res = requests.get("https://dapi.kakao.com/v2/local/search/keyword.json", headers=headers, params={"query": q, "size": 10}).json()
        for p in k_res.get('documents', []):
            color = 'purple' if '약국' in p['place_name'] else 'orange'
            markers.append({'lat': p['y'], 'lon': p['x'], 'name': p['place_name'], 'color': color, 'type': '진료/약국', 'info': p['phone']})
            
    return markers

if PUBLIC_API_KEY.startswith("여기에") or KAKAO_REST_API_KEY.startswith("여기에"):
    st.error("API 키를 코드에 입력해주세요.")
else:
    with st.spinner("데이터 동기화 중..."):
        markers = get_all_data(PUBLIC_API_KEY, KAKAO_REST_API_KEY)
        
        m = folium.Map(location=[37.5665, 126.9780], zoom_start=10)
        for mk in markers:
            naver_url = f"https://search.naver.com/search.naver?query={urllib.parse.quote(mk['name'])}"
            # 검색 버튼 디자인 단순화
            popup_html = f'''<div style="width:200px; font-family:sans-serif;"><b>{mk['name']}</b><br>{mk['info']}<br><br><a href="{naver_url}" target="_blank">🔍 네이버 검색</a></div>'''
            folium.Marker([mk['lat'], mk['lon']], popup=folium.Popup(popup_html), icon=folium.Icon(color=mk['color'])).add_to(m)
        
        components.html(m._repr_html_(), height=750)
