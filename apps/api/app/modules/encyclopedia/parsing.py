"""Turn Markdown, HTML and PDF into plain Markdown-ish text plus metadata."""

import io
import re
from datetime import date
from html.parser import HTMLParser
from typing import ClassVar, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.encyclopedia.models import AUTHORITY_TIERS, VOLATILITY

DOMAINS = (
    "data_engineering",
    "data_architecture",
    "ai_ml",
    "genai",
    "software_engineering",
    "leadership",
    "career",
    "security",
    "communication",
    "general",
)
JURISDICTIONS = ("global", "GB", "IE", "EU", "US", "CA", "IN")
_FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


class SourceMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,118}$")
    title: str = Field(min_length=3, max_length=300)
    url: str | None = Field(default=None, max_length=1000)
    publisher: str | None = Field(default=None, max_length=200)
    authority_tier: Literal["official", "standard", "peer_reviewed", "expert_authored", "community"]
    volatility: Literal["stable", "moderate", "volatile"] = "moderate"
    domain: str
    subtopic: str | None = Field(default=None, max_length=120)
    jurisdiction: str = "global"
    licence: str = Field(min_length=3, max_length=200)
    reviewer: str | None = Field(default=None, max_length=200)
    published_date: date | None = None
    last_reviewed: date | None = None

    @field_validator("domain")
    @classmethod
    def _domain(cls, value: str) -> str:
        if value not in DOMAINS:
            raise ValueError(f"domain must be one of {', '.join(DOMAINS)}")
        return value

    @field_validator("jurisdiction")
    @classmethod
    def _jurisdiction(cls, value: str) -> str:
        if value not in JURISDICTIONS:
            raise ValueError(f"jurisdiction must be one of {', '.join(JURISDICTIONS)}")
        return value

    @field_validator("url")
    @classmethod
    def _url(cls, value: str | None) -> str | None:
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("url must start with http:// or https://")
        return value


assert set(AUTHORITY_TIERS) == {
    "official",
    "standard",
    "peer_reviewed",
    "expert_authored",
    "community",
}
assert set(VOLATILITY) == {"stable", "moderate", "volatile"}


class ParseError(ValueError):
    pass


def split_front_matter(document: str) -> tuple[SourceMeta, str]:
    match = _FRONT.match(document)
    if not match:
        raise ParseError("The document must start with a front matter block between --- lines")
    try:
        raw = yaml.safe_load(match.group(1))
        meta = SourceMeta.model_validate(raw)
    except Exception as exc:
        raise ParseError(f"Invalid front matter: {exc}") from exc
    return meta, document[match.end() :]


class _Text(HTMLParser):
    _SKIP: ClassVar[set[str]] = {"script", "style", "noscript", "template"}
    _BLOCK: ClassVar[set[str]] = {
        "p",
        "div",
        "section",
        "article",
        "li",
        "tr",
        "br",
        "ul",
        "ol",
        "table",
        "blockquote",
        "pre",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP:
            self._skip += 1
        elif tag in ("h1", "h2", "h3", "h4"):
            self.parts.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in self._BLOCK:
            self.parts.append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip:
            self._skip -= 1
        elif tag in ("h1", "h2", "h3", "h4"):
            self.parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_markdown(html: str) -> str:
    parser = _Text()
    parser.feed(html)
    text = "".join(parser.parts)
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def pdf_to_markdown(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:
        raise ParseError(f"Could not read the PDF: {exc}") from exc
    text = "\n\n".join(p for p in pages if p)
    if not text:
        raise ParseError("The PDF has no extractable text (is it a scan?)")
    return text


def to_markdown(content: str | bytes, kind: Literal["markdown", "html", "pdf"]) -> str:
    if kind == "pdf":
        if isinstance(content, str):
            raise ParseError("PDF content must be bytes")
        return pdf_to_markdown(content)
    text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
    return html_to_markdown(text) if kind == "html" else text
