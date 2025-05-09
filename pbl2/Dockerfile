# syntax=docker/dockerfile:1

#################################################
# 1. 베이스 이미지 및 작업 디렉터리 설정
#################################################
FROM python:3.12.8-bookworm

# Python 출력 즉시 반영
ENV PYTHONUNBUFFERED=1
WORKDIR /src

#################################################
# 2. 시스템 의존성 + Faiss, Poetry 설치
#################################################
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libopenblas-dev \
      libomp-dev \
      wget && \
    rm -rf /var/lib/apt/lists/*

# Poetry 설치
RUN pip install "poetry==1.8.4"

#################################################
# 3. 파이썬 의존성 정의 복사 및 설치
#################################################
COPY pyproject.toml ./
COPY poetry.Lock  ./

# 시스템에 직접 설치하도록 설정 후 배포용 패키지 설치
RUN poetry config virtualenvs.create false \
  && poetry install --no-dev --no-interaction --no-ansi

#################################################
# 4. RDS CA 인증서 다운로드
#################################################
RUN mkdir -p /src/certs && \
    wget https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem \
         -O /src/certs/rds-ca-2019-root.pem

#################################################
# 5. 애플리케이션 코드와 마이그레이션 복사
#################################################
COPY api ./api
COPY migrations ./migrations

#################################################
# 6. 환경 설정 및 포트 노출
#################################################
ENV TZ=Asia/Seoul
EXPOSE 8000

#################################################
# 7. 애플리케이션 실행
#################################################
ENTRYPOINT ["uvicorn", "api.main:app", \
            "--host", "0.0.0.0", \
            "--port", "8000", \
            "--reload", \
            "--log-level", "debug"]
