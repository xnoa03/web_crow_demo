from flask import Flask, render_template, request, Response, stream_with_context
import pandas as pd
import time
import re
import json
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)

def generate_crawl_stream(max_pages):
    yield f"data: {json.dumps({'progress': 5, 'msg': '🚀 고속 브라우저 모드 시동 중...'})}\n\n"
    
    TARGET_TAGS = ['게임', '기타', '공겜', '할 게임', '할게임']
    CLUB_ID = "27646284"
    MENU_ID = "44"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"user-agent={USER_AGENT}")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.page_load_strategy = 'eager' 
    
    driver = webdriver.Chrome(options=chrome_options)
    crawl_targets = []
    
    try:
        for page in range(1, max_pages + 1):
            yield f"data: {json.dumps({'progress': 10 + (page/max_pages*10), 'msg': f'📋 {page}페이지 목록 스캔 중...'})}\n\n"
            
            target_url = f"https://cafe.naver.com/ArticleList.nhn?search.clubid={CLUB_ID}&search.menuid={MENU_ID}&search.page={page}"
            driver.get(target_url)
            
            try:
                WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.article")))
            except:
                pass

            posts = driver.find_elements(By.CSS_SELECTOR, "a.article")
            for post in posts:
                try:
                    full_title = post.text.strip().replace('\n', ' ')
                    category = "미분류"
                    if full_title.startswith("["):
                        end_index = full_title.find("]")
                        if end_index != -1:
                            category = full_title[1:end_index]
                    
                    clean_category = category.replace(" ", "")
                    clean_targets = [t.replace(" ", "") for t in TARGET_TAGS]
                    
                    if clean_category in clean_targets and category != "공지":
                        raw_link = post.get_attribute('href')
                        match = re.search(r'articles/(\d+)', raw_link)
                        if match:
                            article_id = match.group(1)
                            if not any(d['id'] == article_id for d in crawl_targets):
                                crawl_targets.append({"id": article_id, "category": category, "title": full_title})
                except:
                    continue
    except Exception as e:
        print(f"목록 에러: {e}")
    
    if not crawl_targets:
        driver.quit()
        yield f"data: {json.dumps({'progress': 100, 'msg': '수집된 데이터가 없습니다.', 'done': True})}\n\n"
        return

    final_data = []
    FORBIDDEN = ["1.", "2.", "3.", "4.", "5.", "6.", "7.", "게임이름", "출시일", "가격", "링크", "주소", "한글", "한국어", "언어", "플레이타임", "플타", "추천이유"]
    
    total_items = len(crawl_targets)
    yield f"data: {json.dumps({'progress': 25, 'msg': f'🚀 {total_items}개의 데이터를 정밀 분석합니다...'})}\n\n"

    for idx, item in enumerate(crawl_targets):
        current_percent = 25 + int((idx + 1) / total_items * 70)
        display_title = item['title'][:15] + "..." if len(item['title']) > 15 else item['title']
        yield f"data: {json.dumps({'progress': current_percent, 'msg': f'[{idx+1}/{total_items}] 분석 중: {display_title}'})}\n\n"
        
        try:
            api_url = f"https://apis.naver.com/cafe-web/cafe-articleapi/v2.1/cafes/{CLUB_ID}/articles/{item['id']}"
            driver.get(api_url)
            
            try:
                json_elem = WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.TAG_NAME, "pre")))
                json_str = json_elem.text
            except:
                json_str = driver.find_element(By.TAG_NAME, "body").text

            data = json.loads(json_str)
            content_html = data['result']['article']['contentHtml']
            soup = BeautifulSoup(content_html, "html.parser")
            content = soup.get_text(separator="\n")
            
            pc_url = f"https://cafe.naver.com/ArticleRead.nhn?clubid={CLUB_ID}&articleid={item['id']}"
            
            info = {
                "카테고리": item['category'], "글제목": item['title'],
                "게임이름": "-", "출시일": "-", "가격": "-", "링크": "-", "한글화": "-", "플레이타임": "-",
                "게시글링크": pc_url
            }
            
            if content:
                lines = content.split('\n')
                
                def smart_extract(current_line, current_idx, all_lines, keywords):
                    temp_line = current_line
                    for useless in ["O,X", "O/X", "(O,X)", "(O/X)", "o,x", "o/x", "OX", "ox"]:
                        temp_line = temp_line.replace(useless, "")

                    separators = [":", "-", ")"]
                    for sep in separators:
                        if sep in temp_line:
                            parts = temp_line.split(sep, 1)
                            header_part = parts[0].replace(" ", "")
                            if any(k in header_part for k in keywords):
                                val = parts[1].strip()
                                if "2025/" in val or "2024/" in val: return "-"
                                if ".kr" in val or ".jpg" in val or ".png" in val: return "-"
                                if val: return val
                    
                    cleaned_line = temp_line
                    cleaned_line = re.sub(r'^[0-9]+[\.]?', '', cleaned_line)
                    for k in keywords:
                        cleaned_line = cleaned_line.replace(k, "")
                    cleaned_line = cleaned_line.replace("여부", "").strip()
                    
                    if len(cleaned_line) > 0 and len(cleaned_line) < 30:
                        if "2025/" in cleaned_line or ".kr" in cleaned_line: return "-"
                        return cleaned_line

                    for k in range(current_idx + 1, len(all_lines)):
                        val = all_lines[k].strip()
                        if val != "":
                            is_header = False
                            for f in FORBIDDEN:
                                if f in val and len(val) < 30:
                                    is_header = True
                                    break
                            if is_header: return "-"
                            
                            if "2025/" in val or "2024/" in val: return "-"
                            if ".kr" in val and "http" not in val: return "-"
                            
                            return val
                    return "-"

                for i, line in enumerate(lines):
                    l = line.replace(" ", "")
                    
                    if "게임이름" in l: 
                        info["게임이름"] = smart_extract(line, i, lines, ["게임이름"])
                    elif "출시일" in l: 
                        info["출시일"] = smart_extract(line, i, lines, ["출시일", "필수아님"])
                    elif "가격" in l: 
                        info["가격"] = smart_extract(line, i, lines, ["가격"])
                    elif ("링크" in l or "주소" in l) and "http" not in l:
                        val = smart_extract(line, i, lines, ["링크", "주소"])
                        if "http" in val: info["링크"] = val
                    elif "http" in line and info["링크"] == "-": 
                        info["링크"] = line.strip()
                    elif "한글" in l or "한국어" in l or "언어" in l or "패치" in l: 
                        info["한글화"] = smart_extract(line, i, lines, ["한글", "한국어", "언어", "패치", "화", "여부"])
                    elif "플레이타임" in l or "플타" in l: 
                        info["플레이타임"] = smart_extract(line, i, lines, ["플레이타임", "플타"])

            final_data.append(info)
            
        except Exception as e:
            continue
    
    driver.quit()

    yield f"data: {json.dumps({'progress': 98, 'msg': '💾 데이터 저장 중...'})}\n\n"
    
    if final_data:
        df = pd.DataFrame(final_data)
        df.to_csv('harry_game_list_final.csv', index=False, encoding="utf-8-sig")
    
    yield f"data: {json.dumps({'progress': 100, 'msg': '완료! 새로고침합니다.', 'done': True})}\n\n"

def parse_time(text):
    text = str(text).lower()
    if text == '-' or text == '': return 0.0
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", text)
    if not nums: return 0.0
    vals = [float(n) for n in nums]
    avg = sum(vals) / len(vals)
    if ('분' in text or 'min' in text) and '시간' not in text: return avg / 60
    return avg

@app.route('/')
def index():
    try:
        df = pd.read_csv('harry_game_list_final.csv').fillna('-')
        df['time_num'] = df['플레이타임'].apply(parse_time)
        games = df.to_dict(orient='records')
    except:
        games = []
    return render_template('index.html', games=games)

@app.route('/crawl_stream')
def crawl_stream():
    pages = int(request.args.get('pages', 3))
    return Response(stream_with_context(generate_crawl_stream(pages)), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True)