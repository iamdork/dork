import unittest
import mock
from dork.matcher import get_roles, Role
from io import BytesIO
import re
import dork.config as config
import dork.git
import yaml

_meta = dict()

_meta['nodorkrole'] = """
dependencies: []
"""

_meta['dorkrole'] = """
dependencies: []
dork: {}
"""


def mock_is_file(path):
    for name in _meta.keys():
        p = "/etc/ansible/roles/%s/meta/main.yml" % name
        if path == p:
            return True
    return False


def mock_open(path, *args):
    expr = re.compile('/etc/ansible/roles/(.+?)/meta/main.yml')
    found = expr.findall(path)
    return BytesIO(_meta[found[0]])


@mock.patch('dork.matcher.config.config', side_effect=[config.Config()])
@mock.patch('dork.matcher.os.path.isfile', mock_is_file)
@mock.patch('__builtin__.open', side_effect=mock_open)
class TestRoleScan(unittest.TestCase):

    @mock.patch('dork.matcher.os.listdir', side_effect=[[
        '.hidden',
        'nometafile',
        'nodorkrole',
        'dorkrole',
    ]])
    def test_get_roles(self, *args):
        roles = [role for role in get_roles()]
        self.assertEqual(len(roles), 1)

_roles_simple = yaml.load("""
dependencies:
- dep_b
- { role: dep_a }
dork:
  matches:
  - index.php
""")

_roles_complex = yaml.load("""
dependencies: []
dork:
  matches:
    pattern_a:
    - index.php
    - test.php
    pattern_b:
    - "*.txt"
    - "*.php"
  tags:
  - "test/**/*.txt": [a,b]
  - "test/**": [c]
""")

_roles_content = yaml.load("""
dependencies: []
dork:
  matches:
    drupal_7:
    - "*.info": "core\\\s*=\\\s*7.x"
""")



class TestRole(unittest.TestCase):
    def test_includes(self):
        role = Role(_roles_simple)
        self.assertItemsEqual(role.includes, ['dep_a', 'dep_b'])

    @mock.patch('dork.matcher.os.path.exists', side_effect=[True])
    def test_match_default(self, m):
        role = Role(_roles_simple)
        repo = dork.git.Repository('/var/source/test')
        self.assertEqual(['default'], role.matching_pattern(repo))

    @mock.patch('dork.matcher.os.path.exists', side_effect=[False])
    def test_match_none(self, m):
        role = Role(_roles_simple)
        repo = dork.git.Repository('/var/source/test')
        self.assertItemsEqual([], role.matching_pattern(repo))

    @mock.patch('dork.matcher.os.path.exists', side_effect=[True, False])
    @mock.patch('dork.matcher.glob', side_effect=[[], ['foo']])
    def test_match_complex_none(self, *args):
        role = Role(_roles_complex)
        repo = dork.git.Repository('/var/source/test')
        self.assertItemsEqual([], role.matching_pattern(repo))

    @mock.patch('dork.matcher.os.path.exists', side_effect=[True, True])
    @mock.patch('dork.matcher.glob', side_effect=[['foo'], []])
    def test_match_complex_match_first(self, *args):
        role = Role(_roles_complex)
        repo = dork.git.Repository('/var/source/test')
        self.assertItemsEqual(['pattern_a'], role.matching_pattern(repo))

    @mock.patch('dork.matcher.os.path.exists', side_effect=[False, True])
    @mock.patch('dork.matcher.glob', side_effect=[['foo'], ['bar']])
    def test_match_complex_match_second(self, *args):
        role = Role(_roles_complex)
        repo = dork.git.Repository('/var/source/test')
        self.assertEqual(['pattern_b'], role.matching_pattern(repo))

    @mock.patch('dork.matcher.os.path.exists', side_effect=[True, True])
    @mock.patch('dork.matcher.glob', side_effect=[['foo'], ['bar']])
    def test_match_complex_match_both(self, *args):
        role = Role(_roles_complex)
        repo = dork.git.Repository('/var/source/test')
        self.assertItemsEqual(['pattern_a', 'pattern_b'], role.matching_pattern(repo))

    def test_tag_matches(self):
        role = Role(_roles_complex)
        self.assertItemsEqual(['a', 'b', 'c'], role.matching_tags(['test/a/b/c.txt']))

    def test_tag_matches_not(self):
        role = Role(_roles_complex)
        self.assertItemsEqual([], role.matching_tags(['foo.txt']))

    def test_tag_matches_some(self):
        role = Role(_roles_complex)
        self.assertItemsEqual(['c'], role.matching_tags(['test/foo.txt']))

    @mock.patch('dork.matcher.glob', side_effect=[['foo']])
    @mock.patch('__builtin__.open', side_effect=lambda f: BytesIO('name = test\ncore=7.x\n'))
    def test_match_by_content(self, *args):
        role = Role(_roles_content)
        repo = dork.git.Repository('/var/source/test')
        self.assertEquals(['drupal_7'], role.matching_pattern(repo))

    @mock.patch('dork.matcher.glob', side_effect=[['foo']])
    @mock.patch('__builtin__.open', side_effect=lambda f: BytesIO('name: test\ncore: 7.x\n'))
    def test_match_not_by_content(self):
        role = Role(_roles_content)
        repo = dork.git.Repository('/var/source/test')
        self.assertEquals([], role.matching_pattern(repo))
