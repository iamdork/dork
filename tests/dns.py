from dork.dns import refresh
import unittest
import mock
from dork.docker import Container

_containers = [
    Container({
        'Name': 'test.a.1',
        'State': {
            'Running': True,
        },
        'NetworkSettings': {
            'IPAddress': '172.17.0.2',
        }
    }),
    Container({
        'Name': 'test.a.2',
        'State': {
            'Running': False,
        },
    }),
    Container({
        'Name': 'test.b.1',
        'State': {
            'Running': True,
        },
        'NetworkSettings': {
            'IPAddress': '172.17.0.3',
        }
    }),
]

_test_append = """
127.0.0.1 localhost
"""

_test_append_result = """
127.0.0.1 localhost
# DORK START
172.17.0.2 test.a.dork
172.17.0.3 test.b.dork
# DORK END
"""

_test_replace = """
127.0.0.1 localhost

# DORK START
172.17.0.1 test.c.dork
# DORK END

1.2.3.4 somedomain
"""

_test_replace_result = """
127.0.0.1 localhost

# DORK START
172.17.0.2 test.a.dork
172.17.0.3 test.b.dork
# DORK END

1.2.3.4 somedomain
"""


def mock_containers():
    return _containers


def mock_open_append(*args):
    return _test_append


def mock_open_replace(*args):
    return _test_replace

@mock.patch('dork.dns.docker.containers', mock_containers)
@mock.patch('dork.dns.call')
class TestDNSRefresh(unittest.TestCase):

    def test_append(self, c):
        with mock.patch('__builtin__.open', mock.mock_open(
                mock=mock.MagicMock(),
                read_data=_test_append)) as m:
            refresh()
            m.assert_has_calls([
                mock.call('/etc/hosts', 'r+'),
                mock.call().__enter__(),
                mock.call().read(),
                mock.call().write(_test_append_result),
                mock.call().__exit__(None, None, None),
            ])

    def test_replace(self, c):
        with mock.patch('__builtin__.open', mock.mock_open(
                mock=mock.MagicMock(),
                read_data=_test_replace)) as m:
            refresh()
            m.assert_has_calls([
                mock.call('/etc/hosts', 'r+'),
                mock.call().__enter__(),
                mock.call().read(),
                mock.call().write(_test_replace_result),
                mock.call().__exit__(None, None, None),
                ])

