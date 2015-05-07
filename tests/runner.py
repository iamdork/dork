import unittest
import mock
from dork.runner import apply_roles


class TestRunner(unittest.TestCase):
    @mock.patch('dork.runner.subprocess.call')
    def test(self, call):
        extra_vars = {'foo': 'a', 'bar': 'b'}
        tags = ['foo', 'bar']
        roles = ['dork.shell', 'dork.nginx']
        apply_roles(roles, '172.17.0.2', extra_vars, tags)
        call.assert_called_once_with([
            'ansible-playbook', '-i', mock.ANY, mock.ANY,
            '--extra-vars', mock.ANY, '--tags', 'foo,bar',
        ])