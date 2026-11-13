"""Présentation du HTML non fiable : nettoyage strict puis isolation navigateur."""

import html
import re
from urllib.parse import urlsplit

import nh3

from app.connectors.common import MAX_EMAIL_HTML_LENGTH, html_to_text

HTML_MARKUP = re.compile(
    r"<!doctype\s+html|</?(?:html|head|body|div|p|table|tr|td|th|a|ul|ol|li|h[1-6]|br|strong|b|em|i|blockquote|span|img)\b",
    re.I,
)


def _attribute(tag: str, attribute: str, value: str) -> str | None:
    if tag == "a" and attribute == "href":
        value = value.strip()
        if len(value) > 2048:
            return None
        try:
            url = urlsplit(value)
            if (
                url.scheme not in {"http", "https"}
                or not url.hostname
                or url.username is not None
                or url.password is not None
            ):
                return None
            if any(
                char.isspace() or ord(char) < 32 or ord(char) == 127 or char == "\\"
                for char in value
            ):
                return None
            _ = url.port
        except ValueError:
            return None
    elif attribute in {"colspan", "rowspan"}:
        if (
            not value.isascii()
            or not value.isdecimal()
            or len(value) > 3
            or not 1 <= int(value) <= 100
        ):
            return None
    return value[:2048] if attribute == "href" else value[:500]


CLEANER = nh3.Cleaner(
    tags={
        "p",
        "div",
        "span",
        "br",
        "hr",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "strong",
        "b",
        "em",
        "i",
        "u",
        "s",
        "blockquote",
        "ul",
        "ol",
        "li",
        "pre",
        "code",
        "table",
        "thead",
        "tbody",
        "tfoot",
        "tr",
        "td",
        "th",
        "caption",
        "a",
        "small",
        "sub",
        "sup",
    },
    clean_content_tags={
        "script",
        "style",
        "iframe",
        "object",
        "embed",
        "svg",
        "math",
        "form",
        "textarea",
        "button",
        "select",
        "template",
        "noscript",
        "title",
    },
    attributes={
        "a": {"href", "title"},
        "td": {"colspan", "rowspan"},
        "th": {"colspan", "rowspan"},
    },
    attribute_filter=_attribute,
    set_tag_attribute_values={"a": {"target": "_blank"}},
    url_schemes={"http", "https"},
    url_relative="deny",
    link_rel="noopener noreferrer",
    strip_comments=True,
)

HTML_PREFIX = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="no-referrer"><style>
body{font-family:Arial,sans-serif;font-size:15px;line-height:1.55;margin:0;padding:16px;color:#20242a;background:#fff;overflow-wrap:anywhere}
table{border-collapse:collapse;max-width:100%}td,th{padding:6px;vertical-align:top;border:1px solid #d5dae0}
a{color:#145da0}pre{white-space:pre-wrap}h1,h2,h3{line-height:1.25}blockquote{margin:12px 0;padding-left:12px;border-left:3px solid #c6ced8}
</style></head><body>"""


def render_email_body(body: str, html_body: str = "") -> dict[str, str | None]:
    source = html_body
    if not source and len(body) <= MAX_EMAIL_HTML_LENGTH:
        if HTML_MARKUP.search(body):
            source = body
        elif HTML_MARKUP.search(html.unescape(body)):
            source = html.unescape(body)
    text_body = body or (html_to_text(source) if source else "")
    if not source or len(source) > MAX_EMAIL_HTML_LENGTH:
        return {"html_document": None, "text_body": text_body}
    cleaned = CLEANER.clean(source)
    return {
        "html_document": HTML_PREFIX + cleaned + "</body></html>"
        if cleaned.strip()
        else None,
        "text_body": text_body,
    }
