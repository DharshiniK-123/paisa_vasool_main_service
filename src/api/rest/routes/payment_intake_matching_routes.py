import logging

import httpx
from fastapi import APIRouter, Request, Response, UploadFile

from src.config.settings import settings

router = APIRouter(prefix="/api/v1/payment_intake_matching")

MATCHING_SERVICE_URL = settings.MATCHING_SERVICE_URL

logger = logging.getLogger(__name__)


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_matching(request: Request, path: str) -> Response:
    """API gateway route for payment_intake_matching service"""

    url = f"{MATCHING_SERVICE_URL}/api/v1/payment_intake_matching/{path}"

    forward_headers = {}
    auth_header = request.headers.get("Authorization")
    if auth_header:
        forward_headers["Authorization"] = auth_header

    content_type = request.headers.get("content-type", "")

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=600.0)) as client:
            if content_type.startswith("multipart/form-data"):
                form = await request.form()
                files = []
                data = {}

                for key, value in form.multi_items():
                    if isinstance(value, UploadFile):
                        files.append(
                            (key, (value.filename, await value.read(), value.content_type))
                        )
                    else:
                        data[key] = value


                response = await client.request(
                    method=request.method,
                    url=url,
                    params=request.query_params,
                    data=data,
                    files=files,
                    headers=forward_headers,
                    cookies=request.cookies,
                )

            elif content_type.startswith("application/json"):
                try:
                    json_body = await request.json()
                except Exception:
                    json_body = None

                response = await client.request(
                    method=request.method,
                    url=url,
                    params=request.query_params,
                    json=json_body,
                    headers=forward_headers,
                    cookies=request.cookies,
                )

            else:
                response = await client.request(
                    method=request.method,
                    url=url,
                    params=request.query_params,
                    content=await request.body(),
                    headers=forward_headers,
                    cookies=request.cookies,
                )

        excluded = {"content-encoding", "transfer-encoding", "content-length"}
        clean_headers = {k: v for k, v in response.headers.items() if k.lower() not in excluded}

        logger.info(
            "proxy_matching_success",
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "forward_url": url,
                "status_code": response.status_code,
            },
        )

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=clean_headers,
        )

    except httpx.RequestError as exc:
        logger.error(
            "proxy_matching_request_failed",
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "forward_url": url,
                "error": str(exc),
            },
        )
        return Response(
            content=b'{"error": "Matching service unavailable"}',
            status_code=503,
            media_type="application/json",
        )

    except httpx.HTTPStatusError as exc:
        logger.error(
            "proxy_matching_http_error",
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "forward_url": url,
                "error": str(exc),
            },
        )
        return Response(
            content=b'{"error": "Matching service error"}',
            status_code=502,
            media_type="application/json",
        )

    except Exception:
        logger.exception(
            "proxy_matching_unexpected_error",
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "forward_url": url,
            },
        )
        return Response(
            content=b'{"error": "Internal server error"}',
            status_code=500,
            media_type="application/json",
        )
