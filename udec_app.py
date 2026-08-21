import streamlit as st
import pandas as pd
import tempfile
import io
import ezdxf
import math
import numpy as np
import plotly.graph_objects as go

# 웹 페이지 기본 설정
st.set_page_config(page_title="UDEC 터널 & 캐드 자동화 툴", layout="wide")

st.title("⛰️ UDEC 터널 모델링 & CAD 좌표 자동화 툴")
st.markdown("캐드 도면(DXF)을 올리면 **터널 형상화 명령어(cr, arc)**와 **지반 레이어 좌표**를 즉시 자동 생성합니다.")

# 파일 업로드
uploaded_file = st.file_uploader("DXF 파일(AutoCAD 저장)을 드래그하거나 클릭해서 업로드하세요", type=['dxf'])

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name
    
    try:
        doc = ezdxf.readfile(tmp_path)
        msp = doc.modelspace()
        
        available_layers = set()
        all_data = []
        arc_details = {}
        line_details = {}
        
        extract_order = 0
        for entity in msp:
            if entity.dxftype() in ['POINT', 'LINE', 'LWPOLYLINE', 'ARC']:
                extract_order += 1
                layer_name = entity.dxf.layer
                available_layers.add(layer_name)
                
                if entity.dxftype() == 'POINT':
                    all_data.append({'추출순서': extract_order, '레이어': layer_name, '종류': '점(POINT)', 'X좌표': entity.dxf.location.x, 'Y좌표': entity.dxf.location.y})
                
                elif entity.dxftype() == 'LINE':
                    sx, sy = entity.dxf.start.x, entity.dxf.start.y
                    ex, ey = entity.dxf.end.x, entity.dxf.end.y
                    all_data.append({'추출순서': extract_order, '레이어': layer_name, '종류': '선(LINE) 시작점', 'X좌표': sx, 'Y좌표': sy})
                    all_data.append({'추출순서': extract_order, '레이어': layer_name, '종류': '선(LINE) 끝점', 'X좌표': ex, 'Y좌표': ey})
                    
                    if layer_name not in line_details: line_details[layer_name] = []
                    line_details[layer_name].append({'sx': sx, 'sy': sy, 'ex': ex, 'ey': ey})
                    
                elif entity.dxftype() == 'LWPOLYLINE':
                    points = list(entity.get_points())
                    for i, point in enumerate(points):
                        all_data.append({'추출순서': extract_order, '레이어': layer_name, '종류': f'폴리선(POLYLINE) 점{i+1}', 'X좌표': point[0], 'Y좌표': point[1]})
                    
                    if layer_name not in line_details: line_details[layer_name] = []
                    for i in range(len(points) - 1):
                        line_details[layer_name].append({'sx': points[i][0], 'sy': points[i][1], 'ex': points[i+1][0], 'ey': points[i+1][1]})
                    if entity.closed:
                        line_details[layer_name].append({'sx': points[-1][0], 'sy': points[-1][1], 'ex': points[0][0], 'ey': points[0][1]})

                elif entity.dxftype() == 'ARC':
                    cx, cy = entity.dxf.center.x, entity.dxf.center.y
                    r = entity.dxf.radius
                    sa, ea = entity.dxf.start_angle, entity.dxf.end_angle
                    
                    ang_diff = (ea - sa) % 360
                    if ang_diff == 0 and sa != ea: ang_diff = 360
                    
                    start_rad = math.radians(sa)
                    start_x = cx + r * math.cos(start_rad)
                    start_y = cy + r * math.sin(start_rad)
                    
                    arc_len = 2 * math.pi * r * (ang_diff / 360.0)
                    calc_n = round(arc_len / 0.5) # 0.5m 간격 기준 추천 절점수
                    n_nodes = min(max(calc_n, 3), 30) if ang_diff >= 120 else min(max(calc_n, 3), 16)
                    
                    all_data.append({'추출순서': extract_order, '레이어': layer_name, '종류': '원호(ARC) 중심점', 'X좌표': cx, 'Y좌표': cy})
                    all_data.append({'추출순서': extract_order, '레이어': layer_name, '종류': '원호(ARC) 시작점', 'X좌표': start_x, 'Y좌표': start_y})
                    
                    if layer_name not in arc_details: arc_details[layer_name] = []
                    arc_details[layer_name].append({
                        'cx': cx, 'cy': cy, 'sx': start_x, 'sy': start_y,
                        'angle': ang_diff, 'nodes': n_nodes, 'length': arc_len
                    })
        
        if all_data:
            full_df = pd.DataFrame(all_data)
            full_df['X좌표'] = full_df['X좌표'].round(4)
            full_df['Y좌표'] = full_df['Y좌표'].round(4)
            
            st.divider()
            
            # 작업 모드 탭 생성 (터널 형상화 전용 / 레이어별 좌표 추출)
            tab1, tab2 = st.tabs(["🚇 터널 모양 형상화 (cr & arc)", "📐 지층/일반 레이어 좌표 추출"])
            
            # ==========================================
            # 탭 1: 터널 모양 형상화 전용
            # ==========================================
            with tab1:
                st.subheader("🚇 터널 형상화 명령어 생성기")
                tunnel_layer_candidates = [l for l in available_layers if "터널" in l or "tunnel" in l.lower()]
                default_tunnel_layer = tunnel_layer_candidates[0] if tunnel_layer_candidates else sorted(list(available_layers))[0]
                
                selected_tunnel_layer = st.selectbox("터널 형상이 그려진 레이어를 선택하세요", sorted(list(available_layers)), index=sorted(list(available_layers)).index(default_tunnel_layer))
                
                t_col1, t_col2 = st.columns([1, 1])
                
                with t_col1:
                    st.markdown("### 📝 생성된 터널 명령어 (cr & arc)")
                    
                    cr_cmds = []
                    arc_cmds = []
                    
                    # 1. cr (직선 구간)
                    if selected_tunnel_layer in line_details:
                        for l in line_details[selected_tunnel_layer]:
                            cr_cmds.append(f"cr {l['sx']:.4f},{l['sy']:.4f} {l['ex']:.4f},{l['ey']:.4f}")
                    
                    # 2. arc (원호 구간)
                    if selected_tunnel_layer in arc_details:
                        for a in arc_details[selected_tunnel_layer]:
                            arc_cmds.append(f"arc {a['cx']:.4f},{a['cy']:.4f} {a['sx']:.4f},{a['sy']:.4f} {a['angle']:.1f} {a['nodes']}")
                    
                    st.write("**1) 원호 구간 (arc 명령어)**")
                    if arc_cmds:
                        st.code("\n".join(arc_cmds), language="text")
                    else:
                        st.info("선택한 레이어에 원호(ARC) 요소를 찾을 수 없습니다.")
                        
                    st.write("**2) 직선 굴착선 구간 (cr 명령어)**")
                    if cr_cmds:
                        st.code("\n".join(cr_cmds), language="text")
                    else:
                        st.info("선택한 레이어에 직선(LINE/POLYLINE) 요소를 찾을 수 없습니다.")

                    st.write("**3) 터널 전체 통합 명령어 (arc + cr)**")
                    all_tunnel_cmds = "\n".join(arc_cmds + cr_cmds)
                    st.code(all_tunnel_cmds, language="text")
                
                # 터널 미리보기
                with t_col2:
                    st.markdown("### 👀 터널 형상 미리보기")
                    fig_t = go.Figure()
                    
                    t_df = full_df[full_df['레이어'] == selected_tunnel_layer].drop_duplicates(subset=['X좌표', 'Y좌표']).reset_index(drop=True)
                    
                    # 선 그리기
                    if selected_tunnel_layer in line_details:
                        for l in line_details[selected_tunnel_layer]:
                            fig_t.add_trace(go.Scatter(x=[l['sx'], l['ex']], y=[l['sy'], l['ey']], mode='lines', line=dict(color='yellow', width=3), showlegend=False))
                    if selected_tunnel_layer in arc_details:
                        for a in arc_details[selected_tunnel_layer]:
                            start_ang = math.atan2(a['sy'] - a['cy'], a['sx'] - a['cx'])
                            end_ang = start_ang + math.radians(a['angle'])
                            angles = np.linspace(start_ang, end_ang, 50)
                            ax_list = a['cx'] + (a['sx'] - a['cx'])/math.cos(start_ang) * np.cos(angles) if math.cos(start_rad) != 0 else a['cx'] + math.sqrt((a['sx']-a['cx'])**2 + (a['sy']-a['cy'])**2) * np.cos(angles)
                            ay_list = a['cy'] + math.sqrt((a['sx']-a['cx'])**2 + (a['sy']-a['cy'])**2) * np.sin(angles)
                            fig_t.add_trace(go.Scatter(x=ax_list, y=ay_list, mode='lines', line=dict(color='yellow', width=3), showlegend=False))
                    
                    # 좌표 점 및 번호
                    if not t_df.empty:
                        fig_t.add_trace(go.Scatter(
                            x=t_df['X좌표'], y=t_df['Y좌표'],
                            mode='markers+text',
                            text=t_df.index.astype(str),
                            textfont=dict(color='cyan', size=14, family='Arial Black'),
                            textposition='top right',
                            marker=dict(color='cyan', size=6),
                            showlegend=False
                        ))
                    
                    fig_t.update_layout(
                        plot_bgcolor='#1E1E1E', paper_bgcolor='#1E1E1E',
                        margin=dict(l=0, r=0, t=0, b=0),
                        xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
                        yaxis=dict(visible=False), dragmode='pan', height=500
                    )
                    st.plotly_chart(fig_t, use_container_width=True, config={'scrollZoom': True})

            # ==========================================
            # 탭 2: 일반 지층/레이어 좌표 추출
            # ==========================================
            with tab2:
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.subheader("1️⃣ 추출할 레이어 선택")
                    layer_list = sorted(list(available_layers))
                    selected_layers = st.multiselect("확인하고 싶은 레이어를 선택하세요", options=layer_list, default=None, key="tab2_layers")
                    
                    text_size = st.slider("🔍 미리보기 번호 크기", min_value=5, max_value=50, value=15, step=1, key="tab2_slider")
                    
                    if selected_layers:
                        filtered_df = full_df[full_df['레이어'].isin(selected_layers)]
                        filtered_df = filtered_df.sort_values(by=['레이어', '추출순서']).drop(columns=['추출순서'])
                        filtered_df = filtered_df.drop_duplicates(subset=['레이어', 'X좌표', 'Y좌표'], keep='first').reset_index(drop=True)
                        
                        st.subheader("2️⃣ UDEC 명령어 작성")
                        st.info("💡 **가이드:** 지층 = `table1`, 전체 지반 = `bl`, 원호 = `arc`, 선 = `bl`")
                        
                        command_settings = {}
                        for layer in selected_layers:
                            c_name, c_cmd, c_opt = st.columns([3, 4, 4])
                            with c_name: st.markdown(f"**{layer}**")
                            with c_cmd: cmd_str = st.text_input("명령어", value="table", key=f"cmd2_{layer}", label_visibility="collapsed")
                            with c_opt: extra_opt = st.text_input("추가 속성", value="", key=f"opt2_{layer}", label_visibility="collapsed")
                            command_settings[layer] = {"prefix": cmd_str, "suffix": extra_opt}
                        
                        st.write("📝 **완성된 UDEC 코드**")
                        final_commands = ""
                        for layer in selected_layers:
                            prefix = command_settings[layer]["prefix"].strip()
                            suffix = command_settings[layer]["suffix"].strip()
                            
                            layer_df = filtered_df[filtered_df['레이어'] == layer]
                            coords = [f"{row['X좌표']:.4f},{row['Y좌표']:.4f}" for _, row in layer_df.iterrows()]
                            coord_str = " ".join(coords)
                            line_str = f"{prefix} {coord_str}"
                            if suffix: line_str += f" {suffix}"
                            final_commands += line_str + "\n"
                        
                        st.code(final_commands, language="text")

                        st.subheader("3️⃣ 추출된 세부 좌표 목록")
                        st.dataframe(filtered_df, use_container_width=True, height=300)
                    else:
                        filtered_df = pd.DataFrame()
                        st.info("👆 레이어를 선택하세요.")

                with col2:
                    st.subheader("👀 도면 미리보기")
                    fig2 = go.Figure()
                    
                    x_unsel, y_unsel, x_sel, y_sel = [], [], [], []
                    
                    for entity in msp:
                        if entity.dxftype() not in ['POINT', 'LINE', 'LWPOLYLINE', 'ARC']: continue
                        layer_name = entity.dxf.layer
                        is_selected = (selected_layers is not None) and (layer_name in selected_layers)
                        
                        if entity.dxftype() == 'LINE':
                            x_coords = [entity.dxf.start.x, entity.dxf.end.x]
                            y_coords = [entity.dxf.start.y, entity.dxf.end.y]
                        elif entity.dxftype() == 'LWPOLYLINE':
                            points = list(entity.get_points())
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
                        else:
                            x_coords = None

                        if x_coords:
                            if is_selected: x_sel.extend(x_coords + [None]); y_sel.extend(y_coords + [None])
                            else: x_unsel.extend(x_coords + [None]); y_unsel.extend(y_coords + [None])

                    if x_unsel: fig2.add_trace(go.Scatter(x=x_unsel, y=y_unsel, mode='lines', line=dict(color='white', width=1), opacity=0.2, showlegend=False))
                    if x_sel: fig2.add_trace(go.Scatter(x=x_sel, y=y_sel, mode='lines', line=dict(color='yellow', width=3), showlegend=False))
                    
                    if selected_layers and not filtered_df.empty:
                        fig2.add_trace(go.Scatter(
                            x=filtered_df['X좌표'], y=filtered_df['Y좌표'],
                            mode='text', text=filtered_df.index.astype(str),
                            textfont=dict(color='cyan', size=text_size, family='Arial Black'),
                            textposition='top right', showlegend=False
                        ))

                    fig2.update_layout(
                        plot_bgcolor='#1E1E1E', paper_bgcolor='#1E1E1E',
                        margin=dict(l=0, r=0, t=0, b=0),
                        xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
                        yaxis=dict(visible=False), dragmode='pan', height=600
                    )
                    st.plotly_chart(fig2, use_container_width=True, config={'scrollZoom': True})

        else:
            st.warning("도면에서 객체를 찾을 수 없습니다.")
            
    except Exception as e:
        st.error(f"파일 처리 중 오류가 발생했습니다: {e}")
