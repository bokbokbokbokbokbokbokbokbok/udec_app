import streamlit as st
import pandas as pd
import tempfile
import io
import ezdxf
import math
import numpy as np
import plotly.graph_objects as go

# 웹 페이지 기본 설정
st.set_page_config(page_title="캐드(DXF) 맞춤형 좌표 추출기", layout="wide")

st.title("📐 캐드(DXF) 맞춤형 좌표 추출 및 UDEC 코드 생성기")
st.markdown("""
도면(DXF)을 업로드하고 레이어를 선택하면 좌표가 추출됩니다.
터널형상(ARC) 선택 시 **호 길이에 따른 추천 절점 수(0.5m 간격 기준)를 자동 계산**하여 `arc` 명령어를 만듭니다.
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
        arc_details = {} # ARC 전용 상세 정보 저장 (중심점, 시작점, 각도, 절점수)
        
        extract_order = 0
        for entity in msp:
            if entity.dxftype() in ['POINT', 'LINE', 'LWPOLYLINE', 'ARC']:
                extract_order += 1
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
                elif entity.dxftype() == 'ARC':
                    cx, cy = entity.dxf.center.x, entity.dxf.center.y
                    r = entity.dxf.radius
                    sa = entity.dxf.start_angle
                    ea = entity.dxf.end_angle
                    
                    # 각도 차이 계산 (시계 반대 방향)
                    ang_diff = (ea - sa) % 360
                    if ang_diff == 0 and sa != ea: ang_diff = 360
                    
                    start_rad = math.radians(sa)
                    start_x = cx + r * math.cos(start_rad)
                    start_y = cy + r * math.sin(start_rad)
                    
                    # 💡 호 길이 L = 2 * pi * r * (각도 / 360)
                    arc_len = 2 * math.pi * r * (ang_diff / 360.0)
                    
                    # 💡 0.5m 단위 기본 절점수 계산 및 메뉴얼 기반 최대/최소 제한
                    calc_n = round(arc_len / 0.5)
                    if ang_diff >= 120:
                        n_nodes = min(max(calc_n, 12), 30) # 대형/반원호: 12~30개 제한
                    else:
                        n_nodes = min(max(calc_n, 3), 16)  # 소형호: 3~16개 제한
                    
                    # 표용 좌표 저장 (중심점, 시작점)
                    all_data.append({'추출순서': extract_order, '레이어': layer_name, '종류': '원호(ARC) 중심점', 'X좌표': cx, 'Y좌표': cy})
                    all_data.append({'추출순서': extract_order, '레이어': layer_name, '종류': '원호(ARC) 시작점', 'X좌표': start_x, 'Y좌표': start_y})
                    
                    # ARC 전용 입력 파라미터 묶음 저장
                    if layer_name not in arc_details:
                        arc_details[layer_name] = []
                    arc_details[layer_name].append({
                        'cx': cx, 'cy': cy,
                        'sx': start_x, 'sy': start_y,
                        'angle': ang_diff,
                        'nodes': n_nodes,
                        'length': arc_len
                    })
        
        if all_data:
            full_df = pd.DataFrame(all_data)
            full_df['X좌표'] = full_df['X좌표'].round(4)
            full_df['Y좌표'] = full_df['Y좌표'].round(4)
            
            st.divider()
            
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.subheader("1️⃣ 추출할 레이어 선택")
                layer_list = sorted(list(available_layers))
                selected_layers = st.multiselect(
                    "확인하고 싶은 레이어를 선택하세요 (여러 개 선택 가능)", 
                    options=layer_list,
                    default=None 
                )
                
                text_size = st.slider("🔍 미리보기 도면의 번호 크기 조절", min_value=5, max_value=50, value=15, step=1)
                
                if selected_layers:
                    filtered_df = full_df[full_df['레이어'].isin(selected_layers)]
                    filtered_df = filtered_df.sort_values(by=['레이어', '추출순서']).drop(columns=['추출순서'])
                    filtered_df = filtered_df.drop_duplicates(subset=['레이어', 'X좌표', 'Y좌표'], keep='first').reset_index(drop=True)
                    
                    st.subheader("2️⃣ UDEC 명령어 작성")
                    st.info("💡 **가이드:** 일반 지층 = `table1`, 전체 지반 = `bl`. **ARC(원호) 레이어**를 `arc`로 입력하면 중심점/시작점/각도/절점수가 자동으로 만들어집니다.")
                    
                    command_settings = {}
                    
                    for layer in selected_layers:
                        c_name, c_cmd, c_opt = st.columns([3, 4, 4])
                        with c_name:
                            st.markdown(f"**{layer}**")
                        with c_cmd:
                            # 레이어 이름에 '터널'이나 'arc'가 포함되면 기본값을 'arc'로 자동 세팅
                            default_cmd = "arc" if ("터널" in layer or "arc" in layer.lower()) else "table"
                            cmd_str = st.text_input("명령어 (좌표 앞)", value=default_cmd, key=f"cmd_{layer}", label_visibility="collapsed")
                        with c_opt:
                            extra_opt = st.text_input("추가 속성 (좌표 뒤)", value="", placeholder="예: 추가옵션", key=f"opt_{layer}", label_visibility="collapsed")
                            
                        command_settings[layer] = {"prefix": cmd_str, "suffix": extra_opt}
                    
                    st.write("📝 **완성된 UDEC 코드 (우측 상단 복사 버튼 클릭)**")
                    final_commands = ""
                    
                    for layer in selected_layers:
                        prefix = command_settings[layer]["prefix"].strip()
                        suffix = command_settings[layer]["suffix"].strip()
                        
                        # 💡 사용자가 명령어를 'arc'로 적었고 해당 레이어에 원호(ARC) 데이터가 존재하는 경우
                        if prefix.lower() == "arc" and layer in arc_details:
                            for arc_info in arc_details[layer]:
                                line_str = f"arc {arc_info['cx']:.4f},{arc_info['cy']:.4f} {arc_info['sx']:.4f},{arc_info['sy']:.4f} {arc_info['angle']:.1f} {arc_info['nodes']}"
                                if suffix: line_str += f" {suffix}"
                                final_commands += line_str + "\n"
                        else:
                            # 일반 명령어 (table, bl 등: 좌표 연속 나열)
                            layer_df = filtered_df[filtered_df['레이어'] == layer]
                            coords = [f"{row['X좌표']:.4f},{row['Y좌표']:.4f}" for _, row in layer_df.iterrows()]
                            coord_str = " ".join(coords)
                            line_str = f"{prefix} {coord_str}"
                            if suffix: line_str += f" {suffix}"
                            final_commands += line_str + "\n"
                    
                    st.code(final_commands, language="text")

                    # 추출된 세부 좌표 목록 표
                    st.subheader("3️⃣ 추출된 세부 좌표 목록")
                    st.success(f"총 {len(filtered_df)}개의 고유 좌표가 추출되었습니다. (왼쪽 번호 = 오른쪽 도면 번호)")
                    st.dataframe(filtered_df, use_container_width=True, height=300)
                    
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        filtered_df.to_excel(writer, index=False, sheet_name='선택좌표데이터')
                    excel_data = output.getvalue()
                    st.download_button(
                        label="📥 선택한 좌표 데이터 엑셀 다운로드 (.xlsx)",
                        data=excel_data,
                        file_name="캐드_선택레이어_좌표.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    filtered_df = pd.DataFrame() 
                    st.info("👆 위에서 추출할 레이어를 선택하시면 코드와 좌표가 표시됩니다.")

            # --- 도면 미리보기 (Plotly) ---
            with col2:
                st.subheader("👀 도면 미리보기")
                
                x_unsel, y_unsel = [], []
                x_sel, y_sel = [], []
                x_pt_unsel, y_pt_unsel = [], []
                x_pt_sel, y_pt_sel = [], []
                
                for entity in msp:
                    if entity.dxftype() not in ['POINT', 'LINE', 'LWPOLYLINE', 'ARC']:
                        continue
                    
                    layer_name = entity.dxf.layer
                    is_selected = (selected_layers is not None) and (layer_name in selected_layers)
                    
                    if entity.dxftype() == 'LINE':
                        x_coords = [entity.dxf.start.x, entity.dxf.end.x]
                        y_coords = [entity.dxf.start.y, entity.dxf.end.y]
                    elif entity.dxftype() == 'LWPOLYLINE':
                        points = entity.get_points()
                        x_coords = [p[0] for p in points]
                        y_coords = [p[1] for p in points]
                        if entity.closed:
                            x_coords.append(x_coords[0])
                            y_coords.append(y_coords[0])
                    elif entity.dxftype() == 'ARC':
                        cx, cy = entity.dxf.center.x, entity.dxf.center.y
                        r = entity.dxf.radius
                        start_ang = math.radians(entity.dxf.start_angle)
                        end_ang = math.radians(entity.dxf.end_angle)
                        if end_ang < start_ang: end_ang += 2 * math.pi
                        angles = np.linspace(start_ang, end_ang, 50)
                        x_coords = list(cx + r * np.cos(angles))
                        y_coords = list(cy + r * np.sin(angles))
                    elif entity.dxftype() == 'POINT':
                        x_coords = None 
                        if is_selected:
                            x_pt_sel.append(entity.dxf.location.x)
                            y_pt_sel.append(entity.dxf.location.y)
                        else:
                            x_pt_unsel.append(entity.dxf.location.x)
                            y_pt_unsel.append(entity.dxf.location.y)

                    if x_coords is not None:
                        if is_selected:
                            x_sel.extend(x_coords + [None])
                            y_sel.extend(y_coords + [None])
                        else:
                            x_unsel.extend(x_coords + [None])
                            y_unsel.extend(y_coords + [None])

                fig = go.Figure()

                if x_unsel:
                    fig.add_trace(go.Scatter(x=x_unsel, y=y_unsel, mode='lines', line=dict(color='white', width=1), opacity=0.2, hoverinfo='none', showlegend=False))
                if x_sel:
                    fig.add_trace(go.Scatter(x=x_sel, y=y_sel, mode='lines', line=dict(color='yellow', width=3), hoverinfo='none', showlegend=False))
                if x_pt_unsel:
                    fig.add_trace(go.Scatter(x=x_pt_unsel, y=y_pt_unsel, mode='markers', marker=dict(color='white', size=3), opacity=0.2, hoverinfo='none', showlegend=False))
                if x_pt_sel:
                    fig.add_trace(go.Scatter(x=x_pt_sel, y=y_pt_sel, mode='markers', marker=dict(color='yellow', size=6), hoverinfo='none', showlegend=False))

                if selected_layers and not filtered_df.empty:
                    fig.add_trace(go.Scatter(
                        x=filtered_df['X좌표'], 
                        y=filtered_df['Y좌표'], 
                        mode='text',
                        text=filtered_df.index.astype(str),
                        textfont=dict(color='cyan', size=text_size, family='Arial Black'), 
                        textposition='top right',
                        hoverinfo='x+y',
                        showlegend=False
                    ))

                fig.update_layout(
                    plot_bgcolor='#1E1E1E',
                    paper_bgcolor='#1E1E1E',
                    margin=dict(l=0, r=0, t=0, b=0),
                    xaxis=dict(visible=False, scaleanchor="y", scaleratio=1), 
                    yaxis=dict(visible=False),
                    dragmode='pan',
                    height=600
                )

                st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
                
        else:
            st.warning("도면에서 점, 선, 폴리선, 원호 객체를 하나도 찾을 수 없습니다.")
            
    except Exception as e:
        st.error(f"파일을 읽고 변환하는 중 오류가 발생했습니다: {e}")
