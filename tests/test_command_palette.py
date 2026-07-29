from __future__ import annotations

import unittest

from app_v2.command_palette import rank_actions


class CommandPaletteTests(unittest.TestCase):
    def test_title_prefix_ranks_before_description_match(self) -> None:
        results = rank_actions("disk")
        self.assertTrue(results)
        self.assertTrue(results[0].action.title.casefold().startswith("disk"))

    def test_favorites_rank_first_without_query(self) -> None:
        results = rank_actions("", ("sfc",))
        self.assertEqual(results[0].action.key, "sfc")

    def test_unknown_query_returns_no_results(self) -> None:
        self.assertEqual(rank_actions("kesinlikle-bulunamaz-xyz"), [])


if __name__ == "__main__":
    unittest.main()
