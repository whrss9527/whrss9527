"""Refresh the latest-posts section of README.md from the whrss.com Atom feed."""

import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

FEED_URL = "https://whrss.com/feed"
README_PATH = "README.md"
POST_COUNT = 5
ATOM = "{http://www.w3.org/2005/Atom}"
SECTION = re.compile(r"(<!-- BLOG-POSTS:START -->\n).*?(<!-- BLOG-POSTS:END -->)", re.DOTALL)


def fetch_posts():
    request = urllib.request.Request(FEED_URL, headers={"User-Agent": "whrss9527-profile-readme"})
    with urllib.request.urlopen(request, timeout=30) as response:
        feed = ET.fromstring(response.read())
    # goblog orders the feed like its home page (pinned first, then newest first);
    # <updated> is the last edit time, so re-sorting by it would surface old edited posts
    entries = feed.findall(ATOM + "entry")[:POST_COUNT]
    if not entries:
        raise SystemExit("feed has no entries, README left unchanged")
    return [(entry.findtext(ATOM + "title"), entry.find(ATOM + "link").get("href")) for entry in entries]


def render(posts):
    # slugs can contain spaces or "&" (e.g. "cloudflare-tunnel "), so encode links for Markdown
    return "".join(f"- [{title}]({urllib.parse.quote(link, safe=':/&%')})\n" for title, link in posts)


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
