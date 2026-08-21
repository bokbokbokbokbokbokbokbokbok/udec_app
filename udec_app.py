import streamlit as st
import pandas as pd
import tempfile
import io
import ezdxf
import math
import numpy as np
import plotly.graph_objects as go

# 웹 페이지 기본 설정
st.set_page_config(page_title="UDEC 터널 & CAD 자동화 툴", layout="wide")

st.title("⛰️ UDEC 터널 모델링 & CAD 좌표 자동화 툴")

# 메인 탭 구별
tab_cad, tab_prop = st.tabs(["📐 CAD 좌표 & 터널 형상화", "🧪 물성치 라이브 표 입력기"])

# ==========================================
# 탭 1: CAD 좌표 및 터널 형상화
# ==========================================
with tab_cad:
    uploaded_file = st.file_uploader("DXF 파일(AutoCAD 저장)을 업로드하세요", type=['dxf'], key="dxf_uploader")

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
                        calc_n = round(arc_len / 0.5)
                        n_nodes = min(max(calc_n, 3), 30) if ang_diff >= 120 else min(max(calc_n, 3), 16)
                        
                        all_data.append({'추출순서': extract_order, '레이어': layer_name, '종류': '원호(ARC) 중심점', 'X좌표': cx, 'Y좌표': cy})
                        all_data.append({'추출순서': extract_order, '레이어': layer_name, '종류': '원호(ARC) 시작점', 'X좌표': start_x, 'Y좌표': start_y})
                        
                        if layer_name not in arc_details: arc_details[layer_name] = []
                        arc_details[layer_name].append({'cx': cx, 'cy': cy, 'sx': start_x, 'sy': start_y, 'angle': ang_diff, 'nodes': n_nodes})

            if all_data:
                full_df = pd.DataFrame(all_data)
                full_df['X좌표'] = full_df['X좌표'].round(4)
                full_df['Y좌표'] = full_df['Y좌표'].round(4)
                
                st.divider()
                sub_tab1, sub_tab2 = st.tabs(["🚇 터널 모양 형상화 (cr & arc)", "📐 일반 레이어 좌표 추출"])
                
                with sub_tab1:
                    st.subheader("🚇 터널 형상화 명령어 생성기")
                    tunnel_layer_candidates = [l for l in available_layers if "터널" in l or "tunnel" in l.lower()]
                    default_tunnel_layer = tunnel_layer_candidates[0] if tunnel_layer_candidates else sorted(list(available_layers))[0]
                    selected_tunnel_layer = st.selectbox("터널 형상이 그려진 레이어 선택", sorted(list(available_layers)), index=sorted(list(available_layers)).index(default_tunnel_layer))
                    
                    t_col1, t_col2 = st.columns([1, 1])
                    with t_col1:
                        st.markdown("### 📝 생성된 터널 명령어")
                        cr_cmds, arc_cmds = [], []
                        if selected_tunnel_layer in line_details:
                            for l in line_details[selected_tunnel_layer]: cr_cmds.append(f"cr {l['sx']:.4f},{l['sy']:.4f} {l['ex']:.4f},{l['ey']:.4f}")
                        if selected_tunnel_layer in arc_details:
                            for a in arc_details[selected_tunnel_layer]: arc_cmds.append(f"arc {a['cx']:.4f},{a['cy']:.4f} {a['sx']:.4f},{a['sy']:.4f} {a['angle']:.1f} {a['nodes']}")
                        
                        st.write("**1) 원호 구간 (arc 명령어)**")
                        st.code("\n".join(arc_cmds) if arc_cmds else "원호 요소를 찾을 수 없습니다.", language="text")
                        st.write("**2) 직선 굴착선 구간 (cr 명령어)**")
                        st.code("\n".join(cr_cmds) if cr_cmds else "직선 요소를 찾을 수 없습니다.", language="text")
                        st.write("**3) 터널 전체 통합 명령어 (arc + cr)**")
                        st.code("\n".join(arc_cmds + cr_cmds), language="text")
                    
                    with t_col2:
                        st.markdown("### 👀 터널 미리보기")
                        fig_t = go.Figure()
                        t_df = full_df[full_df['레이어'] == selected_tunnel_layer].drop_duplicates(subset=['X좌표', 'Y좌표']).reset_index(drop=True)
                        if selected_tunnel_layer in line_details:
                            for l in line_details[selected_tunnel_layer]: fig_t.add_trace(go.Scatter(x=[l['sx'], l['ex']], y=[l['sy'], l['ey']], mode='lines', line=dict(color='yellow', width=3), showlegend=False))
                        if not t_df.empty:
                            fig_t.add_trace(go.Scatter(x=t_df['X좌표'], y=t_df['Y좌표'], mode='markers+text', text=t_df.index.astype(str), textfont=dict(color='cyan', size=14, family='Arial Black'), textposition='top right', marker=dict(color='cyan', size=6), showlegend=False))
                        fig_t.update_layout(plot_bgcolor='#1E1E1E', paper_bgcolor='#1E1E1E', margin=dict(l=0, r=0, t=0, b=0), xaxis=dict(visible=False, scaleanchor="y", scaleratio=1), yaxis=dict(visible=False), dragmode='pan', height=500)
                        st.plotly_chart(fig_t, use_container_width=True, config={'scrollZoom': True})

                with sub_tab2:
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        selected_layers = st.multiselect("확인하고 싶은 레이어를 선택하세요", options=sorted(list(available_layers)), default=None, key="tab2_layers")
                        text_size = st.slider("🔍 미리보기 번호 크기", min_value=5, max_value=50, value=15, step=1, key="tab2_slider")
                        if selected_layers:
                            filtered_df = full_df[full_df['레이어'].isin(selected_layers)].sort_values(by=['레이어', '추출순서']).drop(columns=['추출순서']).drop_duplicates(subset=['레이어', 'X좌표', 'Y좌표'], keep='first').reset_index(drop=True)
                            command_settings = {}
                            for layer in selected_layers:
                                c_name, c_cmd, c_opt = st.columns([3, 4, 4])
                                with c_name: st.markdown(f"**{layer}**")
                                with c_cmd: cmd_str = st.text_input("명령어", value="table", key=f"cmd2_{layer}", label_visibility="collapsed")
                                with c_opt: extra_opt = st.text_input("추가 속성", value="", key=f"opt2_{layer}", label_visibility="collapsed")
                                command_settings[layer] = {"prefix": cmd_str, "suffix": extra_opt}
                            
                            final_commands = ""
                            for layer in selected_layers:
                                prefix, suffix = command_settings[layer]["prefix"].strip(), command_settings[layer]["suffix"].strip()
                                coords = [f"{row['X좌표']:.4f},{row['Y좌표']:.4f}" for _, row in filtered_df[filtered_df['레이어'] == layer].iterrows()]
                                line_str = f"{prefix} {' '.join(coords)}"
                                if suffix: line_str += f" {suffix}"
                                final_commands += line_str + "\n"
                            st.code(final_commands, language="text")
                            st.dataframe(filtered_df, use_container_width=True, height=300)
                        else: filtered_df = pd.DataFrame(); st.info("👆 레이어를 선택하세요.")

                    with col2:
                        fig2 = go.Figure()
                        x_unsel, y_unsel, x_sel, y_sel = [], [], [], []
                        for entity in msp:
                            if entity.dxftype() not in ['POINT', 'LINE', 'LWPOLYLINE', 'ARC']: continue
                            is_selected = (selected_layers is not None) and (entity.dxf.layer in selected_layers)
                            if entity.dxftype() == 'LINE': x_coords, y_coords = [entity.dxf.start.x, entity.dxf.end.x], [entity.dxf.start.y, entity.dxf.end.y]
                            elif entity.dxftype() == 'LWPOLYLINE':
                                points = list(entity.get_points())
                                x_coords, y_coords = [p[0] for p in points], [p[1] for p in points]
                                if entity.closed: x_coords.append(x_coords[0]); y_coords.append(y_coords[0])
                            else: x_coords = None
                            if x_coords:
                                if is_selected: x_sel.extend(x_coords + [None]); y_sel.extend(y_coords + [None])
                                else: x_unsel.extend(x_coords + [None]); y_unsel.extend(y_unsel)
                        if x_unsel: fig2.add_trace(go.Scatter(x=x_unsel, y=y_unsel, mode='lines', line=dict(color='white', width=1), opacity=0.2, showlegend=False))
                        if x_sel: fig2.add_trace(go.Scatter(x=x_sel, y=y_sel, mode='lines', line=dict(color='yellow', width=3), showlegend=False))
                        if selected_layers and not filtered_df.empty:
                            fig2.add_trace(go.Scatter(x=filtered_df['X좌표'], y=filtered_df['Y좌표'], mode='text', text=filtered_df.index.astype(str), textfont=dict(color='cyan', size=text_size, family='Arial Black'), textposition='top right', showlegend=False))
                        fig2.update_layout(plot_bgcolor='#1E1E1E', paper_bgcolor='#1E1E1E', margin=dict(l=0, r=0, t=0, b=0), xaxis=dict(visible=False, scaleanchor="y", scaleratio=1), yaxis=dict(visible=False), dragmode='pan', height=600)
                        st.plotly_chart(fig2, use_container_width=True, config={'scrollZoom': True})
        except Exception as e:
            st.error(f"DXF 읽기 오류: {e}")

