import unittest

from tools.query import _interp, hook_height


class HookHeightTest(unittest.TestCase):
    def test_boom_reaches_required_height(self):
        # LTM 1450-8.1: pluma 26,6 m a 15 m de radio -> ~23,62 m de gancho
        self.assertAlmostEqual(hook_height(26.6, 15.0), 23.62, places=2)

    def test_boom_too_short_returns_none(self):
        self.assertIsNone(hook_height(10.0, 15.0))


class InterpolationTest(unittest.TestCase):
    def test_between_two_points(self):
        self.assertAlmostEqual(
            _interp([(3.0, 100.0), (5.0, 80.0)], 4.0), 90.0)

    def test_below_min_uses_first_value(self):
        self.assertEqual(_interp([(3.0, 100.0)], 2.0), 100.0)

    def test_beyond_max_is_not_reachable(self):
        self.assertIsNone(_interp([(3.0, 100.0)], 4.0))


if __name__ == "__main__":
    unittest.main()
