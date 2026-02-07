from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

# 1. 크롬 연결 설정 (아까와 동일)
chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

try:
    driver = webdriver.Chrome(options=chrome_options)
    print("✅ 크롬 연결 성공!")

    # 2. [중요] 'cafe_main'이라는 이름의 액자(iframe) 안으로 시선 이동
    # 네이버 카페는 이 코드가 없으면 게시글을 절대 못 찾습니다.
    try:
        driver.switch_to.frame("cafe_main")
        print("✅ 게시판 프레임(cafe_main) 진입 성공!")
    except:
        print("⚠️ 프레임 전환 실패 (혹시 모바일 페이지인가요? PC버전으로 접속해주세요)")

    # 3. 게시글 제목들 찾기
    # 네이버 카페 게시글 제목은 보통 'article'이라는 클래스를 가집니다.
    posts = driver.find_elements(By.CSS_SELECTOR, "a.article")
    
    # 혹시 못 찾았으면 다른 태그로 시도 (카페마다 디자인이 다를 수 있음)
    if len(posts) == 0:
        posts = driver.find_elements(By.CSS_SELECTOR, "div.board-list div.inner_list a.article")

    print(f"\n🔍 현재 페이지에서 {len(posts)}개의 글을 발견했습니다!\n")

    # 4. 결과 출력 (상위 10개만)
    for i, post in enumerate(posts[:10]):
        title = post.text.strip()
        link = post.get_attribute('href')
        print(f"[{i+1}] {title}")
        print(f"    👉 링크: {link}")

except Exception as e:
    print("❌ 에러 발생:", e)