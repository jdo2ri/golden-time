import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
import xml.etree.ElementTree as ET
import math
import urllib.parse

st.set_page_config(page_title="응급의료 인프라 통합 시스템", layout="wide")

st.sidebar.title("데이터 탐색")
menu = st.sidebar.radio(
    "메뉴 선택",
    ["1. 실시간 병상 맵 (Real-time)", "2. 최적 이송 경로 (Routing)", "3. 경증 환자 진료 맵 (Live)"]
)

# [필수] API 키 세팅
PUBLIC_API_KEY = "여기에_공공데이터_API_키를_넣으세요"
KAKAO_REST_API_KEY = "여기에_카카오_REST_API_키를_넣으세요"

# 카카오 API 헤더
kakao_headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}

# ==========================================
# 1. 실시간 병상 맵 (Real-time Map)
# ==========================================
if menu == "1. 실시간 병상 맵 (Real-time)":
    st.header("🏥 실시간 응급 병상 맵 (경기도/서울)")
    st.markdown("""
    <div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 15px;">
        <b>상태 범례:</b> 🟢 <b>수용 가능</b> (잔여 병상 1석 이상) | 🔴 <b>수용 불가</b> (포화 상태, 0석)
    </div>
    """, unsafe_allow_html=True)
    
    if PUBLIC_API_KEY == "여기에_공공데이터_API_키를_넣으세요" or KAKAO_REST_API_KEY == "여기에_카카오_REST_API_키를_넣으세요":
        st.error("공공데이터 API 키와 카카오 API 키가 모두 입력되어야 지도가 작동합니다.")
    else:
        with st.spinner("실시간 공공데이터와 카카오 맵 좌표를 동기화 중입니다... (약 3~5초 소요)"):
            url = "http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire"
            params = {"serviceKey": PUBLIC_API_KEY, "STAGE1": "경기도", "pageNo": "1", "numOfRows": "20"} # 속도를 위해 20개만 로드
            
            try:
                response = requests.get(url, params=params)
                root = ET.fromstring(response.text)
                
                m = folium.Map(location=[37.6, 127.15], zoom_start=11)
                valid_data_count = 0
                
                for item in root.findall('.//item'):
                    name = item.findtext('dutyName')
                    beds_str = item.findtext('hvec')
                    
                    if name and beds_str:
                        beds = int(beds_str)
                        
                        # 카카오 API로 해당 병원의 위도/경도 실시간 검색
                        k_url = f"https://dapi.kakao.com/v2/local/search/keyword.json?query={name}"
                        k_res = requests.get(k_url, headers=kakao_headers).json()
                        
                        if k_res.get('documents'):
                            lat = float(k_res['documents'][0]['y'])
                            lon = float(k_res['documents'][0]['x'])
                            address = k_res['documents'][0]['address_name']
                            
                            # 병상 수에 따른 색상 및 아이콘 결정
                            if beds > 0:
                                color = 'green'
                                status_text = f"<span style='color:#27ae60; font-weight:bold;'>수용 가능 (잔여: {beds}석)</span>"
                            else:
                                color = 'red'
                                status_text = "<span style='color:#e74c3c; font-weight:bold;'>수용 불가 (포화)</span>"
                                
                            # 네이버 검색 링크
                            naver_url = f"https://search.naver.com/search.naver?query={urllib.parse.quote(name)}"
                            
                            popup_html = f"""
                            <div style="width: 230px; font-family: 'Malgun Gothic', sans-serif;">
                                <h4 style="margin: 0 0 5px 0;">{name}</h4>
                                <p style="font-size:12px; color:gray; margin:0 0 10px 0;">{address}</p>
                                <p style="margin:0 0 10px 0; font-size:14px;">{status_text}</p>
                                <a href="{naver_url}" target="_blank" style="background-color:#03c75a; color:white; padding:5px 10px; text-decoration:none; border-radius:4px; font-size:12px; display:block; text-align:center;">🔍 네이버에서 병원 검색</a>
                            </div>
                            """
                            
                            folium.Marker(
                                location=[lat, lon],
                                popup=folium.Popup(popup_html, max_width=300),
                                icon=folium.Icon(color=color, icon='info-sign')
                            ).add_to(m)
                            valid_data_count += 1
                
                if valid_data_count > 0:
                    st_folium(m, width=800, height=550)
                    st.success(f"현재 {valid_data_count}개의 응급의료기관 실시간 데이터를 지도에 매핑했습니다.")
                else:
                    st.warning("API 데이터는 수신했으나, 지도에 표시할 병원 좌표를 찾지 못했습니다.")
                    
            except Exception as e:
                st.error("공공데이터 API 통신 중 오류가 발생했습니다. (키 동기화 대기 중일 수 있습니다.)")

