import streamlit as st
import pandas as pd
import tempfile
import io
import ezdxf
import math
import numpy as np
import plotly.graph_objects as go
import pdfplumber # PDF 표 파싱 라이브러리

# 웹 페이지 기본 설정
st.set_page_config(page_title="UDEC 터널 & CAD 자동화 툴", layout="wide")

st.title("⛰️ UDEC 터널 모델링 & CAD 좌표 자동화 툴")
st.markdown("캐드 파일(DXF)과 물성치 파일(**PDF** / **Excel**)을 업로드하면 **UDEC 해석 코드**를 자동 생성합니다.")

# 메인 탭 구분
tab_cad, tab_prop = st.tabs(["📐 CAD 좌표 & 터널 형상화", "🧪 물성치(PDF / Excel) UDEC 변환기"])

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
                                else: x_unsel.extend(x_coords + [None]); y_unsel.extend(y_coords + [None])
                        if x_unsel: fig2.add_trace(go.Scatter(x=x_unsel, y=y_unsel, mode='lines', line=dict(color='white', width=1), opacity=0.2, showlegend=False))
                        if x_sel: fig2.add_trace(go.Scatter(x=x_sel, y=y_sel, mode='lines', line=dict(color='yellow', width=3), showlegend=False))
                        if selected_layers and not filtered_df.empty:
                            fig2.add_trace(go.Scatter(x=filtered_df['X좌표'], y=filtered_df['Y좌표'], mode='text', text=filtered_df.index.astype(str), textfont=dict(color='cyan', size=text_size, family='Arial Black'), textposition='top right', showlegend=False))
                        fig2.update_layout(plot_bgcolor='#1E1E1E', paper_bgcolor='#1E1E1E', margin=dict(l=0, r=0, t=0, b=0), xaxis=dict(visible=False, scaleanchor="y", scaleratio=1), yaxis=dict(visible=False), dragmode='pan', height=600)
                        st.plotly_chart(fig2, use_container_width=True, config={'scrollZoom': True})
        except Exception as e:
            st.error(f"DXF 읽기 오류: {e}")

# ==========================================
# 탭 2: 물성치(PDF / Excel) UDEC 변환기
# ==========================================
with tab_prop:
    st.subheader("🧪 물성치 표(PDF / Excel) ➡️ UDEC 코드 자동 변환기")
    st.markdown("지반 물성치 표가 포함된 **PDF 파일** 또는 **엑셀(.xlsx)** 파일을 업로드하세요.")
    
    prop_file = st.file_uploader("물성치 문서 업로드 (.pdf, .xlsx, .csv)", type=['pdf', 'xlsx', 'xls', 'csv'], key="prop_file_uploader")
    
    df_raw = None
    
    if prop_file is not None:
        file_ext = prop_file.name.split('.')[-1].lower()
        
        # 1. PDF 파일 파싱 (pdfplumber 활용)
        if file_ext == 'pdf':
            try:
                with pdfplumber.open(prop_file) as pdf:
                    all_tables = []
                    for page in pdf.pages:
                        tables = page.extract_tables()
                        for table in tables:
                            all_tables.extend(table)
                    
                    if all_tables:
                        df_raw = pd.DataFrame(all_tables)
                        st.success("📄 PDF 문서에서 표(Table) 데이터를 성공적으로 추출했습니다!")
                    else:
                        st.warning("PDF 문서 내부에서 표(Table) 형태의 텍스트를 찾을 수 없습니다.")
            except Exception as e:
                st.error(f"PDF 파싱 에러: {e}")
                
        # 2. 엑셀 / CSV 파일 파싱
        else:
            try:
                if file_ext == 'csv':
                    df_raw = pd.read_csv(prop_file)
                else:
                    xls = pd.ExcelFile(prop_file)
                    selected_sheet = st.selectbox("물성치 시트 선택", xls.sheet_names)
                    df_raw = pd.read_excel(prop_file, sheet_name=selected_sheet)
            except Exception as e:
                st.error(f"엑셀 파일 읽기 에러: {e}")
                
    if df_raw is not None and not df_raw.empty:
        try:
            st.markdown("### 📄 추출된 원본 표 데이터")
            st.dataframe(df_raw.head(10), use_container_width=True)
            
            st.markdown("### ⚙️ 열 매핑 (필요시 알맞은 열을 선택해 주세요)")
            cols = list(df_raw.columns)
            
            col_a, col_b, col_c, col_d, col_e, col_f, col_g = st.columns(7)
            with col_a: c_layer = st.selectbox("지층명 열", cols, index=0 if len(cols)>0 else 0)
            with col_b: c_e = st.selectbox("변형계수(E) 열", cols, index=1 if len(cols)>1 else 0)
            with col_c: c_v = st.selectbox("포아송비(v) 열", cols, index=2 if len(cols)>2 else 0)
            with col_d: c_den = st.selectbox("단위중량(den) 열", cols, index=3 if len(cols)>3 else 0)
            with col_e: c_coh = st.selectbox("점착력(coh) 열", cols, index=4 if len(cols)>4 else 0)
            with col_f: c_fr = st.selectbox("마찰각(fr) 열", cols, index=5 if len(cols)>5 else 0)
            with col_g: c_te = st.selectbox("인장강도(te) 열", cols, index=6 if len(cols)>6 else 0)
            
            df_calc = pd.DataFrame({
                '지층명': df_raw[c_layer],
                'y_mod': pd.to_numeric(df_raw[c_e], errors='coerce'),
                'p_ratio': pd.to_numeric(df_raw[c_v], errors='coerce'),
                'den': pd.to_numeric(df_raw[c_den], errors='coerce'),
                'coh': pd.to_numeric(df_raw[c_coh], errors='coerce'),
                'fr': pd.to_numeric(df_raw[c_fr], errors='coerce'),
                'te': pd.to_numeric(df_raw[c_te], errors='coerce')
            }).dropna(subset=['y_mod', 'p_ratio']).reset_index(drop=True)
            
            df_calc['mat'] = range(1, len(df_calc) + 1)
            
            # Bulk(K), Shear(G) Modulus 자동 계산
            df_calc['K'] = (df_calc['y_mod'] / (3 * (1 - 2 * df_calc['p_ratio']))).round(0).astype(int)
            df_calc['G'] = (df_calc['y_mod'] / (2 * (1 + df_calc['p_ratio']))).round(0).astype(int)
            
            st.success("🎉 Bulk Modulus(K) 및 Shear Modulus(G) 자동 계산 완료!")
            st.dataframe(df_calc[['mat', '지층명', 'y_mod', 'p_ratio', 'den', 'coh', 'fr', 'te', 'K', 'G']], use_container_width=True)
            
            st.markdown("### 📝 최종 생성된 UDEC 물성 코드 (우측 상단 복사)")
            prop_code = ""
            for _, row in df_calc.iterrows():
                mat = int(row['mat'])
                layer = row['지층명']
                prop_code += f"; --- {layer} ---\n"
                prop_code += f"set y_mod={row['y_mod']} p_ratio={row['p_ratio']}\n"
                prop_code += f"derive\n"
                prop_code += f"PROP mat={mat} den {row['den']} b={row['K']} g={row['G']} coh {row['coh']} fr {row['fr']} te {row['te']}\n"
                prop_code += f"change ins table {mat} mat={mat} cons=3\n\n"
            
            st.code(prop_code, language="text")
            
        except Exception as e:
            st.error(f"물성치 변환 오류: {e}")
