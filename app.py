import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
import xml.etree.ElementTree as ET
import urllib.parse
import re

st.set_page_config(page_title="서울/경기도 응급 의료 통합 시스템", layout="wide")

st.sidebar.title("서울/경기도 응급 의료")
menu = st.sidebar.radio(
    "메뉴 선택",
    ["1. 실시간 응급실 병상", "2. 야간 및 휴일 진료망"]
)

# [필수] API 키 세팅
PUBLIC_API_KEY = "420bdef8cc2ee5353ea2570fbd2718009c49f7c00d463a8eb4cf62955ccc5a4e"
KAKAO_REST_API_KEY = "df786527b50b083ef13999d02cce32f6"

kakao_headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}

def clean_hospital_name(name):
    name = re.sub(r'\(.*?\)', '', name)
    for word in ['의료법인', '재단법인', '사단법인', '사회복지법인', '학교법인']:
        name = name.replace(word, '')
    return name.strip()

# ==========================================
# 1. 실시간 응급실 병상
# ==========================================
if menu == "1. 실시간 응급실 병상":
    st.header("서울/경기도 실시간 응급실 병상")
    st.markdown("""
    <div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 15px; font-size: 14px;">
        <b>지도 마커 안내:</b> 초록색(잔여 병상 1석 이상, 수용 가능) | 빨간색(잔여 병상 0석, 수용 불가)
    </div>
    """, unsafe_allow_html=True)
    
    if PUBLIC_API_KEY.startswith("여기에") or KAKAO_REST_API_KEY.startswith("여기에"):
        st.error("API 키를 코드에 입력해주세요.")
    else:
        with st.spinner("응급의료기관 데이터를 불러오는 중입니다..."):
            url = "http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire"
            
            try:
                res_nyj = requests.get(url, params={"serviceKey": PUBLIC_API_KEY, "STAGE1": "경기도", "STAGE2": "남양주시", "pageNo": "1", "numOfRows": "10"})
                res_guri = requests.get(url, params={"serviceKey": PUBLIC_API_KEY, "STAGE1": "경기도", "STAGE2": "구리시", "pageNo": "1", "numOfRows": "10"})
                
                items = []
                if res_nyj.status_code == 200 and '<item>' in res_nyj.text:
                    items.extend(ET.fromstring(res_nyj.text).findall('.//item'))
                if res_guri.status_code == 200 and '<item>' in res_guri.text:
                    items.extend(ET.fromstring(res_guri.text).findall('.//item'))
                
                if not items:
                    st.warning("공공데이터 서버에서 해당 지역의 데이터를 보내주지 않고 있습니다.")
                else:
                    m = folium.Map(location=[37.6366, 127.1723], zoom_start=11)
                    valid_count = 0
                    bounds = []
                    debug_logs = []
                    
                    for item in items:
                        raw_name = item.findtext('dutyName')
                        beds_str = item.findtext('hvec')
                        
                        if raw_name and beds_str:
                            beds = int(beds_str)
                            search_name = clean_hospital_name(raw_name)
                            
                            # [버그 수정] 한글 인코딩 에러를 막기 위해 파라미터(params) 형식으로 안전하게 전송
                            k_url = "https://dapi.kakao.com/v2/local/search/keyword.json"
                            k_res = requests.get(k_url, headers=kakao_headers, params={"query": search_name}).json()
                            
                            # [에러 추적] 카카오가 데이터를 주지 않을 경우, 그 진짜 이유를 팝업으로 띄움
                            if "documents" not in k_res:
                                st.error(f"🚨 카카오 API 접속 차단 또는 키 오류 발생: {k_res}")
                                st.stop()
                                
                            if len(k_res['documents']) > 0:
                                lat = float(k_res['documents'][0]['y'])
                                lon = float(k_res['documents'][0]['x'])
                                address = k_res['documents'][0]['address_name']
                                bounds.append([lat, lon])
                                
                                color = 'green' if beds > 0 else 'red'
                                status_text = f"<span style='color:#27ae60; font-weight:bold;'>수용 가능 (잔여: {beds}석)</span>" if beds > 0 else "<span style='color:#e74c3c; font-weight:bold;'>수용 불가 (포화)</span>"
                                    
                                naver_url = f"https://search.naver.com/search.naver?query={urllib.parse.quote(search_name)}"
                                
                                popup_html = f"""
                                <div style="width: 220px; font-family: 'Malgun Gothic', sans-serif;">
                                    <h5 style="margin: 0 0 5px 0;">{raw_name}</h5>
                                    <p style="font-size:12px; color:gray; margin:0 0 10px 0;">{address}</p>
                                    <p style="margin:0 0 10px 0; font-size:14px;">{status_text}</p>
                                    <a href="{naver_url}" target="_blank" style="background-color:#03c75a; color:white; padding:5px 10px; text-decoration:none; border-radius:4px; font-size:12px; display:block; text-align:center;">네이버 상세 검색</a>
                                </div>
                                """
                                
                                folium.Marker(
                                    location=[lat, lon],
                                    popup=folium.Popup(popup_html, max_width=300),
                                    icon=folium.Icon(color=color)
                                ).add_to(m)
                                valid_count += 1
                            else:
                                debug_logs.append(f"[{search_name}]")
                    
                    if valid_count > 0:
                        m.fit_bounds(bounds)
                        st_folium(m, width=800, height=550)
                        if debug_logs:
                            with st.expander("카카오맵에서 좌표를 찾지 못한 병원 목록 보기"):
                                st.write("해당 병원들은 카카오맵에 정식 명칭이 다르게 등록되어 있습니다:", ", ".join(debug_logs))
                    else:
                        st.warning("공공데이터(응급실 리스트)는 성공적으로 받아왔으나, 카카오맵에서 위도/경도를 단 한 건도 찾지 못했습니다.")
                        st.write("검색을 시도했던 병원 이름:", ", ".join(debug_logs))
                        
            except Exception as e:
                st.error(f"코드 에러 발생: {e}")

