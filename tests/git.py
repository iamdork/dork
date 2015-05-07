from dork.git import get_repositories, Commit, Repository
from mock import patch
import unittest


class TestRepositoryScan(unittest.TestCase):
    @patch("dork.git.glob", side_effect=[[]])
    @patch("dork.git.call", side_effect=[1])
    def test_no_repository(self, *args):
        num = len([r for r in get_repositories('/var/source/none')])
        self.assertEquals(num, 0)

    @patch("dork.git.glob", side_effect=[[]])
    @patch("dork.git.call", side_effect=[0])
    def test_single_repository(self, *args):
        num = len([r for r in get_repositories('/var/source/single')])
        self.assertEquals(num, 1)

    @patch("dork.git.glob", side_effect=[['/var/source/a/.git',
                                          '/var/source/b/.git',
                                          '/var/source/c/.git',
                                          '/var/source/c/subdirectory/.git',
                                          ]])
    @patch("dork.git.call", side_effect=[1])
    def test_multiple_repositories(self, *args):
        repositories = [r for r in get_repositories('/var/source')]
        num = len(repositories)
        self.assertEquals(num, 3)


class TestRepository(unittest.TestCase):

    def setUp(self):
        self.repository = Repository('/var/source/test')

    def test_directory(self):
        self.assertEqual(self.repository.directory, '/var/source/test')

    @patch('dork.git.check_output', side_effect=['\nabc\n\n'])
    def test_current_commit(self, *args):
        commit = self.repository.current_commit
        self.assertEqual(commit.hash, 'abc')

    @patch('dork.git.check_output', side_effect=['\nabc\n\n'])
    def test_branch(self, co):
        self.assertEqual(self.repository.branch, 'abc')


class TestCommit(unittest.TestCase):
    def setUp(self):
        self.commit_a = Commit('1', Repository('/var/source/test'))
        self.commit_b = Commit('1', Repository('/var/source/test'))
        self.commit_c = Commit('2', Repository('/var/source/test'))
        self.commit_d = Commit('3', Repository('/var/source/test'))

    def test_hash(self):
        self.assertEqual(self.commit_a.hash, '1')

    @patch('dork.git.check_output', side_effect=['my commit message'])
    def test_message(self, *args):
        self.assertEqual(self.commit_a.message, 'my commit message')

    def test_equal(self):
        self.assertTrue(self.commit_a == self.commit_b)
        self.assertTrue(self.commit_a != self.commit_c)

    @patch('dork.git.call', side_effect=[0])
    def test_less_than(self, *args):
        self.assertFalse(self.commit_a < self.commit_b)
        self.assertTrue(self.commit_a < self.commit_c)

    @patch('dork.git.call', side_effect=[0])
    def test_greater_than(self, *args):
        self.assertFalse(self.commit_a > self.commit_b)
        self.assertTrue(self.commit_c > self.commit_a)

    @patch('dork.git.check_output', side_effect=['2\n3\n', '2\n'])
    def test_diff_commits(self, *args):
        self.assertEqual(self.commit_a - self.commit_d, ['2'])
        self.assertEqual(self.commit_a - self.commit_c, [])

    @patch('dork.git.check_output', side_effect=['a\nb\nc\n'])
    def test_diff_files(self, *args):
        self.assertEqual(self.commit_a % self.commit_b, ['a', 'b', 'c'])
