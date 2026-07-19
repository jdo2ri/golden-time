import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
import xml.etree.ElementTree as ET
import urllib.parse
import re

# 화면 넓게 쓰기
st.set_page_config(page_title="서울/경기도 응급 의료 통합 시스템", layout="wide")

# [필수] API 키 세팅
PUBLIC_API_KEY = "420bdef8cc2ee5353ea2570fbd2718009c49f7c00d463a8eb4cf62955ccc5a4e"
KAKAO_REST_API_KEY = "df786527b50b083ef13999d02cce32f6"

def clean_hospital_name(name):
    name = re.sub(r'\(.*?\)', '', name)
    for word in ['의료법인', '재단법인', '사단법인', '사회복지법인', '학교법인']:
        name = name.replace(word, '')
    return name.strip()

# ==========================================
# 통합 지도 UI 구성
# ==========================================
st.title("🚨 서울/경기도 응급 의료 통합 지도")
st.markdown("""
<div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 15px; font-size: 15px;">
    <b>📍 지도 마커 범례 (클릭 시 네이버 상세검색)</b><br>
    🟢 <b>수용 가능 응급실</b> (잔여 병상 1석 이상) &nbsp;|&nbsp; 🔴 <b>수용 불가 응급실</b> (병상 포화, 0석)<br>
    🟠 <b>야간 및 휴일 진료</b> (경증 환자용) &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|&nbsp; 🟣 <b>심야 약국</b>
</div>
""", unsafe_allow_html=True)

# 서울/경기 방대한 데이터를 가져오므로 캐싱 필수 (5분 유지)
@st.cache_data(ttl=300)
def load_all_data(pub_key, kakao_key):
    markers = []
    bounds = []
    kakao_headers = {"Authorization": f"KakaoAK {kakao_key}"}
    
    # 1. 공공데이터 응급실 (서울 + 경기도 전체)
    url = "http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire"
    
    for stage1 in ["서울특별시", "경기도"]:
        try:
            # numOfRows를 300으로 늘려 서울/경기 권역 응급실을 한 번에 다 가져옵니다.
            res = requests.get(url, params={"serviceKey": pub_key, "STAGE1": stage1, "pageNo": "1", "numOfRows": "300"}, timeout=10)
            if res.status_code == 200 and '<item>' in res.text:
                items = ET.fromstring(res.text).findall('.//item')
                for item in items:
                    raw_name = item.findtext('dutyName')
                    beds_str = item.findtext('hvec')
                    if raw_name and beds_str:
                        beds = int(beds_str)
                        search_name = clean_hospital_name(raw_name)
                        
                        # 카카오 좌표 검색
                        k_url = "https://dapi.kakao.com/v2/local/search/keyword.json"
                        k_res = requests.get(k_url, headers=kakao_headers, params={"query": search_name}).json()
                        if k_res.get('documents'):
                            lat = float(k_res['documents'][0]['y'])
                            lon = float(k_res['documents'][0]['x'])
                            address = k_res['documents'][0]['address_name']
                            
                            color = 'green' if beds > 0 else 'red'
                            status = f"잔여 병상: {beds}석 (수용 가능)" if beds > 0 else "수용 불가 (포화 상태)"
                            
                            markers.append({
                                "lat": lat, "lon": lon, "name": raw_name, "address": address,
                                "color": color, "type": "응급실", "info": status
                            })
                            bounds.append([lat, lon])
        except Exception:
            pass

    # 2. 카카오 API 야간/휴일 진료 및 심야 약국 (서울 + 경기 전체 범위)
    queries = [
        {"q": "서울 야간진료", "c": "orange", "t": "야간 진료"},
        {"q": "경기 야간진료", "c": "orange", "t": "야간 진료"},
        {"q": "서울 휴일진료", "c": "orange", "t": "휴일 진료"},
        {"q": "경기 휴일진료", "c": "orange", "t": "휴일 진료"},
        {"q": "서울 심야약국", "c": "purple", "t": "심야 약국"},
        {"q": "경기 심야약국", "c": "purple", "t": "심야 약국"}
    ]
    
    k_url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    
    # 각 키워드별로 카카오 API 데이터를 최대한 긁어옵니다. (페이지를 1~3까지 돌려서 더 넓은 범위를 커버)
    for q in queries:
        for page_num in range(1, 4):
            try:
                k_res = requests.get(k_url, headers=kakao_headers, params={"query": q["q"], "size": 15, "page": page_num}, timeout=5).json()
                for place in k_res.get('documents', []):
                    lat = float(place['y'])
                    lon = float(place['x'])
                    name = place['place_name']
                    address = place['address_name']
                    phone = place['phone'] if place['phone'] else "연락처 정보 없음"
                    
                    markers.append({
                        "lat": lat, "lon": lon, "name": name, "address": address,
                        "color": q["c"], "type": q["t"], "info": f"📞 {phone}"
                    })
                    bounds.append([lat, lon])
            except Exception:
                pass
                
    return markers, bounds

# ==========================================
# 지도 렌더링
# ==========================================
if PUBLIC_API_KEY.startswith("여기에") or KAKAO_REST_API_KEY.startswith("여기에"):
    st.error("API 키 두 개를 코드에 입력해주세요.")
else:
    with st.spinner("서울 및 경기도 전체의 응급 의료 데이터를 불러오고 있습니다... (약 10초 소요)"):
        markers, bounds = load_all_data(PUBLIC_API_KEY, KAKAO_REST_API_KEY)
        
        if not markers:
            st.warning("데이터를 불러오지 못했습니다. API 서버 상태를 확인해주세요.")
        else:
            # 기본 중심을 서울(종로구) 정도로 잡음
            m = folium.Map(location=[37.5665, 126.9780], zoom_start=10)
            
            for mk in markers:
                naver_url = f"https://search.naver.com/search.naver?query={urllib.parse.quote(mk['name'])}"
                
                # 팝업에 표시되는 '타입(mk['type'])'은 검색어가 아닌 무조건 야간진료, 휴일진료, 심야약국 등으로 고정 출력됨
                popup_html = f'''
                <div style="width: 240px; font-family: 'Malgun Gothic', sans-serif;">
                    <div style="font-size:11px; color:white; background-color:{mk['color']}; display:inline-block; padding:2px 6px; border-radius:3px; margin-bottom:5px;">{mk['type']}</div>
                    <h5 style="margin: 0 0 5px 0; color:#2c3e50;">{mk['name']}</h5>
                    <div style="font-size:12px; color:gray; margin-bottom:5px;">📍 {mk['address']}</div>
                    <div style="font-size:13px; font-weight:bold; color:#e74c3c; margin-bottom:10px;">{mk['info']}</div>
                    <a href="{naver_url}" target="_blank" style="background-color:#03c75a; color:white; padding:6px 10px; text-decoration:none; border-radius:4px; font-size:12px; display:block; text-align:center; font-weight:bold;">🔍 네이버에서 상세 정보 확인</a>
                </div>
                '''
                
                folium.Marker(
                    location=[mk['lat'], mk['lon']],
                    popup=folium.Popup(popup_html, max_width=300),
                    icon=folium.Icon(color=mk['color'])
                ).add_to(m)
            
            # 마커가 존재하는 서울/경기 권역으로 지도 뷰 자동 조절
            if bounds:
                m.fit_bounds(bounds)
            
            st.success(f"총 {len(markers)}개의 응급 의료 기관(서울+경기)을 지도에 표시했습니다.")
            st_folium(m, width=1200, height=750)
