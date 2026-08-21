import streamlit as st
import pandas as pd
import tempfile
import io
import ezdxf

# 웹 페이지 기본 설정
st.set_page_config(page_title="캐드(DXF) 좌표 추출기", layout="wide")

st.title("📐 캐드(DXF) 좌표 엑셀 추출기")
st.markdown("""
캐드(AutoCAD 등) 도면에서 점(Point), 선(Line), 폴리선(Polyline)의 좌표를 추출하여 엑셀로 변환해주는 툴입니다.

**사용 방법:**
1. 캐드에서 도면을 열고 `다른 이름으로 저장(Save As)`을 눌러 파일 형식을 **DXF**로 저장합니다.
2. 저장한 DXF 파일을 아래에 업로드하세요.
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
