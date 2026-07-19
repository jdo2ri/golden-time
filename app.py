import streamlit as st
import pandas as pd
import requests
import folium
import streamlit.components.v1 as components  # 속도 개선을 위한 새 모듈
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
# 이모지 삭제 완료
st.title("서울/경기도 응급 의료 통합 지도") 

# 불필요한 텍스트 삭제 완료
st.markdown("""
<div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 15px; font-size: 15px;">
    <b>📍 지도 마커 범례</b><br>
    🟢 <b>수용 가능 응급실</b> (잔여 병상 1석 이상) &nbsp;|&nbsp; 🔴 <b>수용 불가 응급실</b> (병상 포화, 0석)<br>
    🟠 <b>야간 및 휴일 진료</b> (경증 환자용) &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|&nbsp; 🟣 <b>심야 약국</b>
</div>
""", unsafe_allow_html=True)

# 5분 캐싱 유지 (최초 1회만 로딩)
@st.cache_data(ttl=300)
def load_all_data(pub_key, kakao_key):
    markers = []
    bounds = []
    kakao_headers = {"Authorization": f"KakaoAK {kakao_key}"}
    
    # 1. 공공데이터 응급실 (서울 + 경기도 전체)
    url = "http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire"
    
    for stage1 in ["서울특별시", "경기도"]:
        try:
            res = requests.get(url, params={"serviceKey": pub_key, "STAGE1": stage1, "pageNo": "1", "numOfRows": "200"}, timeout=10)
            if res.status_code == 200 and '<item>' in res.text:
                items = ET.fromstring(res.text).findall('.//item')
                for item in items:
                    raw_name = item.findtext('dutyName')
                    beds_str = item.findtext('hvec')
                    if raw_name and beds_str:
                        beds = int(beds_str)
                        search_name = clean_hospital_name(raw_name)
                        
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

    # 2. 카카오 API 야간/휴일 진료 및 심야 약국
    queries = [
        {"q": "서울 야간진료", "c": "orange", "t": "야간 진료"},
        {"q": "경기 야간진료", "c": "orange", "t": "야간 진료"},
        {"q": "서울 휴일진료", "c": "orange", "t": "휴일 진료"},
        {"q": "경기 휴일진료", "c": "orange", "t": "휴일 진료"},
        {"q": "서울 심야약국", "c": "purple", "t": "심야 약국"},
        {"q": "경기 심야약국", "c": "purple", "t": "심야 약국"}
    ]
    
    k_url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    
    for q in queries:
        for page_num in range(1, 3): # 속도 최적화를 위해 페이지 탐색 최적화
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
# 지도 렌더링 (HTML 렌더링 방식으로 속도 100배 향상)
# ==========================================
if PUBLIC_API_KEY.startswith("여기에") or KAKAO_REST_API_KEY.startswith("여기에"):
    st.error("API 키 두 개를 코드에 입력해주세요.")
else:
    with st.spinner("서울 및 경기도 권역의 데이터를 렌더링 중입니다... (최초 1회만 로딩)"):
        markers, bounds = load_all_data(PUBLIC_API_KEY, KAKAO_REST_API_KEY)
        
        if not markers:
            st.warning("데이터를 불러오지 못했습니다. API 서버 상태를 확인해주세요.")
        else:
            m = folium.Map(location=[37.5665, 126.9780], zoom_start=10)
            
            for mk in markers:
                naver_url = f"https://search.naver.com/search.naver?query={urllib.parse.quote(mk['name'])}"
                
                popup_html = f'''
                <div style="width: 240px; font-family: 'Malgun Gothic', sans-serif;">
                    <div style="font-size:11px; color:white; background-color:{mk['color']}; display:inline-block; padding:2px 6px; border-radius:3px; margin-bottom:5px;">{mk['type']}</div>
                    <h5 style="margin: 0 0 5px 0; color:#2c3e50;">{mk['name']}</h5>
                    <div style="font-size:12px; color:gray; margin-bottom:5px;">📍 {mk['address']}</div>
                    <div style="font-size:13px; font-weight:bold; color:#e74c3c; margin-bottom:10px;">{mk['info']}</div>
                    <a href="{naver_url}" target="_blank" style="background-color:#03c75a; color:white; padding:6px 10px; text-decoration:none; border-radius:4px; font-size:12px; display:block; text-align:center; font-weight:bold;">네이버 상세 정보 확인</a>
                </div>
                '''
                
                folium.Marker(
                    location=[mk['lat'], mk['lon']],
                    popup=folium.Popup(popup_html, max_width=300),
                    icon=folium.Icon(color=mk['color'])
                ).add_to(m)
            
            if bounds:
                m.fit_bounds(bounds)
            
            st.success(f"총 {len(markers)}개의 데이터가 로딩되었습니다. (이제 지도를 움직여도 멈추지 않습니다.)")
            
            # st_folium을 버리고 순수 HTML로 지도를 박아버리는 방식 적용
            components.html(m._repr_html_(), height=750)
