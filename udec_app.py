import streamlit as st
import pandas as pd
import math
import tempfile
import io
import ezdxf

# 웹 페이지 기본 설정
st.set_page_config(page_title="UDEC & CAD 작업 간소화", layout="wide")

st.title("⛰️ UDEC 해석 모델링 & CAD 자동화 툴")
st.markdown("엑셀 수식 작업과 캐드 좌표 추출을 웹에서 한 번에 처리하세요.")

# 왼쪽 사이드바 메뉴 구성
st.sidebar.header("작업 메뉴")
menu = [
    "터널 모양 형상화", 
    "위경사 보정", 
    "물성치 (원물성치 변환)", 
    "절리군 물성치", 
    "경계면 좌표", 
    "록볼트 (Cable)", 
    "간단 수식",
    "캐드(DXF) 좌표 추출"  # <--- 새로운 메뉴 추가!
]
choice = st.sidebar.selectbox("원하는 작업을 선택하세요", menu)

# ==========================================
# 기존 UDEC 엑셀 기능들 (뼈대)
# ==========================================
if choice == "터널 모양 형상화":
    st.header("터널 모양 형상화 (arc / cr)")
    st.info("여기에 중심점, 시작점, 각도 등을 입력받아 arc 명령어를 생성하는 UI가 들어갈 예정입니다.")

elif choice == "위경사 보정":
    st.header("위경사 보정 (Apparent Dip)")
    st.info("Dip(진경사), Dip direction, Strike 등을 입력받아 보정값을 계산합니다.")

elif choice == "물성치 (원물성치 변환)":
    st.header("물성치 변환 명령어 생성")
    st.info("단위중량, 점착력, 내부마찰각 등을 입력하여 PROP 및 change 명령어를 생성합니다.")

elif choice == "절리군 물성치":
    st.header("절리군(Joint) 물성치")
    st.info("DIP, DIR, JRC, JCS 등을 입력받아 jmat 명령어를 생성합니다.")

elif choice == "경계면 좌표":
    st.header("경계면 좌표 설정")
    st.info("좌측/우측/바닥 경계면 좌표를 입력받아 bound 명령어를 만듭니다.")

elif choice == "록볼트 (Cable)":
    st.header("록볼트 (Cable) 명령어 생성")
    st.info("X, Y 좌표를 입력받아 cable 명령어를 한 줄로 출력합니다.")

elif choice == "간단 수식":
    st.header("간단 수식")
    st.info("기타 table 명령어 등 간단한 텍스트 조합을 수행합니다.")

# ==========================================
# 신규 기능: 캐드(DXF) 좌표 추출기
# ==========================================
elif choice == "캐드(DXF) 좌표 추출":
    st.header("📐 캐드(DXF) 좌표 엑셀 추출기")
    st.markdown("""
    **사용 방법:**
    1. 캐드(AutoCAD 등)에서 도면을 엽니다.
    2. `다른 이름으로 저장(Save As)`을 눌러 파일 형식을 **DXF**로 저장합니다.
    3. 저장한 DXF 파일을 아래에 업로드하세요.
    """)

    # 파일 업로드 칸 생성
    uploaded_file = st.file_uploader("DXF 파일을 드래그하거나 클릭해서 업로드하세요", type=['dxf'])

    if uploaded_file is not None:
        # 업로드된 파일을 임시 파일로 저장 (ezdxf가 읽을 수 있도록 처리)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name
        
        try:
            # DXF 파일 읽기
            doc = ezdxf.readfile(tmp_path)
            msp = doc.modelspace() # 모델 스페이스 공간 가져오기
            
            data = []
            
            # 도면 안의 객체들을 돌면서 좌표 추출
            for entity in msp:
                if entity.dxftype() == 'POINT':
                    data.append({'종류': '점(POINT)', 'X좌표': entity.dxf.location.x, 'Y좌표': entity.dxf.location.y})
                
                elif entity.dxftype() == 'LINE':
                    data.append({'종류': '선(LINE) 시작점', 'X좌표': entity.dxf.start.x, 'Y좌표': entity.dxf.start.y})
                    data.append({'종류': '선(LINE) 끝점', 'X좌표': entity.dxf.end.x, 'Y좌표': entity.dxf.end.y})
                
                elif entity.dxftype() == 'LWPOLYLINE':
                    # 폴리선은 점이 여러개이므로 반복문으로 추출
                    for i, point in enumerate(entity.get_points()):
                        data.append({'종류': f'폴리선(POLYLINE) 점{i+1}', 'X좌표': point[0], 'Y좌표': point[1]})
            
            # 추출된 데이터가 있다면 화면에 보여주고 엑셀로 변환
            if data:
                df = pd.DataFrame(data)
                
                # 소수점 4자리까지만 깔끔하게 표시
                df['X좌표'] = df['X좌표'].round(4)
                df['Y좌표'] = df['Y좌표'].round(4)

                st.success(f"🎉 성공! 총 {len(df)}개의 좌표를 추출했습니다.")
                
                # 화면에 표 형태로 띄워주기
                st.dataframe(df, use_container_width=True) 
                
                # 엑셀 다운로드 버튼 생성
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='좌표데이터')
                excel_data = output.getvalue()
                
                st.download_button(
                    label="📥 엑셀 파일로 다운로드 (.xlsx)",
                    data=excel_data,
                    file_name="캐드_좌표_추출결과.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("도면에서 점(POINT), 선(LINE), 폴리선(LWPOLYLINE) 객체를 찾을 수 없습니다.")
                
        except Exception as e:
            st.error(f"파일을 읽고 변환하는 중 오류가 발생했습니다: {e}")
