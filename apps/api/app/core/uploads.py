"""Checks for files users upload (for example a CV), before anything reads or stores them.

Nothing in the app accepts uploads yet; this is the gate every future upload route must pass
through. It checks size, the extension against an allow-list, that the content really is that
type, and, for PDFs, that there is no active content. A virus scanner can be plugged in with
``set_scanner``; the ClamAV one talks to a clamd daemon over TCP.
"""

import asyncio
import re
import struct
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath
from typing import Protocol

from app.core.errors import AppError

MAX_UPLOAD_BYTES = 5_000_000
ALLOWED = {"pdf", "docx", "txt"}
_PDF_ACTIVE = re.compile(rb"/(JavaScript|JS|Launch|OpenAction|AA|EmbeddedFile|RichMedia)\b")


class UploadRejected(AppError):
    status_code = 422
    code = "upload_rejected"


@dataclass(frozen=True)
class CheckedUpload:
    filename: str
    kind: str
    size: int


class Scanner(Protocol):
    async def scan(self, content: bytes) -> str | None:
        """Return a signature name if the content is malicious, otherwise None."""
        ...


class NullScanner:
    async def scan(self, content: bytes) -> str | None:
        return None


class ClamAvScanner:
    def __init__(self, host: str, port: int = 3310, timeout: float = 20.0) -> None:
        self._host, self._port, self._timeout = host, port, timeout

    async def scan(self, content: bytes) -> str | None:
        async def run() -> str | None:
            reader, writer = await asyncio.open_connection(self._host, self._port)
            try:
                writer.write(b"zINSTREAM\0")
                for start in range(0, len(content), 65536):
                    chunk = content[start : start + 65536]
                    writer.write(struct.pack("!I", len(chunk)) + chunk)
                writer.write(struct.pack("!I", 0))
                await writer.drain()
                reply = (await reader.read(1024)).decode(errors="replace").strip("\0\n ")
            finally:
                writer.close()
            if reply.endswith("FOUND"):
                return reply.split(":", 1)[-1].replace("FOUND", "").strip() or "malware"
            if reply.endswith("ERROR"):
                raise UploadRejected("The file could not be scanned. Please try again later.")
            return None

        try:
            return await asyncio.wait_for(run(), self._timeout)
        except (TimeoutError, OSError) as exc:
            # Fail closed: an unscanned file is not accepted.
            raise UploadRejected("The file could not be scanned. Please try again later.") from exc


_scanner: Scanner = NullScanner()


def set_scanner(scanner: Scanner) -> None:
    global _scanner
    _scanner = scanner


def _kind(filename: str) -> str:
    name = PurePath(filename).name
    if name != filename.strip() or not name or name.startswith("."):
        raise UploadRejected("That file name is not allowed")
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension not in ALLOWED:
        raise UploadRejected(f"Only {', '.join(sorted(ALLOWED))} files are accepted")
    return extension


def _check_content(kind: str, content: bytes) -> None:
    if kind == "pdf":
        if not content.startswith(b"%PDF-"):
            raise UploadRejected("That does not look like a PDF")
        if _PDF_ACTIVE.search(content):
            raise UploadRejected(
                "PDFs with scripts, launch actions or embedded files are not accepted"
            )
    elif kind == "docx":
        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                names = archive.namelist()
                if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                    raise UploadRejected("That does not look like a Word document")
                if any(n.lower().endswith(("vbaproject.bin", ".exe", ".dll")) for n in names):
                    raise UploadRejected("Documents with macros or executables are not accepted")
                if sum(i.file_size for i in archive.infolist()) > 50 * MAX_UPLOAD_BYTES:
                    raise UploadRejected("That document expands to an unreasonable size")
        except zipfile.BadZipFile as exc:
            raise UploadRejected("That does not look like a Word document") from exc
    else:
        if b"\0" in content:
            raise UploadRejected("That does not look like a text file")
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UploadRejected("Text files must be UTF-8") from exc


async def check_upload(
    filename: str, content: bytes, *, max_bytes: int = MAX_UPLOAD_BYTES
) -> CheckedUpload:
    if not content:
        raise UploadRejected("The file is empty")
    if len(content) > max_bytes:
        raise UploadRejected(f"Files can be up to {max_bytes // 1_000_000} MB")
    kind = _kind(filename)
    _check_content(kind, content)
    if (signature := await _scanner.scan(content)) is not None:
        raise UploadRejected(f"The file was blocked by the virus scanner ({signature})")
    return CheckedUpload(filename=PurePath(filename).name, kind=kind, size=len(content))