# ==========================================
# 2. 최적 이송 경로 (Routing & Error Fix)
# ==========================================
elif menu == "2. 최적 이송 경로 (Routing)":
    st.header("🚑 위치 기반 실제 도로망 최적 이송 경로")
    st.write("사용자의 위치를 입력하면, **카카오 맵 API가 주변의 가장 가까운 응급실을 찾아** 경로를 안내합니다.")
    
    search_query = st.text_input("출발지 입력 (예: 남양주 다산고등학교, 내 집 주소 등)", value="남양주 다산고등학교")
    
    if st.button("가장 가까운 응급실 길찾기"):
        if KAKAO_REST_API_KEY == "여기에_카카오_REST_API_키를_넣으세요":
            st.error("카카오 REST API 키가 필요합니다.")
        else:
            with st.spinner("좌표 검색 및 최적 경로 탐색 중..."):
                # 1. 출발지 좌표 검색
                k_url = f"https://dapi.kakao.com/v2/local/search/keyword.json?query={search_query}"
                k_res = requests.get(k_url, headers=kakao_headers).json()
                
                if not k_res.get('documents'):
                    st.error("❌ 입력하신 장소를 찾을 수 없습니다. 도로명 주소나 정확한 상호명으로 다시 검색해주세요.")
                else:
                    start_lat = float(k_res['documents'][0]['y'])
                    start_lon = float(k_res['documents'][0]['x'])
                    start_name = k_res['documents'][0]['place_name']
                    
                    st.success(f"📍 출발지 확인 완료: {start_name}")
                    
                    # 2. 출발지 주변 가장 가까운 '응급실' 실시간 검색 (카카오 카테고리/키워드 혼합 검색)
                    er_url = f"https://dapi.kakao.com/v2/local/search/keyword.json?query=응급실&y={start_lat}&x={start_lon}&radius=10000&sort=distance"
                    er_res = requests.get(er_url, headers=kakao_headers).json()
                    
                    if not er_res.get('documents'):
                        st.error("반경 10km 이내에 검색되는 응급실이 없습니다.")
                    else:
                        best_hospital = er_res['documents'][0]
                        dest_lat = float(best_hospital['y'])
                        dest_lon = float(best_hospital['x'])
                        dest_name = best_hospital['place_name']
                        
                        # 3. OSRM 길찾기 API 연동
                        route_url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{dest_lon},{dest_lat}?overview=full&geometries=geojson"
                        
                        m = folium.Map(location=[start_lat, start_lon], zoom_start=13)
                        folium.Marker([start_lat, start_lon], popup=f"출발: {start_name}", icon=folium.Icon(color='blue', icon='user')).add_to(m)
                        folium.Marker([dest_lat, dest_lon], popup=f"도착: {dest_name}", icon=folium.Icon(color='red', icon='plus')).add_to(m)
                        
                        try:
                            route_res = requests.get(route_url).json()
                            if route_res.get('routes'):
                                route_geom = route_res['routes'][0]['geometry']
                                distance_km = route_res['routes'][0]['distance'] / 1000
                                duration_min = route_res['routes'][0]['duration'] / 60
                                
                                folium.GeoJson(route_geom, style_function=lambda x: {'color': '#3498db', 'weight': 6, 'opacity': 0.8}).add_to(m)
                                st.info(f"가장 가까운 응급실: **{dest_name}** | 이동 거리: **{distance_km:.1f}km** | 소요 시간: **약 {duration_min:.0f}분**")
                            else:
                                raise Exception("경로 없음")
                        except:
                            # OSRM이 뻗거나 골목길을 못 찾을 경우 멈추지 않고 직선으로 대체 (에러 방어)
                            folium.PolyLine(locations=[[start_lat, start_lon], [dest_lat, dest_lon]], color='gray', dash_array='10').add_to(m)
                            st.warning(f"가장 가까운 응급실: **{dest_name}**\n(현재 위치에서 실제 도로망 안내가 지원되지 않아 직선 경로로 표시합니다.)")
                        
                        st_folium(m, width=800, height=500)

