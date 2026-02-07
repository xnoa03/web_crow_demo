from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

# 1. 크롬 연결
chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

try:
    driver = webdriver.Chrome(options=chrome_options)
    print("✅ 크롬 연결 성공!")

    # 2. '게시판 알맹이' 주소로 바로 이동
    # (이 주소는 iframe이 없는 순수 게시판 화면입니다)
    target_url = "https://cafe.naver.com/ArticleList.nhn?search.clubid=27646284&search.menuid=44"
    
    # 이미 같은 주소면 새로고침 안 함 (속도 향상)
    if driver.current_url != target_url:
        driver.get(target_url)
        time.sleep(2) 
    print("✅ 게시판 목록 페이지 도착!")

    # 3. [수정됨] 프레임 전환(switch_to) 삭제!
    # 우리는 이미 내부에 있으므로 바로 찾으면 됩니다.

    # 4. 게시글 제목 찾기
    # 'article' 클래스를 가진 a 태그 찾기
    posts = driver.find_elements(By.CSS_SELECTOR, "a.article")
    
    # 못 찾았을 경우 대비용 (다른 스타일일 수 있음)
    if len(posts) == 0:
        # 가끔 로딩이 덜 되면 못 찾을 수 있어서 1초 더 대기
        time.sleep(1)
        posts = driver.find_elements(By.CSS_SELECTOR, "div.board-list div.inner_list a.article")

    print(f"\n🔍 게시글 {len(posts)}개를 찾았습니다!\n")
    
    # 5. 결과 출력
    for i, post in enumerate(posts[:10]): 
        try:
            title = post.text.strip().replace('\n', ' ')
            link = post.get_attribute('href')
            print(f"[{i+1}] {title}")
            # 링크가 너무 길면 보기 싫으니까 살짝 줄여서 출력
            print(f"    👉 {link[:50]}...") 
        except:
            continue

except Exception as e:
    print("❌ 에러 발생:", e)