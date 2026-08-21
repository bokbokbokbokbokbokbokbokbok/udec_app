import streamlit as st
import pandas as pd
import tempfile
import io
import ezdxf
import matplotlib.pyplot as plt

# 웹 페이지 기본 설정
st.set_page_config(page_title="캐드(DXF) 맞춤형 좌표 추출기", layout="wide")

st.title("📐 캐드(DXF) 맞춤형 좌표 추출 및 미리보기")
st.markdown("""
캐드 도면(DXF)을 업로드하면 도면을 미리보기로 확인하며 레이어를 선택할 수 있습니다.
선택한 레이어는 **노란색 선**과 **표와 일치하는 청록색 고유 번호**로 표시됩니다.
""")

# 파일 업로드
uploaded_file = st.file_uploader("DXF 파일을 드래그하거나 클릭해서 업로드하세요", type=['dxf'])

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name
    
    try:
        # DXF 파일 읽기
        doc = ezdxf.readfile(tmp_path)
        msp = doc.modelspace()
        
        available_layers = set()
        all_data = []
        
        # 1. 데이터 수집 (그려진 순서 기록)
        extract_order = 0
        for entity in msp:
            if entity.dxftype() in ['POINT', 'LINE', 'LWPOLYLINE']:
                extract_order += 1  # 💡 도면에 존재하는 순서를 고유하게 기록합니다.
                layer_name = entity.dxf.layer
                available_layers.add(layer_name)
                
                if entity.dxftype() == 'POINT':
                    all_data.append({'추출순서': extract_order, '레이어': layer_name, '종류': '점(POINT)', 'X좌표': entity.dxf.location.x, 'Y좌표': entity.dxf.location.y})
                elif entity.dxftype() == 'LINE':
                    all_data.append({'추출순서': extract_order, '레이어': layer_name, '종류': '선(LINE) 시작점', 'X좌표': entity.dxf.start.x, 'Y좌표': entity.dxf.start.y})
                    all_data.append({'추출순서': extract_order, '레이어': layer_name, '종류': '선(LINE) 끝점', 'X좌표': entity.dxf.end.x, 'Y좌표': entity.dxf.end.y})
                elif entity.dxftype() == 'LWPOLYLINE':
                    for i, point in enumerate(entity.get_points()):
                        all_data.append({'추출순서': extract_order, '레이어': layer_name, '종류': f'폴리선(POLYLINE) 점{i+1}', 'X좌표': point[0], 'Y좌표': point[1]})
        
        if all_data:
            full_df = pd.DataFrame(all_data)
            full_df['X좌표'] = full_df['X좌표'].round(4)
            full_df['Y좌표'] = full_df['Y좌표'].round(4)
            
            st.divider()
            
            # 화면을 반으로 나누기
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.subheader("1️⃣ 추출할 레이어 선택")
                layer_list = sorted(list(available_layers))
                selected_layers = st.multiselect(
                    "확인하고 싶은 레이어를 선택하세요 (여러 개 선택 가능)", 
                    options=layer_list,
                    default=None 
                )
                
                st.subheader("2️⃣ 좌표 추출 결과")
                if selected_layers:
                    # 💡 가나다순 정렬로 꼬이는 현상을 막고 '추출순서'대로 정렬
                    filtered_df = full_df[full_df['레이어'].isin(selected_layers)]
                    filtered_df = filtered_df.sort_values(by=['레이어', '추출순서']).drop(columns=['추출순서']).reset_index(drop=True)
                    
                    st.success(f"선택하신 레이어에서 총 {len(filtered_df)}개의 좌표를 찾았습니다!")
                    st.dataframe(filtered_df, use_container_width=True, height=400)
                    
                    # 엑셀 다운로드
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        filtered_df.to_excel(writer, index=False, sheet_name='선택좌표데이터')
                    excel_data = output.getvalue()
                    
                    st.download_button(
                        label="📥 선택한 데이터 엑셀로 다운로드 (.xlsx)",
                        data=excel_data,
                        file_name="캐드_선택레이어_좌표.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.info("👆 위에서 추출할 레이어를 선택하시면 좌표가 표시됩니다.")

            # --- 도면 그리기 (오른쪽 화면) ---
            with col2:
                st.subheader("👀 도면 미리보기 (표 번호 연동)")
                
                fig, ax = plt.subplots(figsize=(8, 8))
                fig.patch.set_facecolor('#1E1E1E') 
                ax.set_facecolor('#1E1E1E')
                
                # 1. 도면 선 및 점 그리기
                for entity in msp:
                    if entity.dxftype() not in ['POINT', 'LINE', 'LWPOLYLINE']:
                        continue
                    
                    layer_name = entity.dxf.layer
                    is_selected = (selected_layers is not None) and (layer_name in selected_layers)
                    
                    color = 'yellow' if is_selected else 'white'
                    linewidth = 2.0 if is_selected else 0.5
                    alpha = 1.0 if is_selected else 0.2  
                    zorder = 10 if is_selected else 1    
                    
                    if entity.dxftype() == 'LINE':
                        x = [entity.dxf.start.x, entity.dxf.end.x]
                        y = [entity.dxf.start.y, entity.dxf.end.y]
                        ax.plot(x, y, color=color, linewidth=linewidth, alpha=alpha, zorder=zorder)
                    elif entity.dxftype() == 'LWPOLYLINE':
                        points = entity.get_points()
                        x = [p[0] for p in points]
                        y = [p[1] for p in points]
                        if entity.closed: 
                            x.append(x[0])
                            y.append(y[0])
                        ax.plot(x, y, color=color, linewidth=linewidth, alpha=alpha, zorder=zorder)
                    elif entity.dxftype() == 'POINT':
                        px = entity.dxf.location.x
                        py = entity.dxf.location.y
                        ax.scatter(px, py, color=color, s=15, alpha=alpha, zorder=zorder)
                
                # 2. 표 인덱스와 100% 동일한 고유 번호 매기기
                if selected_layers and not filtered_df.empty:
                    for idx, row in filtered_df.iterrows():
                        # idx는 표의 가장 왼쪽 인덱스(0, 1, 2...)입니다.
                        ax.text(row['X좌표'], row['Y좌표'], str(idx), color='cyan', fontsize=12, fontweight='bold', zorder=15)
                
                ax.set_aspect('equal', 'datalim')
                ax.axis('off')
                
                st.pyplot(fig)
                
        else:
            st.warning("도면에서 점, 선, 폴리선 객체를 하나도 찾을 수 없습니다.")
            
    except Exception as e:
        st.error(f"파일을 읽고 변환하는 중 오류가 발생했습니다: {e}")