# ==========================================
# 탭 2: 물성치 라이브 표 입력기 (수정 요청 반영)
# ==========================================
with tab_prop:
    st.subheader("🧪 물성치 라이브 표 입력기")
    st.markdown("""
    아래 표에서 각 항목을 직접 클릭하여 타이핑해 주세요.
    행이 모자라면 표 맨 아래 **`+` (Add row)** 버튼을 클릭하여 계속 추가할 수 있습니다.
    """)
    
    # 이미지 표 양식을 바탕으로 한 초기 기본 데이터셋
    default_prop_data = pd.DataFrame([
        {"지층명": "매립층", "단위중량": 18.0, "점착력": 5.0, "내부마찰각": 27.0, "변형계수": 10.0, "포아송비": 0.35},
        {"지층명": "퇴적모래", "단위중량": 18.5, "점착력": 0.0, "내부마찰각": 28.0, "변형계수": 20.0, "포아송비": 0.34},
        {"지층명": "풍화토,N>30", "단위중량": 19.5, "점착력": 24.0, "내부마찰각": 30.0, "변형계수": 50.0, "포아송비": 0.32},
        {"지층명": "3-2등급", "단위중량": 24.0, "점착력": 800.0, "내부마찰각": 37.0, "변형계수": 4800.0, "포아송비": 0.25},
        {"지층명": "3-1등급", "단위중량": 24.5, "점착력": 1200.0, "내부마찰각": 39.0, "변형계수": 6300.0, "포아송비": 0.24},
        {"지층명": "2-2등급", "단위중량": 25.0, "점착력": 1900.0, "내부마찰각": 41.0, "변형계수": 11000.0, "포아송비": 0.23},
        {"지층명": "2-1등급", "단위중량": 26.0, "점착력": 3100.0, "내부마찰각": 43.0, "변형계수": 14000.0, "포아송비": 0.22},
        {"지층명": "단층파쇄대", "단위중량": 21.0, "점착력": 50.0, "내부마찰각": 31.0, "변형계수": 350.0, "포아송비": 0.30},
        {"지층명": "1등급", "단위중량": 27.0, "점착력": 3800.0, "내부마찰각": 45.0, "변형계수": 23000.0, "포아송비": 0.21}
    ])
    
    # 라이브 에디터 표
    edited_df = st.data_editor(
        default_prop_data,
        num_rows="dynamic", # 💡 사용자가 자유롭게 행을 추가/삭제할 수 있음
        use_container_width=True,
        column_config={
            "지층명": st.column_config.TextColumn("지층명", help="지층 또는 암반 등급 이름을 적으세요."),
            "단위중량": st.column_config.NumberColumn("단위중량 (kN/m³)", format="%.1f"),
            "점착력": st.column_config.NumberColumn("점착력 (kPa)", format="%.1f"),
            "내부마찰각": st.column_config.NumberColumn("내부마찰각 (°)", format="%.1f"),
            "변형계수": st.column_config.NumberColumn("변형계수 (MPa)", format="%.1f"),
            "포아송비": st.column_config.NumberColumn("포아송비", format="%.2f")
        }
    )
    
    if edited_df is not None and not edited_df.empty:
        try:
            # 수치 연산을 위해 클리닝
            df_calc = edited_df.dropna(subset=['변형계수', '포아송비']).copy()
            df_calc['mat'] = range(1, len(df_calc) + 1)
            
            # UDEC 체계 단위 변환 및 K, G 자동 산정
            # 1. den: kN/m^3 -> 10^6 kg/m^3 (나누기 10000)
            df_calc['den_udec'] = (df_calc['단위중량'] / 10000.0).round(5)
            
            # 2. coh, te: kPa -> MPa (나누기 1000)
            df_calc['coh_udec'] = (df_calc['점착력'] / 1000.0).round(4)
            df_calc['te_udec'] = (df_calc['coh_udec'] / 10.0).round(4) # 인장강도는 점착력의 1/10
            
            # 3. K, G 산정
            df_calc['K'] = (df_calc['변형계수'] / (3 * (1 - 2 * df_calc['포아송비']))).round(0).astype(int)
            df_calc['G'] = (df_calc['변형계수'] / (2 * (1 + df_calc['포아송비']))).round(0).astype(int)
            
            st.divider()
            st.markdown("### 📊 자동 연산 및 계산된 결과 ($K$, $G$ 산정)")
            
            disp_df = df_calc[['mat', '지층명', '변형계수', '포아송비', 'den_udec', 'coh_udec', '내부마찰각', 'te_udec', 'K', 'G']].copy()
            disp_df.columns = ['mat', '지층명', 'E (MPa)', 'v', 'den (UDEC)', 'coh (MPa)', 'fr (°)', 'te (MPa)', 'K (Bulk)', 'G (Shear)']
            st.dataframe(disp_df, use_container_width=True)
            
            # UDEC 물성 생성 코드
            st.markdown("### 📝 최종 생성된 UDEC 물성 코드 (우측 상단 클릭 후 복사)")
            prop_code = ""
            for _, row in df_calc.iterrows():
                mat = int(row['mat'])
                layer = row['지층명']
                e_val = row['변형계수']
                v_val = row['포아송비']
                den = row['den_udec']
                k_val = row['K']
                g_val = row['G']
                coh = row['coh_udec']
                fr = row['내부마찰각']
                te = row['te_udec']
                
                prop_code += f"; --- {layer} ---\n"
                prop_code += f"set y_mod={e_val} p_ratio={v_val}\n"
                prop_code += f"derive\n"
                prop_code += f"PROP mat={mat} den {den} b={k_val} g={g_val} coh {coh} fr {fr} te {te}\n"
                prop_code += f"change ins table {mat} mat={mat} cons=3\n\n"
            
            st.code(prop_code, language="text")
            
        except Exception as e:
            st.error(f"계산 중 오류가 발생했습니다: {e}")
