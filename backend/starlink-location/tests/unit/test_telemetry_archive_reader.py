"""Only raw samples with same-scrape live mode provenance may be recovered."""

import httpx

from app.services.telemetry_archive.reader import ArchiveReader
from tests.unit.test_flight_events import START


def test_raw_scrape_times_and_live_provenance():
    stamp = START.timestamp()

    def respond(request):
        assert request.url.path == "/api/v1/query"
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [
                        {
                            "metric": {
                                "__name__": "starlink_mode_info",
                                "mode": "live",
                                "instance": "one",
                                "job": "starlink-location",
                            },
                            "values": [[stamp, "1"]],
                        },
                        {
                            "metric": {
                                "__name__": "starlink_dish_speed_knots",
                                "instance": "one",
                                "job": "starlink-location",
                            },
                            "values": [[stamp, "0"], [stamp + 1, "99"]],
                        },
                        {
                            "metric": {
                                "__name__": "starlink_dish_speed_knots",
                                "instance": "two",
                            },
                            "values": [[stamp, "999"]],
                        },
                    ],
                },
            },
        )

    with httpx.Client(
        base_url="http://prometheus", transport=httpx.MockTransport(respond)
    ) as client:
        batch = ArchiveReader(client, instance="one").read(START, START)
    assert len(batch) == 1
    assert batch[0][0] == START
    assert batch[0][3] == 0
