"""Put the latest version of each app on its project card, from the app's GitHub Releases.

The versions go into releases.json and the cards are rendered again; nothing changes when
no app has shipped since the last run.
"""

import json
import os
import urllib.request

import render_cards

OWNER = "whrss9527"


def latest_release(repo):
    request = urllib.request.Request(
        f"https://api.github.com/repos/{OWNER}/{repo}/releases?per_page=10",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "whrss9527-profile-readme"},
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        releases = [release for release in json.load(response) if not release["draft"]]
    # count prereleases too: Pop shipped only betas at first, and /releases/latest skips them
    return max(releases, key=lambda release: release["published_at"], default=None)


def main():
    versions = {}
    for card in render_cards.CARDS_DATA:
        if release := latest_release(card.slug):
            versions[card.slug] = release["tag_name"]
    if not versions:
        raise SystemExit("no releases found, cards left unchanged")
    render_cards.RELEASES.write_text(json.dumps(versions, indent=2) + "\n", encoding="utf-8")
    render_cards.main()


if __name__ == "__main__":
    main()
