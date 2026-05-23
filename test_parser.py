import sys, types, unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

# Stub discord so parser can be imported without the package installed
discord_stub = types.ModuleType("discord")
sys.modules.setdefault("discord", discord_stub)

from parser import is_wordle_results, parse_scores, extract_wordle_num


SAMPLE_YESTERDAY = (
    "**Your group is on a 50 day streak!** 🔥 Here are yesterday's results:\n"
    "👑 1/6: <@756216215894229083>\n"
    "4/6: <@242949886213881857> @Léonydas <@527145299718963200> <@493835936657047552> "
    "<@369539297667317771> @MR\\.penis <@267011733871263745> <@293628108815204352>\n"
    "5/6: <@654724173783891981> <@709837301068333196> <@352367260645589003>"
)

SAMPLE_TODAY = (
    "**Your group is on a 3 day streak!** 🔥 Here are today's results:\n"
    "2/6: <@111111111111111111>\n"
    "X/6: <@222222222222222222>"
)


class TestTrigger(unittest.TestCase):
    def test_yesterday_matches(self):
        self.assertTrue(is_wordle_results(SAMPLE_YESTERDAY))

    def test_today_ignored(self):
        # "today's results" must NOT trigger since we only want the final summary
        self.assertFalse(is_wordle_results(SAMPLE_TODAY))

    def test_unrelated_message(self):
        self.assertFalse(is_wordle_results("hey what's up"))


class TestParseScores(unittest.TestCase):
    def test_all_id_mentions_captured(self):
        scores = parse_scores(SAMPLE_YESTERDAY)
        ids = {uid for uid, _ in scores}
        # The 9 players with <@id> mentions must all be found
        expected = {
            "756216215894229083",
            "242949886213881857",
            "527145299718963200",
            "493835936657047552",
            "369539297667317771",
            "267011733871263745",
            "293628108815204352",
            "654724173783891981",
            "709837301068333196",
            "352367260645589003",
        }
        self.assertEqual(ids, expected)

    def test_attempts_correct(self):
        scores = dict(parse_scores(SAMPLE_YESTERDAY))
        self.assertEqual(scores["756216215894229083"], 1)   # 1/6
        self.assertEqual(scores["242949886213881857"], 4)   # 4/6
        self.assertEqual(scores["654724173783891981"], 5)   # 5/6

    def test_failed_wordle(self):
        content = "Here are yesterday's results:\nX/6: <@999999999999999999>"
        scores = parse_scores(content)
        self.assertEqual(scores, [("999999999999999999", 7)])

    def test_plain_text_mentions_skipped(self):
        # @Léonydas and @MR\.penis have no <@id> → not captured (expected limitation)
        scores = parse_scores(SAMPLE_YESTERDAY)
        ids = {uid for uid, _ in scores}
        self.assertNotIn("Léonydas", ids)

    def test_mentions_after_plain_text_still_captured(self):
        # The key regression: <@id> after a plain-text @name must still be found
        content = "Here are yesterday's results:\n4/6: <@111> @PlainName <@222> <@333>"
        scores = parse_scores(content)
        ids = {uid for uid, _ in scores}
        self.assertIn("111", ids)
        self.assertIn("222", ids)
        self.assertIn("333", ids)

    def test_crown_emoji_before_score(self):
        content = "Here are yesterday's results:\n👑 1/6: <@111111111111111111>"
        scores = parse_scores(content)
        self.assertEqual(scores, [("111111111111111111", 1)])

    def test_empty_message(self):
        self.assertEqual(parse_scores(""), [])


class TestWordleNum(unittest.TestCase):
    def _make_msg(self, embed_title=None, content="", created_at=None):
        msg = MagicMock()
        msg.content = content
        msg.created_at = created_at or datetime(2026, 5, 17, 22, 0, tzinfo=timezone.utc)
        if embed_title:
            embed = MagicMock()
            embed.title = embed_title
            embed.description = None
            embed.footer = None
            msg.embeds = [embed]
        else:
            msg.embeds = []
        return msg

    def test_from_embed(self):
        msg = self._make_msg(embed_title="Wordle No. 1793")
        self.assertEqual(extract_wordle_num(msg), 1793)

    def test_fallback_from_date(self):
        # May 17, 2026 at 22:00 UTC → wordle_num = (May 17 - June 19 2021).days = 1793
        msg = self._make_msg(
            content="Here are yesterday's results:\n1/6: <@1>",
            created_at=datetime(2026, 5, 17, 22, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(extract_wordle_num(msg), 1793)

    def test_no_embed_no_trigger_returns_zero(self):
        msg = self._make_msg(content="hello")
        self.assertEqual(extract_wordle_num(msg), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
