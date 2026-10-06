# syntax=docker/dockerfile:1
FROM python:3.11-slim
WORKDIR /research
COPY tools/acceptance/weather_detail_comparison/requirements.txt /research/requirements.txt
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements.txt
COPY tools/acceptance /research/acceptance
ENV PYTHONPATH=/research
ENTRYPOINT ["python", "-m", "acceptance.weather_detail_comparison.generate"]