# ==========================================
# 3. 경증 환자 진료 맵 (Live Kakao Search)
# ==========================================
else:
    st.header("🌙 경증 환자 진료 맵 (서울/경기)")
    st.write("하드코딩된 가짜 데이터가 아닙니다. 카카오 API를 통해 **현재 등록된 야간진료 의원 및 심야약국을 실시간으로 검색**하여 표시합니다.")
    
    st.markdown("""
    <div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 15px;">
        <b>분류 기준:</b> 🔵 달빛어린이병원 (소아 야간) | 🟢 심야약국 / 야간약국
    </div>
    """, unsafe_allow_html=True)
    
    if KAKAO_REST_API_KEY == "여기에_카카오_REST_API_키를_넣으세요":
        st.error("카카오 REST API 키가 필요합니다.")
    else:
        with st.spinner("카카오 맵에서 실시간 의료기관을 수집 중입니다..."):
            m2 = folium.Map(location=[37.6, 127.12], zoom_start=11)
            
            # 실시간으로 검색할 키워드들 (남양주/구리/서울 등 원하는 키워드를 넣으면 다 긁어옵니다)
            search_queries = [
                {"query": "남양주 달빛어린이병원", "color": "blue"},
                {"query": "구리 달빛어린이병원", "color": "blue"},
                {"query": "남양주 심야약국", "color": "green"},
                {"query": "구리 야간약국", "color": "green"}
            ]
            
            result_count = 0
            
            for sq in search_queries:
                k_url = f"https://dapi.kakao.com/v2/local/search/keyword.json?query={sq['query']}&size=10"
                k_res = requests.get(k_url, headers=kakao_headers).json()
                
                if k_res.get('documents'):
                    for place in k_res['documents']:
                        lat = float(place['y'])
                        lon = float(place['x'])
                        name = place['place_name']
                        address = place['address_name']
                        phone = place['phone'] if place['phone'] else "전화번호 정보 없음"
                        
                        naver_url = f"https://search.naver.com/search.naver?query={urllib.parse.quote(name)}"
                        
                        popup_html = f"""
                        <div style="width: 230px; font-family: 'Malgun Gothic', sans-serif;">
                            <h4 style="margin: 0 0 5px 0;">{name}</h4>
                            <p style="font-size:12px; color:gray; margin:0 0 5px 0;">{address}</p>
                            <p style="font-size:12px; font-weight:bold; margin:0 0 10px 0;">📞 {phone}</p>
                            <a href="{naver_url}" target="_blank" style="background-color:#03c75a; color:white; padding:5px 10px; text-decoration:none; border-radius:4px; font-size:12px; display:block; text-align:center;">🔍 네이버에서 상세 보기</a>
                        </div>
                        """
                        
                        folium.Marker(
                            location=[lat, lon],
                            popup=folium.Popup(popup_html, max_width=300),
                            icon=folium.Icon(color=sq['color'], icon='info-sign')
                        ).add_to(m2)
                        result_count += 1
            
            if result_count > 0:
                st_folium(m2, width=800, height=550)
                st.success(f"카카오 맵 API에서 실시간으로 {result_count}개의 야간/심야 의료기관을 찾아 지도에 반영했습니다.")
            else:
                st.warning("현재 검색된 결과가 없습니다.")
