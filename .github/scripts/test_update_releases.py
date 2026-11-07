"""Check stable release selection without network access or card writes."""

import io
import json
import unittest
import urllib.error
from unittest.mock import patch

import update_releases


def response(value):
    return io.BytesIO(json.dumps(value).encode("utf-8"))


class LatestReleaseTests(unittest.TestCase):
    @patch("update_releases.urllib.request.urlopen")
    def test_uses_stable_endpoint_without_requesting_betas(self, urlopen):
        stable = {"tag_name": "v0.72.0", "prerelease": False}
        urlopen.return_value = response(stable)

        self.assertEqual(update_releases.latest_release("pop"), stable)

        urlopen.assert_called_once()
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.github.com/repos/whrss9527/pop/releases/latest")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 30)

    @patch("update_releases.urllib.request.urlopen")
    def test_beta_only_fallback_ignores_drafts_and_uses_publication_date(self, urlopen):
        beta = {"tag_name": "v1-beta.2", "draft": False, "published_at": "2026-11-07T00:00:00Z"}
        releases = [
            {"tag_name": "draft", "draft": True, "published_at": "2026-11-08T00:00:00Z"},
            beta,
            {"tag_name": "v1-beta.1", "draft": False, "published_at": "2026-11-06T00:00:00Z"},
        ]
        urlopen.side_effect = [
            urllib.error.HTTPError("latest", 404, "Not Found", None, None),
            response(releases),
        ]

        self.assertEqual(update_releases.latest_release("pop"), beta)

        self.assertEqual(urlopen.call_count, 2)
        self.assertTrue(urlopen.call_args.args[0].full_url.endswith("/releases?per_page=10"))

    @patch("update_releases.urllib.request.urlopen")
    def test_service_error_is_not_hidden_by_beta_fallback(self, urlopen):
        urlopen.side_effect = urllib.error.HTTPError("latest", 503, "Unavailable", None, None)

        with self.assertRaises(urllib.error.HTTPError):
            update_releases.latest_release("pop")

        urlopen.assert_called_once()

    @patch("update_releases.urllib.request.urlopen")
    def test_empty_fallback_has_no_release(self, urlopen):
        urlopen.side_effect = [
            urllib.error.HTTPError("latest", 404, "Not Found", None, None),
            response([]),
        ]

        self.assertIsNone(update_releases.latest_release("pop"))


if __name__ == "__main__":
    unittest.main()
