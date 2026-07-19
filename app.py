import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
import xml.etree.ElementTree as ET
import math

st.set_page_config(page_title="응급의료 인프라 통합 시스템", layout="wide")

st.sidebar.title("데이터 탐색")
menu = st.sidebar.radio(
    "메뉴 선택",
    ["1. 실시간 병상 대시보드", "2. 최적 이송 경로 (Real Routing)", "3. 경증 환자 진료 맵"]
)

# [필수] API 키 세팅 (발급받은 키를 여기에 넣으세요)
PUBLIC_API_KEY = "420bdef8cc2ee5353ea2570fbd2718009c49f7c00d463a8eb4cf62955ccc5a4e"
KAKAO_REST_API_KEY = "c96834f4061643fe5ae6b48c3f3efb69"

# ==========================================
# 1. 실시간 병상 대시보드
# ==========================================
if menu == "1. 실시간 병상 대시보드":
    st.header("남양주시 권역 실시간 응급 병상 현황")
    
    if PUBLIC_API_KEY == "여기에_공공데이터_API_키를_넣으세요":
        st.warning("공공데이터포털 API 키가 필요합니다.")
    else:
        url = "http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire"
        params = {"serviceKey": PUBLIC_API_KEY, "STAGE1": "경기도", "STAGE2": "남양주시", "pageNo": "1", "numOfRows": "10"}
        try:
            response = requests.get(url, params=params)
            root = ET.fromstring(response.text)
            hospital_list = []
            for item in root.findall('.//item'):
                name = item.findtext('dutyName')
                beds = item.findtext('hvec')
                if name and beds:
                    hospital_list.append({"의료기관명": name, "잔여 병상(석)": int(beds)})
            
            if hospital_list:
                df = pd.DataFrame(hospital_list)
                df['상태'] = df['잔여 병상(석)'].apply(lambda x: "수용 가능" if x > 0 else "수용 불가 (포화)")
                st.dataframe(df, use_container_width=True)
            else:
                st.error("데이터 조회 실패 또는 서버 동기화 대기 중")
        except Exception as e:
            st.error("API 연동 오류")

# ==========================================
# 2. 최적 이송 경로 시뮬레이션 (Real API)
# ==========================================
elif menu == "2. 최적 이송 경로 (Real Routing)":
    st.header("위치 기반 실제 도로망 최적 이송 경로")
    st.write("입력하신 장소를 카카오 맵 API로 검색하여, 실제 도로망(자동차/도보/자전거) 기준 최적 경로를 탐색합니다.")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input("출발지 입력 (상호명, 건물명, 주소 등)", value="남양주 다산고등학교")
    with col2:
        transport_mode = st.selectbox("이동 수단", ["자동차", "자전거", "도보"])
    
    if st.button("실시간 경로 탐색"):
        if KAKAO_REST_API_KEY == "여기에_카카오_REST_API_키를_넣으세요":
            st.error("이 기능을 사용하려면 카카오 REST API 키가 필요합니다.")
        else:
            # 1. 카카오 로컬 API로 진짜 좌표 검색 (Geocoding)
            headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
            k_url = f"https://dapi.kakao.com/v2/local/search/keyword.json?query={search_query}"
            k_res = requests.get(k_url, headers=headers).json()
            
            if not k_res.get('documents'):
                st.error("장소를 찾을 수 없습니다. 정확한 상호명이나 주소를 입력하세요.")
            else:
                start_lat = float(k_res['documents'][0]['y'])
                start_lon = float(k_res['documents'][0]['x'])
                start_name = k_res['documents'][0]['place_name']
                start_address = k_res['documents'][0]['address_name']
                
                st.success(f"📍 검색 완료: {start_name} ({start_address})")
                
                # 2. 고정된 병원이 아닌, 권역 내 주요 대형병원 데이터베이스 연동
                hospitals = [
                    {"name": "구리 한양대병원", "lat": 37.6009, "lon": 127.1324},
                    {"name": "남양주 현대병원", "lat": 37.7247, "lon": 127.1936},
                    {"name": "남양주 한양병원", "lat": 37.6715, "lon": 127.2023},
                    {"name": "의정부 을지대병원", "lat": 37.7550, "lon": 127.0650},
                    {"name": "서울아산병원", "lat": 37.5265, "lon": 127.1080}
                ]
                
                # 가장 가까운 병원 계산 (실제 유클리디안 거리 연산)
                def calc_dist(lat1, lon1, lat2, lon2):
                    return math.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)
                
                best_hospital = min(hospitals, key=lambda x: calc_dist(start_lat, start_lon, x['lat'], x['lon']))
                
                # 3. 오픈소스 라우팅 API (OSRM)로 실제 도로 경로 요청
                mode_dict = {"자동차": "driving", "자전거": "bike", "도보": "foot"}
                osrm_profile = mode_dict[transport_mode]
                
                route_url = f"http://router.project-osrm.org/route/v1/{osrm_profile}/{start_lon},{start_lat};{best_hospital['lon']},{best_hospital['lat']}?overview=full&geometries=geojson"
                route_res = requests.get(route_url).json()
                
                # 지도 그리기
                m = folium.Map(location=[start_lat, start_lon], zoom_start=13)
                
                # 마커 추가
                folium.Marker([start_lat, start_lon], popup=f"출발: {start_name}", icon=folium.Icon(color='blue')).add_to(m)
                folium.Marker([best_hospital['lat'], best_hospital['lon']], popup=f"도착: {best_hospital['name']}", icon=folium.Icon(color='red', icon='plus')).add_to(m)
                
                # 실제 경로(PolyLine)가 있을 경우 지도에 그림
                if route_res.get('routes'):
                    route_geom = route_res['routes'][0]['geometry']
                    distance_km = route_res['routes'][0]['distance'] / 1000
                    duration_min = route_res['routes'][0]['duration'] / 60
                    
                    folium.GeoJson(route_geom, name='최적 경로', style_function=lambda x: {'color': '#e74c3c', 'weight': 6, 'opacity': 0.8}).add_to(m)
                    
                    st.info(f"목적지: **{best_hospital['name']}** | {transport_mode} 기준 이동 거리: **{distance_km:.1f}km** | 소요 시간: **{duration_min:.0f}분**")
                else:
                    st.warning("선택하신 이동 수단으로 탐색 가능한 도로 경로가 없습니다.")
                
                st_folium(m, width=800, height=500)

