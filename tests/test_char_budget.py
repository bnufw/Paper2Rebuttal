import unittest

from char_budget import ensure_within_char_limit


class TestCharBudget(unittest.TestCase):
    def test_under_limit_no_attempts(self):
        r = ensure_within_char_limit("abc", 5, compress=lambda d, lim: d)
        self.assertEqual(r.text, "abc")
        self.assertEqual(r.chars, 3)
        self.assertEqual(r.attempts, 0)

    def test_compresses_to_limit(self):
        def compress(draft: str, limit: int) -> str:
            return (draft or "")[:limit]

        r = ensure_within_char_limit("x" * 10, 5, compress=compress)
        self.assertEqual(len(r.text), 5)
        self.assertGreaterEqual(r.attempts, 1)

    def test_raises_when_cannot_compress(self):
        with self.assertRaises(ValueError):
            ensure_within_char_limit("x" * 10, 5, compress=lambda d, lim: d, max_attempts=2)


if __name__ == "__main__":
    unittest.main()

