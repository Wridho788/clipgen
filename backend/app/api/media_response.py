"""
HTTP Range responses for media playback.

Starlette 0.27 ``FileResponse`` ignores ``Range`` headers, so a browser
``<video>`` cannot seek inside a long source without downloading it from the
start. The editor seeks to the trim start constantly, so serve byte ranges.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

_RANGE = re.compile(r"bytes=(\d*)-(\d*)$")
_CHUNK = 1024 * 512


def media_file_response(request: Request, path: Path, media_type: str = "video/mp4", filename: str | None = None):
    size = path.stat().st_size
    header = request.headers.get("range")
    if not header:
        response = FileResponse(path=path, media_type=media_type, filename=filename)
        response.headers["Accept-Ranges"] = "bytes"
        return response

    match = _RANGE.match(header.strip())
    if not match or (not match.group(1) and not match.group(2)):
        raise HTTPException(status_code=416, detail="Range tidak valid", headers={"Content-Range": f"bytes */{size}"})
    if match.group(1):
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else size - 1
    else:
        # Suffix range: the last N bytes.
        start = max(0, size - int(match.group(2)))
        end = size - 1
    end = min(end, size - 1)
    if start > end or start >= size:
        raise HTTPException(status_code=416, detail="Range di luar ukuran file", headers={"Content-Range": f"bytes */{size}"})

    length = end - start + 1

    def iterate():
        with open(path, "rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining > 0:
                chunk = handle.read(min(_CHUNK, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Content-Range": f"bytes {start}-{end}/{size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
    }
    if filename:
        headers["Content-Disposition"] = f'attachment; filename="{os.path.basename(filename)}"'
    return StreamingResponse(iterate(), status_code=206, media_type=media_type, headers=headers)
