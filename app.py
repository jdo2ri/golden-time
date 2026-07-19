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
KAKAO_REST_API_KEY = "c96834f4061643fe5ae6b48c3f3efb69"

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
    
    if PUBLIC_API_KEY == "여기에_공공데이터_API_키를_넣으세요" or KAKAO_REST_API_KEY == "여기에_카카오_REST_API_키를_넣으세요":
        st.error("공공데이터 API 키와 카카오 API 키를 코드에 입력해야 지도가 작동합니다.")
    else:
        with st.spinner("응급의료기관 데이터를 불러오는 중입니다..."):
            # 남양주와 구리 데이터를 확실하게 가져오기 위해 지역을 지정
            url = "http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire"
            
            try:
                # 남양주시 데이터 호출
                res_nyj = requests.get(url, params={"serviceKey": PUBLIC_API_KEY, "STAGE1": "경기도", "STAGE2": "남양주시", "pageNo": "1", "numOfRows": "10"})
                # 구리시 데이터 호출
                res_guri = requests.get(url, params={"serviceKey": PUBLIC_API_KEY, "STAGE1": "경기도", "STAGE2": "구리시", "pageNo": "1", "numOfRows": "10"})
                
                items = []
                if res_nyj.status_code == 200 and res_nyj.text.strip().startswith('<'):
                    items.extend(ET.fromstring(res_nyj.text).findall('.//item'))
                if res_guri.status_code == 200 and res_guri.text.strip().startswith('<'):
                    items.extend(ET.fromstring(res_guri.text).findall('.//item'))
                
                if not items:
                    st.warning("공공데이터 서버에서 해당 지역의 응급실 데이터를 주지 않고 있습니다. (API 키 동기화 대기 중일 수 있습니다)")
                else:
                    m = folium.Map(location=[37.6366, 127.1723], zoom_start=11)
                    valid_count = 0
                    bounds = []
                    
                    for item in items:
                        raw_name = item.findtext('dutyName')
                        beds_str = item.findtext('hvec')
                        
                        if raw_name and beds_str:
                            beds = int(beds_str)
                            search_name = clean_hospital_name(raw_name)
                            
                            # 카카오 API 좌표 검색
                            k_url = f"https://dapi.kakao.com/v2/local/search/keyword.json?query={search_name}"
                            k_res = requests.get(k_url, headers=kakao_headers).json()
                            
                            # 카카오 API 에러 원인 즉시 파악 로직
                            if k_res.get("code") == -401:
                                st.error("🚨 카카오 REST API 키가 잘못되었습니다. (카카오 디벨로퍼스에서 반드시 'REST API 키'를 복사했는지 확인해주세요!)")
                                st.stop()
                                
                            if k_res.get('documents'):
                                lat = float(k_res['documents'][0]['y'])
                                lon = float(k_res['documents'][0]['x'])
                                address = k_res['documents'][0]['address_name']
                                bounds.append([lat, lon])
                                
                                if beds > 0:
                                    color = 'green'
                                    status_text = f"<span style='color:#27ae60; font-weight:bold;'>수용 가능 (잔여: {beds}석)</span>"
                                else:
                                    color = 'red'
                                    status_text = "<span style='color:#e74c3c; font-weight:bold;'>수용 불가 (포화)</span>"
                                    
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
                    
                    if valid_count > 0:
                        m.fit_bounds(bounds) # 병원들이 다 보이도록 지도 시야 자동 조절
                        st_folium(m, width=800, height=550)
                    else:
                        st.warning("응급실 이름으로 위도/경도를 찾지 못했습니다. 카카오 맵 검색결과가 없습니다.")
                        
            except Exception as e:
                st.error(f"공공데이터 서버 통신 에러: {e}")

# ==========================================
# 2. 야간 및 휴일 진료망
# ==========================================
elif menu == "2. 야간 및 휴일 진료망":
    st.header("서울/경기도 야간 및 휴일 진료망")
    
    # 📌 휴일 진료(주황색) 범례 확실하게 추가 완료
    st.markdown("""
    <div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 15px; font-size: 14px;">
        <b>지도 마커 안내:</b> 파란색(야간 진료 의원) | 주황색(휴일 진료 의원) | 초록색(심야 약국)
    </div>
    """, unsafe_allow_html=True)
    
    if KAKAO_REST_API_KEY == "여기에_카카오_REST_API_키를_넣으세요":
        st.error("카카오 REST API 키를 입력해야 지도가 렌더링됩니다.")
    else:
        with st.spinner("해당 지역의 야간/휴일 의료기관 데이터를 수집 중입니다..."):
            m2 = folium.Map(location=[37.6000, 127.1500], zoom_start=11)
            
            # 📌 검색어에 '휴일진료' 추가 완료
            search_queries = [
                {"query": "남양주 야간진료", "color": "blue"},
                {"query": "남양주 휴일진료", "color": "orange"},
                {"query": "남양주 심야약국", "color": "green"},
                {"query": "구리 야간진료", "color": "blue"},
                {"query": "구리 휴일진료", "color": "orange"},
                {"query": "구리 심야약국", "color": "green"}
            ]
            
            result_count = 0
            bounds = []
            
            for sq in search_queries:
                k_url = f"https://dapi.kakao.com/v2/local/search/keyword.json?query={sq['query']}&size=10"
                k_res = requests.get(k_url, headers=kakao_headers).json()
                
                # 에러 감지
                if k_res.get("code") == -401:
                    st.error("🚨 카카오 REST API 키가 올바르지 않습니다. 카카오 디벨로퍼스에서 키를 다시 확인해주세요.")
                    st.stop()
                
                if k_res.get('documents'):
                    for place in k_res['documents']:
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
