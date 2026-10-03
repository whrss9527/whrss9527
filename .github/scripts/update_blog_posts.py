"""Refresh the latest-posts section of README.md from the blog.whrss.com Atom feed."""

import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

FEED_URL = "https://blog.whrss.com/feed"
README_PATH = "README.md"
POST_COUNT = 5
ATOM = "{http://www.w3.org/2005/Atom}"
SECTION = re.compile(r"(<!-- BLOG-POSTS:START -->\n).*?(<!-- BLOG-POSTS:END -->)", re.DOTALL)
# the blog shows its dates in Beijing time, the feed gives them in UTC
BEIJING = timezone(timedelta(hours=8))
# C0 controls that XML 1.0 forbids even as character references; none of them can be part
# of a multi-byte UTF-8 sequence, so they can be dropped from the raw bytes
NOT_XML = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def fetch_posts():
    request = urllib.request.Request(FEED_URL, headers={"User-Agent": "whrss9527-profile-readme"})
    with urllib.request.urlopen(request, timeout=30) as response:
        # the feed carries every post in full, and an old one pasted from editor.md has a
        # stray backspace (\x08) that makes the whole feed malformed for a strict parser
        feed = ET.fromstring(NOT_XML.sub(b"", response.read()))
    # the blog orders the feed like its home page (pinned first, then newest first);
    # <updated> is the last edit time, so re-sorting by it would surface old edited posts
    entries = feed.findall(ATOM + "entry")[:POST_COUNT]
    if not entries:
        raise SystemExit("feed has no entries, README left unchanged")
    return [
        (entry.findtext(ATOM + "title"), entry.find(ATOM + "link").get("href"), entry.findtext(ATOM + "published"))
        for entry in entries
    ]


def day(published):
    """The Beijing date of an RFC 3339 timestamp such as 2026-10-02T02:00:00.000Z."""
    moment = datetime.fromisoformat(published.replace("Z", "+00:00"))
    return moment.astimezone(BEIJING).date().isoformat()


def render(posts):
    """One post per line, each opening with a mark, so a title that wraps on a phone still reads as one.

    Atom makes <published> optional. When every post has one, the date is the mark and the lines
    start flush with the page, like git log; otherwise they fall back to a bulleted list.
    """
    dated = all(published for _, _, published in posts)
    lines = []
    for title, link, published in posts:
        title = title.replace("[", r"\[").replace("]", r"\]")
        # slugs can contain spaces or "&" (e.g. "cloudflare-tunnel "), so encode links for Markdown
        post = f"[{title}]({urllib.parse.quote(link, safe=':/&%')})"
        lines.append(f"`{day(published)}` {post}" if dated else f"- {post}")
    return ("<br>\n" if dated else "\n").join(lines) + "\n"


def main():
    posts = fetch_posts()
    with open(README_PATH, encoding="utf-8") as file:
        readme = file.read()
    readme, count = SECTION.subn(lambda match: match.group(1) + render(posts) + match.group(2), readme)
    if count != 1:
        raise SystemExit("README.md must contain exactly one BLOG-POSTS section")
    with open(README_PATH, "w", encoding="utf-8") as file:
        file.write(readme)


if __name__ == "__main__":
    main()
