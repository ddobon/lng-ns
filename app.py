import streamlit as st
import pandas as pd
from mailer_logic import SaaSMailer

st.set_page_config(layout="wide", page_title="배송지연 안내 발송기")

def safe_read_csv(file, file_description="파일"):
    """Safely read CSV with multiple encoding attempts"""
    encodings = ['utf-8-sig', 'cp949', 'euc-kr', 'latin1', 'utf-8']
    
    for i, encoding in enumerate(encodings):
        try:
            file.seek(0)
            df = pd.read_csv(file, encoding=encoding)
            if i > 0:  # If not the first encoding
                st.info(f"ℹ️ {file_description}을(를) {encoding} 인코딩으로 읽었습니다.")
            return df
        except UnicodeDecodeError:
            if i == len(encodings) - 1:  # Last attempt
                st.error(f"❌ {file_description} 인코딩 오류. 파일을 UTF-8로 저장하여 다시 시도해주세요.")
                raise
            continue
        except Exception as e:
            st.error(f"❌ {file_description} 읽기 오류: {str(e)}")
            raise
    
    return None

def main():
    st.title("📮 배송지연 안내 메일 자동 발송기")
    
    st.markdown("""
    업로드한 CSV에서 **배송지연 분류**가 비어있는 항목을 찾아 협력사별로 안내 메일을 자동 생성합니다.
    """)
    
    # Sidebar: Configuration
    with st.sidebar:
        st.header("⚙️ 설정 (Gmail)")
        
        gmail_id = st.text_input("Gmail 주소", placeholder="example@gmail.com")
        gmail_pw = st.text_input("앱 비밀번호", type="password", help="Google 계정 관리 > 보안 > 앱 비밀번호에서 생성")
        sender_name = st.text_input("발신자명", value="배송관리팀")
        
        st.info("💡 앱 비밀번호는 구글 계정 설정에서 생성할 수 있습니다.")

        st.divider()
        st.write("사용법:")
        st.write("1. `input_template.csv` 업로드")
        st.write("2. `mail_list` 업로드 (협력사 이메일 정보)")
        st.write("3. 분석 및 미리보기")
        st.write("4. 메일 발송")

    # Main: File Upload
    col1, col2 = st.columns(2)
    
    with col1:
        uploaded_file = st.file_uploader("1️⃣ 주문/배송 데이터 (CSV)", type=['csv'])
        
    with col2:
        mail_list_file = st.file_uploader("2️⃣ 협력사 메일 리스트 (CSV/Excel)", type=['csv', 'xlsx'])

    # Optional Template
    with st.expander("3️⃣ 메일 템플릿 수정 (선택사항)"):
        # Default template
        default_template = """**제목: [배송확인] {{협력사명}} 배송 지연 건 확인 요청 드립니다**

안녕하세요, {{협력사명}} 담당자님.

귀사의 일익 번창을 기원합니다.
현재 아래 주문 건에 대하여 배송 흐름이 확인되지 않거나 지연되고 있어 확인 요청드립니다.

**[요청 사항]**
**정확한 출고 예정일**을 회신 부탁드립니다.
품절로 취소가 필요할 경우 **품절**로 회신 부탁드립니다.

**[확인 요청 상세 정보]**

| 상품코드 | 상품명 | 단품명 | 주문번호 | 운송장번호 |
| :--- | :--- | :--- | :--- | :--- |
| {{상품코드}} | {{상품명}} | {{단품명}} | {{주문번호}} | {{운송장번호}} |

바쁘시겠지만 빠른 확인 부탁드립니다.
감사합니다."""
        template_input = st.text_area("템플릿 내용", value=default_template, height=300)

    # Analyze Button
    if uploaded_file and mail_list_file:
        if st.button("🔍 데이터 분석 및 메일 생성", type="primary"):
            try:
                # Load Data

                data_df = safe_read_csv(uploaded_file, "주문/배송 데이터")

                if mail_list_file.name.endswith('.csv'):
                    mail_list_df = safe_read_csv(mail_list_file, "협력사 메일 리스트")
                else:
                    mail_list_df = pd.read_excel(mail_list_file)
                
                # Initialize Mailer
                mailer = SaaSMailer(data_df, mail_list_df, template_input)
                
                # Process
                with st.spinner("분석 중..."):
                    mail_items, logs = mailer.filter_and_process()
                
                # Show Logs
                with st.expander("처리 로그 보기", expanded=False):
                    for log in logs:
                        st.write(log)
                
                if not mail_items:
                    st.warning("⚠️ 발송할 대상(배송지연 분류가 비어있는 항목)이 없습니다.")
                else:
                    # Sort: Valid emails first, missing emails last (User Request)
                    mail_items.sort(key=lambda x: 0 if x['email'] else 1)
                    
                    st.success(f"✅ 총 {len(mail_items)}개의 안내 메일이 생성되었습니다.")
                    st.session_state['mail_items'] = mail_items
                    st.session_state['ready_to_send'] = True
                    
            except Exception as e:
                st.error(f"오류 발생: {str(e)}")
                
    # Preview and Send Section
    if st.session_state.get('ready_to_send') and st.session_state.get('mail_items'):
        mail_items = st.session_state['mail_items']
        
        st.divider()
        st.subheader("📋 메일 미리보기 & 발송")
        
        # Tabs for preview
        if len(mail_items) > 10:
            selected_partner = st.selectbox("협력사 선택", [m['partner_name'] for m in mail_items])
            preview_item = next((m for m in mail_items if m['partner_name'] == selected_partner), None)
            display_items = [preview_item] if preview_item else []
        else:
            tabs = st.tabs([f"{m['partner_name']} ({m['count']}건)" for m in mail_items])
            display_items = zip(tabs, mail_items)

        # Iterate via tabs or single view
        if len(mail_items) <= 10:
             for tab, item in display_items:
                with tab:
                    render_preview(item)
        else:
            if display_items:
                render_preview(display_items[0])

        st.divider()
        col_send, col_dummy = st.columns([1, 4])
        with col_send:
            if st.button("🚀 전체 메일 발송 시작", type="primary", use_container_width=True):
                if not gmail_id or not gmail_pw:
                    st.error("⚠️ 설정 사이드바에서 Gmail 계정과 앱 비밀번호를 입력해주세요.")
                else:
                    # Config
                    smtp_config = {
                        'server': 'smtp.gmail.com',
                        'port': 587,
                        'username': gmail_id,
                        'password': gmail_pw,
                        'from_email': gmail_id,
                        'from_name': sender_name
                    }
                    
                    # Create a mailer instance for sending (we only need the utility methods)
                    temp_mailer = SaaSMailer(None, None, None)
                    
                    # Sending Process
                    progress_bar = st.progress(0)
                    status_area = st.empty()
                    
                    success_cnt = 0
                    fail_cnt = 0
                    
                    # Filter: Send only to partners with email
                    valid_items = [item for item in mail_items if item['email']]
                    skipped_count = len(mail_items) - len(valid_items)
                    
                    if skipped_count > 0:
                        st.info(f"ℹ️ 이메일 주소가 없는 {skipped_count}건은 발송 리스트에서 제외되었습니다.")

                    if not valid_items:
                        st.warning("발송할 유효한 이메일 대상이 없습니다.")
                    else:
                        for i, item in enumerate(valid_items):
                            status_area.write(f"sending to {item['partner_name']}...")
                            success, msg = temp_mailer.send_single_mail(item, smtp_config)
                            
                            if success:
                                success_cnt += 1
                            else:
                                fail_cnt += 1
                                st.write(f"❌ {item['partner_name']} 실패: {msg}")
                                
                            progress_bar.progress((i + 1) / len(valid_items))
                    
                    status_area.write("완료!")
                    st.success(f"발송 완료! 성공: {success_cnt}, 실패: {fail_cnt}")


def render_preview(item):
    st.markdown(f"**수신**: {item['email'] if item['email'] else '❌ 이메일 없음'}")
    
    import streamlit.components.v1 as components
    
    # Simple SaaSMailer instance to get html
    temp_mailer = SaaSMailer(None, None, None)
    html_content = temp_mailer.markdown_to_html(item['content'])
    
    with st.expander("HTML 미리보기", expanded=True):
        components.html(html_content, height=400, scrolling=True)
        
    with st.expander("원본 텍스트 보기"):
        st.text(item['content'])

if __name__ == "__main__":
    main()