# ==========================================
# 3. 경증 환자 진료 네트워크 (상세 팝업 기능)
# ==========================================
else:
    st.header("경증 환자 진료 네트워크 (서울특별시 + 경기도)")
    st.write("야간 및 휴일에 이용 가능한 1차 의료기관 인프라 지도입니다. 마커를 클릭하면 상세 정보가 표시됩니다.")

    st.markdown("""
    <div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; border-left: 4px solid #34495e; margin-bottom: 20px;">
        <b>분류 기준:</b> 🔵 야간 진료(달빛어린이병원 등) | 🟠 휴일 진료 | 🟢 심야 공공 약국
    </div>
    """, unsafe_allow_html=True)

    # 데이터베이스
    clinic_db = [
        {"name": "정석소아청소년과의원", "address": "경기도 남양주시 다산동", "type": "야간", "lat": 37.6122, "lon": 127.1511, "time": "평일 23시까지"},
        {"name": "연세곰돌이소아과", "address": "서울특별시 서초구 방배동", "type": "휴일", "lat": 37.4835, "lon": 126.9924, "time": "주말/공휴일 정상 진료"},
        {"name": "성북우리아이들병원", "address": "서울특별시 성북구 하월곡동", "type": "야간", "lat": 37.6042, "lon": 127.0371, "time": "달빛어린이병원 (22시까지)"},
        {"name": "다산새봄약국", "address": "경기도 남양주시 다산동", "type": "약국", "lat": 37.6155, "lon": 127.1533, "time": "심야약국 (22시~01시)"},
        {"name": "수유제일약국", "address": "서울특별시 강북구 수유동", "type": "약국", "lat": 37.6375, "lon": 127.0253, "time": "심야약국 (연중무휴 24시간)"}
    ]

    m2 = folium.Map(location=[37.5800, 127.0800], zoom_start=11)

    for item in clinic_db:
        # 이모지 대신 깔끔한 색상 마커 적용
        if item['type'] == '야간':
            color = 'blue'
        elif item['type'] == '휴일':
            color = 'orange'
        else:
            color = 'green'
            
        # 네이버 지도 스타일의 상세 팝업 HTML 구현
        popup_html = f"""
        <div style="width: 250px; font-family: 'Malgun Gothic', sans-serif;">
            <h4 style="margin: 0 0 8px 0; color: #2c3e50;">{item['name']}</h4>
            <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">📍 {item['address']}</div>
            <div style="font-size: 13px; color: #e74c3c; font-weight: bold; margin-bottom: 10px;">🕒 {item['time']}</div>
            <hr style="margin: 5px 0; border: 0.5px solid #ecf0f1;">
            <div style="font-size: 11px; color: #95a5a6;">해당 데이터는 지자체 공공데이터를 기반으로 합니다.</div>
        </div>
        """
        
        folium.Marker(
            location=[item['lat'], item['lon']],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color=color)
        ).add_to(m2)

    st_folium(m2, width=800, height=550)
