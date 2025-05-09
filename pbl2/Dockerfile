# syntax=docker/dockerfile:1

#################################################
# 1. 베이스 이미지 및 작업 디렉터리 설정
#################################################
FROM python:3.12.8-bookworm
ENV PYTHONUNBUFFERED=1
WORKDIR /app

#################################################
# 2. 시스템 의존성 + Poetry, Faiss 설치
#################################################
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential curl git \
 && pip install --no-cache-dir \
      "poetry==1.8.4" \
      faiss-cpu \
 && rm -rf /var/lib/apt/lists/*

#################################################
# 3. 프로젝트 의존성 복사 및 설치
#################################################
COPY pyproject.toml poetry.lock ./
# Poetry 가상환경 생성 방지하고 직접 설치
RUN poetry config virtualenvs.create false \
 && poetry install --no-dev --no-interaction --no-ansi

#################################################
# 4. 애플리케이션 소스 복사
#################################################
COPY . .

#################################################
# 5. 환경 변수 및 포트 설정
#################################################
ENV TZ=Asia/Seoul
EXPOSE 8000

#################################################
# 6. 애플리케이션 실행
#################################################
ENTRYPOINT ["uvicorn", "api.main:app", \
            "--host", "0.0.0.0", \
            "--port", "8000", \
            "--reload", \
            "--log-level", "debug"]
