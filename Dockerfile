FROM python:3.9

# 1. 필수 시스템 패키지 설치 (gnupg 추가됨)
RUN apt-get update && apt-get install -y wget gnupg unzip

# 2. 구글 크롬 설치 (apt-key 대신 gpg --dearmor 방식 사용)
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable

# 3. 작업 폴더 설정
WORKDIR /app

# 4. 파일 복사
COPY . /app

# 5. 파이썬 라이브러리 설치
RUN pip install --no-cache-dir -r requirements.txt

# 6. 서버 실행
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--timeout", "120", "app:app"]