import streamlit as st
import pandas as pd
import math

# 웹 페이지 기본 설정
st.set_page_config(page_title="UDEC 작업 간소화", layout="wide")

st.title("⛰️ UDEC 해석 모델링 자동화 툴")
st.markdown("엑셀에서 작업하던 명령어 생성 및 수식 계산을 웹에서 바로 처리합니다.")

# 왼쪽 사이드바 메뉴 구성 (엑셀 시트 기준)
st.sidebar.header("작업 메뉴")
menu = [
    "터널 모양 형상화", 
    "위경사 보정", 
    "물성치 (원물성치 변환)", 
    "절리군 물성치", 
    "경계면 좌표", 
    "록볼트 (Cable)", 
    "간단 수식"
]
choice = st.sidebar.selectbox("원하는 작업을 선택하세요", menu)

# 1. 터널 모양 형상화
if choice == "터널 모양 형상화":
    st.header("터널 모양 형상화 (arc / cr)")
    st.info("여기에 중심점, 시작점, 각도 등을 입력받아 arc 명령어를 생성하는 UI가 들어갈 예정입니다.")

# 2. 위경사 보정
elif choice == "위경사 보정":
    st.header("위경사 보정 (Apparent Dip)")
    st.info("Dip(진경사), Dip direction, Strike 등을 입력받아 보정값을 계산합니다.")

# 3. 물성치
elif choice == "물성치 (원물성치 변환)":
    st.header("물성치 변환 명령어 생성")
    st.info("단위중량, 점착력, 내부마찰각 등을 입력하여 PROP 및 change 명령어를 생성합니다.")

# 4. 절리군 물성치
elif choice == "절리군 물성치":
    st.header("절리군(Joint) 물성치")
    st.info("DIP, DIR, JRC, JCS 등을 입력받아 jmat 명령어를 생성합니다.")

# 5. 경계면 좌표
elif choice == "경계면 좌표":
    st.header("경계면 좌표 설정")
    st.info("좌측/우측/바닥 경계면 좌표를 입력받아 bound 명령어를 만듭니다.")

# 6. 록볼트
elif choice == "록볼트 (Cable)":
    st.header("록볼트 (Cable) 명령어 생성")
    st.info("X, Y 좌표를 입력받아 cable 명령어를 한 줄로 출력합니다.")

# 7. 간단 수식
elif choice == "간단 수식":
    st.header("간단 수식")
    st.info("기타 table 명령어 등 간단한 텍스트 조합을 수행합니다.")
