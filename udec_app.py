import streamlit as st
import pandas as pd
import tempfile
import io
import ezdxf
import math
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="UDEC 모델링 & CAD 자동화 툴", layout="wide")

st.title("⛰️ UDEC 터널 모델링 & CAD 좌표 자동화 툴")

uploaded_file = st.file_uploader("DXF 파일(AutoCAD 저장)을 업로드하세요", type=['dxf'])

# 상단 메인 탭 구성
main_tab1, main_tab2 = st.tabs(["📐 CAD 좌표 & 터널 형상화", "🧪 물성치 자동 변환기"])

# ==========================================
# 탭 2: 물성치 자동 변환기 (HWP / Excel 연동)
# ==========================================
with main_tab2:
    st.subheader("🧪 지반 물성치 UDEC 코드 자동 생성기")
    st.markdown("""
    한글 파일(.hwp)이나 엑셀의 물성치 표를 복사해서 **[텍스트 붙여넣기]** 하거나 **[엑셀 파일]**을 업로드하세요.
    변형계수($E$)와 포아송비($\\nu$)를 바탕으로 **Bulk Modulus($K$)**와 **Shear Modulus($G$)**를 자동 계산하여 `PROP` 코드를 생성합니다.
    """)
    
    input_method = st.radio("입력 방식 선택", ["한글 표 붙여넣기 (텍스트)", "엑셀/CSV 파일 업로드"], horizontal=True)
    
    df_prop = None
    
    if input_method == "한글 표 붙여넣기 (텍스트)":
        st.caption("💡 한글 표나 엑셀에서 [지층명, E(변형계수), v(포아송비), den(단위중량), coh(점착력), fr(마찰각), te(인장강도)] 순으로 복사해 붙여넣으세요.")
        default_text = """매립층\t10\t0.35\t0.0018\t0.005\t27\t0.0005
퇴적모래\t20\t0.34\t0.00185\t0\t28\t0
풍화토\t50\t0.32\t0.00195\t0.024\t30\t0.0024
3-2등급\t4800\t0.25\t0.0024\t0.8\t37\t0.08
3-1등급\t6300\t0.24\t0.00245\t1.2\t39\t0.12"""
        
        user_paste = st.text_area("표 데이터 붙여넣기", value=default_text, height=150)
        
        if user_paste.strip():
            try:
                lines = [line.split('\t') if '\t' in line else line.split() for line in user_paste.strip().split('\n')]
                df_prop = pd.DataFrame(lines)
                if df_prop.shape[1] >= 7:
                    df_prop = df_prop.iloc[:, :7]
                    df_prop.columns = ['지층명', 'y_mod', 'p_ratio', 'den', 'coh', 'fr', 'te']
            except Exception as e:
                st.error(f"데이터 형식을 읽는 중 오류가 발생했습니다: {e}")

    else:
        prop_file = st.file_uploader("물성치 엑셀/CSV 업로드", type=['xlsx', 'xls', 'csv'])
        if prop_file is not None:
            try:
                if prop_file.name.endswith('.csv'):
                    df_prop = pd.read_csv(prop_file)
                else:
                    df_prop = pd.read_excel(prop_file)
            except Exception as e:
                st.error(f"파일을 읽을 수 없습니다: {e}")

    if df_prop is not None and not df_prop.empty:
        try:
            # 수치형 컬럼 변환
            num_cols = ['y_mod', 'p_ratio', 'den', 'coh', 'fr', 'te']
            for col in num_cols:
                df_prop[col] = pd.to_numeric(df_prop[col], errors='coerce')
            
            # mat 번호 부여 (1부터 시작)
            df_prop['mat'] = range(1, len(df_prop) + 1)
            
            # K, G 자동 계산 (UDEC 공식)
            # K = E / (3 * (1 - 2*v))
            # G = E / (2 * (1 + v))
            df_prop['K'] = (df_prop['y_mod'] / (3 * (1 - 2 * df_prop['p_ratio']))).round(1)
            df_prop['G'] = (df_prop['y_mod'] / (2 * (1 + df_prop['p_ratio']))).round(1)
            
            st.markdown("### 📊 계산된 물성치 데이터")
            st.dataframe(df_prop[['mat', '지층명', 'y_mod', 'p_ratio', 'den', 'coh', 'fr', 'te', 'K', 'G']], use_container_width=True)
            
            # UDEC 물성 코드 생성
            st.markdown("### 📝 생성된 UDEC 물성치 코드")
            
            prop_cmds = ""
            for _, row in df_prop.iterrows():
                mat = int(row['mat'])
                layer = row['지층명']
                e_val = row['y_mod']
                v_val = row['p_ratio']
                den = row['den']
                k_val = row['K']
                g_val = row['G']
                coh = row['coh']
                fr = row['fr']
                te = row['te']
                
                prop_cmds += f"; --- {layer} (mat={mat}) ---\n"
                prop_cmds += f"set y_mod={e_val} p_ratio={v_val}\n"
                prop_cmds += f"derive\n"
                prop_cmds += f"PROP mat={mat} den {den} b={k_val} g={g_val} coh {coh} fr {fr} te {te}\n"
                prop_cmds += f"change ins table {mat} mat={mat} cons=3\n\n"
            
            st.code(prop_cmds, language="text")
            
        except Exception as e:
            st.warning("물성치 컬럼 항목을 확인해 주세요. [지층명, y_mod, p_ratio, den, coh, fr, te] 데이터가 필요합니다.")

# ==========================================
# 탭 1: CAD 좌표 및 터널 형상화 (기존 코드)
# ==========================================
with main_tab1:
    if uploaded_file is not None:
        try:
            # (기존 DXF 스캔, 탭1, 탭2 및 Plotly 미리보기 코드 실행)
            pass
        except Exception as e:
            st.error(f"오류: {e}")
    else:
        st.info("👆 먼저 상단의 DXF 캐드 파일을 업로드해 주세요.")
