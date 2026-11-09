import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock, patch

import nba
from lib.webhook import (
    _payload_size,
    create_discord_messages,
    create_lark_messages,
    detect_webhook_type,
    send_webhook,
)


class WebhookTests(unittest.TestCase):
    def test_detects_supported_hostnames_without_substring_false_positives(self):
        self.assertEqual(
            detect_webhook_type("https://open.larkoffice.com/open-apis/bot/v2/hook/fake-token"),
            "lark",
        )
        self.assertEqual(
            detect_webhook_type("https://discord.com/api/webhooks/fake-id/fake-token"),
            "discord",
        )
        for url in (
            "https://open.larkoffice.com.evil.example/hook",
            "https://example.test/open.larkoffice.com/hook",
            "https://discord.com.evil.example/webhook",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                detect_webhook_type(url)

    def test_discord_long_content_is_split_within_embed_limit(self):
        content = ("一行内容\n" * 1200).rstrip()
        payloads = create_discord_messages("日报", content)
        self.assertGreater(len(payloads), 1)
        chunks = [payload["embeds"][0]["description"] for payload in payloads]
        self.assertTrue(all(len(chunk) <= 4096 for chunk in chunks))
        self.assertEqual("\n".join(chunks), content)

    def test_lark_long_content_is_split_by_utf8_body_size(self):
        content = "中文内容\n" * 3000
        limit = 1800
        payloads = create_lark_messages("日报", content, limit=limit)
        self.assertGreater(len(payloads), 1)
        self.assertTrue(all(_payload_size(payload) <= limit for payload in payloads))
        chunks = [
            payload["card"]["elements"][0]["text"]["content"].split("\n\n", 1)[1]
            for payload in payloads
        ]
        self.assertEqual("".join(chunks), content)

    @patch("lib.webhook.requests.post")
    def test_lark_sends_every_payload_and_rejects_business_error(self, post):
        ok = Mock(status_code=200)
        ok.json.return_value = {"code": 0}
        post.return_value = ok
        payloads = create_lark_messages("标题", "内容" * 1000, limit=800)
        send_webhook("https://open.larkoffice.com/open-apis/bot/v2/hook/fake", "lark", payloads)
        self.assertEqual(post.call_count, len(payloads))
        for call in post.call_args_list:
            self.assertIsInstance(call.kwargs["data"], bytes)
            self.assertLessEqual(len(call.kwargs["data"]), 800)

        failed = Mock(status_code=200)
        failed.json.return_value = {"code": 19001}
        post.reset_mock()
        post.return_value = failed
        with self.assertRaisesRegex(RuntimeError, "code=19001"):
            send_webhook(
                "https://open.larkoffice.com/open-apis/bot/v2/hook/fake",
                "lark",
                [{"msg_type": "text"}],
            )


class NBADataTests(unittest.TestCase):
    @patch("nba.get_pacific_time_date", return_value=date(2026, 1, 10))
    @patch("nba.requests.get")
    def test_queries_two_days_filters_status_and_deduplicates_events(self, get, _today):
        final = {"id": "same", "status": {"type": {"name": "STATUS_FINAL"}}}
        scheduled = {"id": "future", "status": {"type": {"name": "STATUS_SCHEDULED"}}}
        in_progress = {"id": "live", "status": {"type": {"name": "STATUS_IN_PROGRESS"}}}
        responses = []
        for events in ([final, scheduled], [final, in_progress]):
            response = Mock(status_code=200)
            response.json.return_value = {"events": events}
            responses.append(response)
        get.side_effect = responses

        games, source = nba.get_games_from_espn()

        self.assertEqual(source, "espn")
        self.assertEqual({game["id"] for game in games}, {"same", "live"})
        self.assertEqual(get.call_count, 2)
        self.assertIn("dates=20260110", get.call_args_list[0].args[0])
        self.assertIn("dates=20260109", get.call_args_list[1].args[0])

    def test_alert_identity_and_state_are_stable(self):
        by_id = {"game_id": "game-1", "id": "player-1", "team": "A", "name": "Name"}
        renamed = {**by_id, "name": "Other Name", "points": 55}
        self.assertEqual(nba.alert_identity(by_id), nba.alert_identity(renamed))
        self.assertEqual(
            nba.alert_identity({"game_id": "game-1", "team": "LAL", "name": " Test Player "}),
            "game-1:LAL:test player",
        )

        with tempfile.TemporaryDirectory() as directory:
            state_file = os.path.join(directory, "state.json")
            with patch.dict(os.environ, {"NBA50_STATE_FILE": state_file}):
                current = datetime.now(timezone.utc).isoformat()
                old = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
                nba.save_sent_state({"current": current, "old": old})
                self.assertEqual(nba.load_sent_state(), {"current": current})
                with open(state_file, encoding="utf-8") as state:
                    self.assertEqual(json.load(state)["sent"]["old"], old)

    @patch("nba.get_espn_summary")
    def test_game_status_controls_player_lookup(self, summary):
        scheduled = {"id": "future", "status": {"type": {"name": "STATUS_SCHEDULED"}}}
        self.assertEqual(nba.check_espn_game_for_50_points(scheduled, []), [])
        summary.assert_not_called()


if __name__ == "__main__":
    unittest.main()
