import unittest
import mock
from dork import dork


class DorkTest(unittest.TestCase):

    def setUp(self):
        self.mock = mock.MagicMock()

    def test_shout(self):
        d = dork.Dork()
        print(d)
        self.assertTrue(False)