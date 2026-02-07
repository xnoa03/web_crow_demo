import streamlit as st
import pandas as pd
import time
import re
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


def run_crawler(max_pages):
    status_text = st.empty()
    progress_bar = st.progress(0)
    

    TARGET_TAGS = ['게임', '기타', '공겜']
    CLUB_ID = "27646284"
    
    status_text.text("📋 게시글 목록을 스캔하고 있습니다... (Selenium)")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.page_load_strategy = 'eager'

    driver = webdriver.Chrome(options=chrome_options)
    
    crawl_targets = []
    
    try:
        
        for page in range(1, max_pages + 1):
            status_text.text(f"📋 게시글 목록 스캔 중... ({page}/{max_pages} 페이지)")
            
            # 주소 뒤에 &search.page={page} 를 붙여서 페이지 이동
            target_url = f"https://cafe.naver.com/ArticleList.nhn?search.clubid={CLUB_ID}&search.menuid=44&search.page={page}"
            driver.get(target_url)
            time.sleep(0.5) # 페이지 로딩 대기 (너무 빠르면 차단될 수 있음)

            posts = driver.find_elements(By.CSS_SELECTOR, "a.article")
            
            # 현재 페이지의 글 수집
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
                            # 중복 수집 방지 (혹시 몰라서)
                            if not any(d['id'] == article_id for d in crawl_targets):
                                crawl_targets.append({
                                    "id": article_id,
                                    "category": category,
                                    "title": full_title
                                })
                except:
                    continue
            
            # 진행률 바 업데이트 (목록 수집 단계)
            progress_bar.progress(page / max_pages)
                
    except Exception as e:
        st.error(f"목록 수집 중 에러: {e}")
    finally:
        driver.quit()

    # ---------------------------------------------------------
    # 2. 상세 정보 수집 (API 터보 모드)
    # ---------------------------------------------------------
    if not crawl_targets:
        status_text.warning("수집 대상이 없습니다.")
        return pd.DataFrame()

    status_text.text(f"🚀 총 {len(crawl_targets)}개의 게임을 발견! 상세 정보를 분석합니다...")
    progress_bar.progress(0) # 바 초기화
    
    final_data = []
    
    FORBIDDEN_HEADERS = [
        "1.", "2.", "3.", "4.", "5.", "6.", "7.",
        "게임이름", "출시일", "가격", "링크", "주소", "한글", "플레이타임", "플타", "추천이유"
    ]

    for idx, item in enumerate(crawl_targets):
        # 상세 수집 진행률
        progress_bar.progress((idx + 1) / len(crawl_targets))
        
        try:
            api_url = f"https://apis.naver.com/cafe-web/cafe-articleapi/v2.1/cafes/{CLUB_ID}/articles/{item['id']}"
            response = requests.get(api_url)
            data = response.json()
            
            content_html = data['result']['article']['contentHtml']
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
                
                def get_safe_value(current_idx, all_lines):
                    for k in range(current_idx + 1, len(all_lines)):
                        val = all_lines[k].strip()
                        if val != "":
                            for header in FORBIDDEN_HEADERS:
                                if header in val and len(val) < 30:
                                    return "-"
                            return val
                    return "-"

                for i, line in enumerate(lines):
                    check_line = line.replace(" ", "")
                    
                    if "게임이름" in check_line: info["게임이름"] = get_safe_value(i, lines)
                    elif "출시일" in check_line: info["출시일"] = get_safe_value(i, lines)
                    elif "가격" in check_line: info["가격"] = get_safe_value(i, lines)
                    elif ("링크" in check_line or "주소" in check_line) and "http" not in check_line:
                            val = get_safe_value(i, lines)
                            if "http" in val: info["링크"] = val
                    elif "http" in line and info["링크"] == "-": info["링크"] = line.strip()
                    elif "한글" in check_line: info["한글화"] = get_safe_value(i, lines)
                    elif "플레이타임" in check_line or "플타" in check_line: info["플레이타임"] = get_safe_value(i, lines)

            final_data.append(info)
            
        except:
            continue

    status_text.success(f"🎉 {len(final_data)}개 게임 수집 완료! ({max_pages} 페이지)")
    time.sleep(1)
    status_text.empty()
    progress_bar.empty()
    
    return pd.DataFrame(final_data)



st.set_page_config(page_title="해리야 할래말래?", page_icon="📚", layout="wide")

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
    
    # [추가됨] 페이지 수 설정 슬라이더
    page_limit = st.number_input("탐색할 페이지 수 (1~10)", min_value=1, max_value=20, value=3)
    
    if st.button("🚀 데이터 가져오기"):
        with st.spinner(f"최근 {page_limit}페이지를 훑어보는 중입니다..."):
            new_df = run_crawler(page_limit) # 함수에 페이지 수 전달
            if not new_df.empty:
                new_df.to_csv('harry_game_list_final.csv', index=False, encoding="utf-8-sig")
                st.cache_data.clear()
                st.rerun() 
            else:
                st.warning("수집된 데이터가 없습니다.")
    
    st.info(f"설정된 페이지 수만큼 과거 글까지 탐색합니다.")

st.title("📚 해리야 이 게임 할래말래?")
st.caption("팬카페 추천 게임 리스트 (페이지 탐색 기능 추가)")

df = load_data()

if df.empty:
    st.info("👈 왼쪽 사이드바에서 페이지 수를 정하고 [데이터 가져오기] 버튼을 눌러주세요!")
else:
    tags = df['카테고리'].unique().tolist()
    selected_tags = st.multiselect("장르 선택", tags, default=tags)
    search_korean = st.text_input("한글화 검색", "")
    
    filtered_df = df[df['카테고리'].isin(selected_tags)]
    if search_korean:
        filtered_df = filtered_df[filtered_df['한글화'].astype(str).str.contains(search_korean, na=False)]
    
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
    if st.button("🐚 마법의 소라고동"):
        if not filtered_df.empty:
            pick = filtered_df.sample(1).iloc[0]
            st.balloons()
            st.success(f"### 🚀 추천: **{pick['글제목']}**")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("장르", pick['카테고리'])
            c2.metric("게임명", pick['게임이름'])
            c3.metric("가격", pick['가격'])
            c4.metric("한글화", pick['한글화'])
            st.markdown(f"👉 [상점 페이지]({pick['링크']}) | [추천글 보기]({pick['게시글링크']})")