# ==========================================
# 2. 야간 및 휴일 진료망
# ==========================================
elif menu == "2. 야간 및 휴일 진료망":
    st.header("서울/경기도 야간 및 휴일 진료망")
    
    st.markdown("""
    <div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 15px; font-size: 14px;">
        <b>지도 마커 안내:</b> 파란색(소아과 의원) | 주황색(응급실) | 초록색(24시 약국)
    </div>
    """, unsafe_allow_html=True)
    
    if KAKAO_REST_API_KEY.startswith("여기에"):
        st.error("카카오 REST API 키를 입력해주세요.")
    else:
        with st.spinner("해당 지역의 의료기관 데이터를 수집 중입니다..."):
            m2 = folium.Map(location=[37.6000, 127.1500], zoom_start=11)
            
            # [버그 수정] 카카오맵에 100% 등록되어 있는 확실한 키워드로 변경
            search_queries = [
                {"query": "남양주 24시 약국", "color": "green"},
                {"query": "구리 24시 약국", "color": "green"},
                {"query": "남양주 소아과", "color": "blue"},
                {"query": "구리 소아과", "color": "blue"},
                {"query": "남양주 응급실", "color": "orange"},
                {"query": "구리 응급실", "color": "orange"}
            ]
            
            result_count = 0
            bounds = []
            
            k_url = "https://dapi.kakao.com/v2/local/search/keyword.json"
            
            for sq in search_queries:
                k_res = requests.get(k_url, headers=kakao_headers, params={"query": sq['query'], "size": 10}).json()
                
                # [에러 추적] 에러 시 화면에 진짜 이유 출력
                if "documents" not in k_res:
                    st.error(f"🚨 카카오 API 차단됨 (권한/설정 문제): {k_res}")
                    st.stop()
                
                for place in k_res.get('documents', []):
                    lat = float(place['y'])
                    lon = float(place['x'])
                    name = place['place_name']
                    address = place['address_name']
                    phone = place['phone'] if place['phone'] else "번호 없음"
                    
                    bounds.append([lat, lon])
                    
                    naver_url = f"https://search.naver.com/search.naver?query={urllib.parse.quote(name)}"
                    
                    popup_html = f"""
                    <div style="width: 220px; font-family: 'Malgun Gothic', sans-serif;">
                        <h5 style="margin: 0 0 5px 0;">{name}</h5>
                        <p style="font-size:12px; color:gray; margin:0 0 5px 0;">{address}</p>
                        <p style="font-size:12px; font-weight:bold; margin:0 0 10px 0;">연락처: {phone}</p>
                        <a href="{naver_url}" target="_blank" style="background-color:#03c75a; color:white; padding:5px 10px; text-decoration:none; border-radius:4px; font-size:12px; display:block; text-align:center;">네이버 상세 검색</a>
                    </div>
                    """
                    
                    folium.Marker(
                        location=[lat, lon],
                        popup=folium.Popup(popup_html, max_width=300),
                        icon=folium.Icon(color=sq['color'])
                    ).add_to(m2)
                    result_count += 1
            
            if result_count > 0:
                m2.fit_bounds(bounds) # 마커들이 다 보이게 지도 사이즈 자동 조절
                st_folium(m2, width=800, height=550)
            else:
                st.warning("현재 지도에 표시할 데이터가 없습니다.")
