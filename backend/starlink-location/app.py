from fastapi import FastAPI
from prometheus_client import REGISTRY, Gauge, generate_latest

app = FastAPI()

# Define the starlink_service_info gauge metric
starlink_service_info = Gauge(
    'starlink_service_info',
    'Starlink service information',
    ['version', 'mode']
)

# Set the metric with labels and value
starlink_service_info.labels(version='0.1.0', mode='stub').set(1)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    from fastapi.responses import Response
    return Response(
        content=generate_latest(REGISTRY),
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )
