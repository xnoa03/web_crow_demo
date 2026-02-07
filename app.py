import streamlit as st
import pandas as pd
import time
import re
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# ==========================================
# 1. 크롤링 로봇 (클라우드 우회 + 터보 모드)
# ==========================================
def run_crawler(max_pages):
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    # --- [설정] ---
    TARGET_TAGS = ['게임', '기타', '공겜']
    CLUB_ID = "27646284" # 해쿠아리움
    MENU_ID = "44"       # 해리야 할래말래 게시판
    
    # [핵심] 네이버가 봇을 차단하지 못하게 사람인 척하는 설정
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    status_text.text(f"🤖 클라우드 서버에서 탐색을 시작합니다... (최대 {max_pages}페이지)")
    
    # --------------------------------------------------------
    # 1단계: 목록 수집 (Selenium Headless)
    # --------------------------------------------------------
    chrome_options = Options()
    chrome_options.add_argument("--headless") # 화면 없이 실행
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080") # 화면 크기 설정 (중요)
    chrome_options.add_argument(f"user-agent={USER_AGENT}") # 봇 탐지 우회
    
    driver = webdriver.Chrome(options=chrome_options)
    crawl_targets = []
    
    try:
        for page in range(1, max_pages + 1):
            status_text.text(f"📋 {page}페이지 스캔 중... (게시글 목록 확보)")
            
            target_url = f"https://cafe.naver.com/ArticleList.nhn?search.clubid={CLUB_ID}&search.menuid={MENU_ID}&search.page={page}"
            driver.get(target_url)
            time.sleep(1.5) # 페이지 로딩 대기

            posts = driver.find_elements(By.CSS_SELECTOR, "a.article")
            
            # [디버깅] 게시글을 하나도 못 찾았을 경우
            if len(posts) == 0 and page == 1:
                st.warning(f"⚠️ {page}페이지에서 게시글을 찾지 못했습니다. (네이버 보안 차단 가능성)")
                # 스크린샷 찍어서 확인해보기 (선택사항)
                # driver.save_screenshot("debug.png")
                # st.image("debug.png")

            for post in posts:
                try:
                    full_title = post.text.strip().replace('\n', ' ')
                    raw_link = post.get_attribute('href')
                    
                    category = "미분류"
                    if full_title.startswith("[") and "]" in full_title:
                        end_index = full_title.find("]")
                        category = full_title[1:end_index]
                    
                    if category in TARGET_TAGS and category != "공지":
                        match = re.search(r'articles/(\d+)', raw_link)
                        if match:
                            article_id = match.group(1)
                            # 중복 방지
                            if not any(d['id'] == article_id for d in crawl_targets):
                                crawl_targets.append({
                                    "id": article_id,
                                    "category": category,
                                    "title": full_title
                                })
                except:
                    continue
            
            # 페이지별 진행률 표시
            progress_bar.progress(page / max_pages * 0.3) # 전체 공정의 30% 배정
            
    except Exception as e:
        st.error(f"목록 수집 중 에러: {e}")
    finally:
        driver.quit() # 브라우저 종료

    # --------------------------------------------------------
    # 2단계: 상세 정보 수집 (API 활용 - 고속 모드)
    # --------------------------------------------------------
    if not crawl_targets:
        status_text.warning("수집 대상이 없습니다.")
        progress_bar.empty()
        return pd.DataFrame()

    status_text.text(f"🚀 {len(crawl_targets)}개의 게임을 발견! 상세 정보를 분석합니다...")
    
    final_data = []
    
    # 밀림 방지를 위한 '다음 질문(Header)' 감지 리스트
    FORBIDDEN_HEADERS = [
        "1.", "2.", "3.", "4.", "5.", "6.", "7.",
        "게임이름", "출시일", "가격", "링크", "주소", "한글", "플레이타임", "플타", "추천이유"
    ]

    for idx, item in enumerate(crawl_targets):
        # 진행률 업데이트 (나머지 70%)
        current_progress = 0.3 + ((idx + 1) / len(crawl_targets) * 0.7)
        progress_bar.progress(min(current_progress, 1.0))
        
        try:
            # 네이버 모바일 API 주소
            api_url = f"https://apis.naver.com/cafe-web/cafe-articleapi/v2.1/cafes/{CLUB_ID}/articles/{item['id']}"
            
            # [중요] API 요청 시에도 User-Agent 헤더 필수
            headers = {'User-Agent': USER_AGENT}
            response = requests.get(api_url, headers=headers)
            
            if response.status_code != 200: continue

            data = response.json()
            content_html = data['result']['article']['contentHtml']
            
            # HTML 태그 제거 및 텍스트 추출
            soup = BeautifulSoup(content_html, "html.parser")
            content_text = soup.get_text(separator="\n")
            
            info = {
                "카테고리": item['category'],
                "글제목": item['title'],
                "게임이름": "-", "출시일": "-", "가격": "-", 
                "링크": "-", "한글화": "-", "플레이타임": "-",
                "게시글링크": f"https://cafe.naver.com/ArticleRead.nhn?clubid={CLUB_ID}&articleid={item['id']}"
            }
            
            if content_text:
                lines = content_text.split('\n')
                
                # [핵심] 안전하게 값 가져오기 (밀림 방지 로직)
                def get_safe_value(current_idx, all_lines):
                    for k in range(current_idx + 1, len(all_lines)):
                        val = all_lines[k].strip()
                        if val != "":
                            # 가져온 줄이 '질문(Header)'처럼 생겼으면 데이터 없음 처리
                            for header in FORBIDDEN_HEADERS:
                                if header in val and len(val) < 30:
                                    return "-"
                            return val
                    return "-"

                for i, line in enumerate(lines):
                    check_line = line.replace(" ", "") # 띄어쓰기 무시 비교
                    
                    if "게임이름" in check_line: info["게임이름"] = get_safe_value(i, lines)
                    elif "출시일" in check_line: info["출시일"] = get_safe_value(i, lines)
                    elif "가격" in check_line: info["가격"] = get_safe_value(i, lines)
                    elif ("링크" in check_line or "주소" in check_line) and "http" not in check_line:
                            val = get_safe_value(i, lines)
                            if "http" in val: info["링크"] = val
                    elif "http" in line and info["링크"] == "-": # 본문에 덩그러니 있는 링크
                         info["링크"] = line.strip()
                    elif "한글" in check_line: info["한글화"] = get_safe_value(i, lines)
                    elif "플레이타임" in check_line or "플타" in check_line: info["플레이타임"] = get_safe_value(i, lines)

            final_data.append(info)
        except:
            continue

    status_text.success(f"🎉 수집 완료! ({len(final_data)}개)")
    time.sleep(1)
    status_text.empty()
    progress_bar.empty()
    
    return pd.DataFrame(final_data)


