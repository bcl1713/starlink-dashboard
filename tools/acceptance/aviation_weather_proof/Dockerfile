# syntax=docker/dockerfile:1
FROM python:3.11-slim
WORKDIR /research
COPY tools/acceptance/aviation_weather_proof/requirements.txt /research/requirements.txt
RUN --mount=type=secret,id=proxy_ca,required=true \
    PIP_CERT=/run/secrets/proxy_ca pip install --no-cache-dir -r requirements.txt
COPY tools/acceptance/aviation_weather_proof /research/acceptance/aviation_weather_proof
ENV PYTHONPATH=/research
ENTRYPOINT ["python", "-m", "acceptance.aviation_weather_proof.capture"]
