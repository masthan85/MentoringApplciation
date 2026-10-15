import io
import json
import logging
import zipfile

import pytest
from app.core.logging import JsonFormatter, redact
from app.core.uploads import (
    UploadRejected,
    check_upload,
    set_scanner,
)


def _docx(extra: str | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<w:document/>")
        if extra:
            z.writestr(extra, b"x")
    return buffer.getvalue()


async def test_valid_files_pass() -> None:
    assert (await check_upload("cv.pdf", b"%PDF-1.7\nplain")).kind == "pdf"
    assert (await check_upload("cv.docx", _docx())).kind == "docx"
    assert (await check_upload("notes.txt", "héllo".encode())).kind == "txt"


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("cv.exe", b"MZ"),
        ("cv.pdf", b"not a pdf"),
        ("cv.pdf", b"%PDF-1.7 /OpenAction << /S /JavaScript >>"),
        ("cv.docx", b"plain text"),
        ("cv.docx", _docx("word/vbaProject.bin")),
        ("notes.txt", b"a\0b"),
        ("notes.txt", b"\xff\xfe"),
        ("../cv.pdf", b"%PDF-1.7"),
        (".hidden.pdf", b"%PDF-1.7"),
        ("cv.pdf", b""),
    ],
)
async def test_bad_files_are_rejected(name: str, content: bytes) -> None:
    with pytest.raises(UploadRejected):
        await check_upload(name, content)


async def test_size_limit_and_scanner() -> None:
    with pytest.raises(UploadRejected):
        await check_upload("a.txt", b"x" * 11, max_bytes=10)

    class Dirty:
        async def scan(self, content: bytes) -> str | None:
            return "Eicar-Test"

    set_scanner(Dirty())
    try:
        with pytest.raises(UploadRejected, match="Eicar"):
            await check_upload("a.txt", b"hello")
    finally:
        from app.core.uploads import NullScanner

        set_scanner(NullScanner())


def test_logs_do_not_carry_emails_numbers_or_tokens() -> None:
    assert redact("sent to ada@example.com") == "sent to [email]"
    assert redact("card 4111111111111111") == "card [number]"
    assert "[token]" in redact("Authorization: Bearer abcdefghijklmnop.qrstuv")
    record = logging.LogRecord("x", logging.INFO, "", 0, "user ada@example.com signed in", (), None)
    record.contact = "bob@example.com"
    line = json.loads(JsonFormatter("test").format(record))
    assert "@" not in json.dumps(line)