# ==========================================
# 2. 웹 UI 구성
# ==========================================
st.set_page_config(page_title="해리야 할래말래?", page_icon="🦦", layout="wide")

@st.cache_data
def load_data():
    try:
        df = pd.read_csv('harry_game_list_final.csv')
        if df.empty: return pd.DataFrame()
        return df.fillna('-')
    except:
        return pd.DataFrame()

with st.sidebar:
    st.header("⚙️ 데이터 관리")
    
    # 페이지 수 설정
    page_limit = st.number_input("탐색할 페이지 수 (1~10)", min_value=1, max_value=10, value=3)
    
    if st.button("🚀 데이터 가져오기"):
        with st.spinner("해쿠아리움에 접속 중입니다..."):
            new_df = run_crawler(page_limit)
            if not new_df.empty:
                new_df.to_csv('harry_game_list_final.csv', index=False, encoding="utf-8-sig")
                st.cache_data.clear()
                st.rerun() 
            else:
                st.warning("수집된 데이터가 없습니다. (잠시 후 다시 시도해보세요)")
    
    st.info("버튼을 누르면 실시간으로 카페를 탐색합니다.")

st.title("🦦 해리야 이 게임 할래말래?")
st.caption("팬카페 추천 게임 리스트 (클라우드 최적화 버전)")

df = load_data()

if df.empty:
    st.info("👈 왼쪽 사이드바에서 [데이터 가져오기] 버튼을 눌러주세요!")
else:
    # 필터링
    tags = df['카테고리'].unique().tolist()
    selected_tags = st.multiselect("장르 선택", tags, default=tags)
    search_korean = st.text_input("한글화 검색", "")
    
    filtered_df = df[df['카테고리'].isin(selected_tags)]
    if search_korean:
        filtered_df = filtered_df[filtered_df['한글화'].astype(str).str.contains(search_korean, na=False)]
    
    # 테이블 출력
    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
        column_order=["카테고리", "글제목", "게임이름", "가격", "한글화", "플레이타임", "링크", "게시글링크"],
        column_config={
            "글제목": st.column_config.TextColumn("게시글 제목", width="medium"),
            "링크": st.column_config.LinkColumn("상점", display_text="구매 🔗"),
            "게시글링크": st.column_config.LinkColumn("원글", display_text="카페 📄"),
            "가격": st.column_config.TextColumn("가격"),
            "플레이타임": st.column_config.TextColumn("플타")
        }
    )
    
    st.divider()
    
    # 랜덤 추천
    if st.button("🐚 마법의 소라고동"):
        if not filtered_df.empty:
            pick = filtered_df.sample(1).iloc[0]
            st.balloons()
            
            # 추천 메시지 (게임 이름이 없으면 글 제목 사용)
            display_title = pick['게임이름'] if pick['게임이름'] != '-' else pick['글제목']
            
            st.success(f"### 🚀 추천: **{display_title}**")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("장르", pick['카테고리'])
            c2.metric("가격", pick['가격'])
            c3.metric("한글화", pick['한글화'])
            c4.metric("플타", pick['플레이타임'])
            
            st.markdown(f"👉 [상점 페이지 바로가기]({pick['링크']})")
            st.markdown(f"👉 [추천글 보러가기]({pick['게시글링크']})")
        else:
            st.warning("추천할 게임이 없습니다.")
