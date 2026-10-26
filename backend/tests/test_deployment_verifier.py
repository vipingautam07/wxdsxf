import httpx
import pytest

from scripts.verify_live import require_allowed_origin


@pytest.mark.parametrize("allowed", [None, "https://different-project.vercel.app", "*"])
def test_http_200_without_matching_origin_fails_verification(allowed):
    headers = {"access-control-allow-origin": allowed} if allowed else {}
    response = httpx.Response(
        200, headers=headers, request=httpx.Request("GET", "https://backend.example/api/day")
    )
    with pytest.raises(AssertionError, match="Set CORS_ORIGINS"):
        require_allowed_origin(response, "https://frontend.example")


def test_matching_origin_passes_verification():
    response = httpx.Response(
        200,
        headers={"access-control-allow-origin": "https://frontend.example"},
        request=httpx.Request("GET", "https://backend.example/api/day"),
    )
    require_allowed_origin(response, "https://frontend.example")
