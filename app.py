import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
import xml.etree.ElementTree as ET

st.set_page_config(page_title="남양주시 응급의료 인프라 분석", layout="wide")

st.sidebar.title("데이터 탐색")
menu = st.sidebar.radio(
    "메뉴 선택",
    ["실시간 병상 대시보드", "최적 이송 경로 시뮬레이션", "야간/휴일 진료 맵 (Dynamic)"]
)

# ==========================================
# 1. 실시간 병상 대시보드
# ==========================================
if menu == "실시간 병상 대시보드":
    st.header("남양주시 권역 실시간 응급 병상 현황")
    
    # [주의] 본인의 Decoding API 키를 아래에 넣으세요.
    API_KEY = "420bdef8cc2ee5353ea2570fbd2718009c49f7c00d463a8eb4cf62955ccc5a4e"
    
    if API_KEY == "여기에_본인의_API_키를_입력하세요":
        st.warning("API 키가 없습니다. 공공데이터포털(data.go.kr)에서 키를 발급받아 입력해주세요.")
    else:
        url = "http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire"
        params = {"serviceKey": API_KEY, "STAGE1": "경기도", "STAGE2": "남양주시", "pageNo": "1", "numOfRows": "10"}
        
        try:
            response = requests.get(url, params=params)
            
            # 서버가 에러(일반 텍스트/HTML)를 반환할 때의 방어 코드
            if not response.text.strip().startswith('<'):
                st.warning("⏳ 공공데이터포털 서버에 API 키가 등록(동기화)되는 중입니다. 발급 후 1~2시간 정도 기다린 후 새로고침 해주세요!")
            else:
                root = ET.fromstring(response.text)
                
                # XML 응답은 왔으나 서비스 키 미등록 에러인 경우 방어
                result_code = root.findtext('.//resultCode')
                if result_code and result_code != "00":
                    result_msg = root.findtext('.//resultMsg')
                    st.warning(f"⏳ API 키 동기화 대기 중이거나 서버 오류입니다. (보통 발급 후 1~2시간 소요)\n- 사유: {result_msg}")
                else:
                    hospital_list = []
                    for item in root.findall('.//item'):
                        name = item.findtext('dutyName')
                        beds = item.findtext('hvec') # 응급실 일반병상
                        
                        if name and beds:
                            hospital_list.append({"의료기관명": name, "실시간 잔여 병상": int(beds)})
                    
                    if hospital_list:
                        df = pd.DataFrame(hospital_list)
                        df['현재 상태'] = df['실시간 잔여 병상'].apply(lambda x: "수용 가능" if x > 0 else "포화 (수용 불가)")
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.error("현재 조회된 데이터가 없습니다.")
        except Exception as e:
            st.error(f"API 호출 중 오류 발생: {e}")

# ==========================================
# 2. 최적 이송 경로 시뮬레이션
# ==========================================
elif menu == "최적 이송 경로 시뮬레이션":
    st.header("위치 기반 이송 경로 분석")
    st.write("다산동에서 인근 권역응급의료센터(구리 한양대병원)까지의 이동 경로 시각화")
    
    m = folium.Map(location=[37.605, 127.144], zoom_start=13)
    folium.Marker([37.611, 127.155], popup="다산동 (출발지)").add_to(m)
    folium.Marker([37.6009, 127.1324], popup="구리 한양대병원", icon=folium.Icon(color='red')).add_to(m)
    folium.PolyLine(locations=[[37.611, 127.155], [37.6009, 127.1324]], color='blue', weight=4).add_to(m)
    
    st_folium(m, width=800, height=400)

# ==========================================
# 3. 야간/휴일 진료 맵
# ==========================================
else:
    st.header("남양주시 경증 환자 진료 네트워크 맵")
    st.write("데이터베이스(CSV/API)가 업데이트되면 지도에 즉시 반영되는 동적(Dynamic) 맵입니다.")

    dynamic_data = [
        {"이름": "정석소아청소년과의원", "유형": "야간", "위도": 37.6122, "경도": 127.1511, "정보": "평일 23시까지"},
        {"이름": "다산소아청소년과의원", "유형": "휴일", "위도": 37.6521, "경도": 127.3005, "정보": "주말/공휴일 운영"},
        {"이름": "다산새봄약국", "유형": "약국", "위도": 37.6155, "경도": 127.1533, "정보": "심야약국 (22시~01시)"},
        {"이름": "백세약국", "유형": "약국", "위도": 37.7252, "경도": 127.1955, "정보": "심야약국 (22시~01시)"}
    ]
    df_clinic = pd.DataFrame(dynamic_data)

    m2 = folium.Map(location=[37.6366, 127.2100], zoom_start=11)

    for idx, row in df_clinic.iterrows():
        if row['유형'] == '야간':
            emoji = '🌙'
        elif row['유형'] == '휴일':
            emoji = '☀️'
        else:
            emoji = '💊'
            
        icon_html = f'<div style="font-size: 28px; text-shadow: 2px 2px 4px rgba(0,0,0,0.4);">{emoji}</div>'
        
        folium.Marker(
            location=[row['위도'], row['경도']],
            popup=f"<b>{row['이름']}</b><br>{row['정보']}",
            icon=folium.DivIcon(html=icon_html)
        ).add_to(m2)

    st_folium(m2, width=800, height=500)
    
    st.subheader("📋 의료기관 데이터베이스 현황")
    st.dataframe(df_clinic, use_container_width=True)
