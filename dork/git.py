from subprocess import call, check_output, PIPE
from glob2 import glob, Globber
import os

def _listdir(path):
    if os.path.exists(path + '/.git'):
        return []
    else:
        return os.listdir(path)

def _islink(path):
    return os.path.islink(path) and not os.path.isdir(path)

class GitGlobber(Globber):
    listdir = staticmethod(_listdir)
    islink = staticmethod(_islink)


git_globber = GitGlobber()

def get_repositories(directory):
    """
    Returns a <Repository> object or <None> if no repository was found.
    :param: directory: str
    :rtype: list[Repository]
    """
    if _is_repository(directory):
        yield Repository(directory)
    else:
        repositories = [subdir[:-5] for subdir in git_globber.glob(directory + '/**/.git')]
        for d in repositories:
            if not any([((r + '/') in d and d is not r) for r in repositories]):
                yield Repository(d)


class Commit:
    """
    Class for working with git commits.
    <, > , <= and >= check if commits are valid ascendants/descendants of
    each other.
    """
    def __init__(self, commit_hash, repository):
        """
        :type commit_hash: str
        :type repository: Repository
        """
        self.__hash = commit_hash
        self.__directory = repository.directory
        self.__repo = repository
        pass

    def __eq__(self, other):
        """
        :type other: Commit
        :rtype: bool
        """
        return self.__hash == other.__hash

    def __lt__(self, other):
        """
        :type other: Commit
        :rtype: bool
        """
        return not self.__eq__(other) and _is_ancestor(self.__directory, self.__hash, other.__hash)

    def __gt__(self, other):
        """
        :type other: Commit
        :rtype: bool
        """
        return not self.__eq__(other) and _is_ancestor(self.__directory, other.__hash, self.__hash)

    def __le__(self, other):
        """
        :type other: Commit
        :rtype: bool
        """
        return self.__eq__(other) or self.__lt__(other)

    def __ge__(self, other):
        """
        :type other: Commit
        :rtype: bool
        """
        return self.__eq__(other) or self.__gt__(other)

    def __sub__(self, other):
        """
        :type other: Commit
        :rtype: list
        """
        return _commit_diff(self.__directory, self.__hash, other.__hash)

    def __mod__(self, other):
        """
        :type other: Commit
        :rtype: list
        """
        return _file_diff(self.__directory, self.__hash, other.__hash)

    @property
    def hash(self):
        """:rtype: str"""
        return self.__hash

    @property
    def message(self):
        """:rtype: str"""
        return _commit_message(self.__directory, self.__hash)


class Repository:

    def __init__(self, directory):
        """
        :type directory: str
        """
        self.__directory = directory

    @classmethod
    def scan(cls, directory):
        return get_repositories(directory)

    __current_commit = None
    @property
    def current_commit(self):
        """
        :rtype: Commit
        """
        if self.__current_commit is None:
            self.__current_commit = Commit(_current_commit(self.directory), self)
        return self.__current_commit

    def get_commit(self, commit_hash):
        return Commit(commit_hash, self)

    @property
    def branch(self):
        """
        :rtype: str
        """
        return _current_branch(self.directory)

    @property
    def directory(self):
        """
        :rtype: str
        """
        return self.__directory


def _is_repository(directory):
    """
    Test if a directory actually is a git repository.
    :param directory:
    :return:
    """
    return call(['git', 'rev-parse'], cwd=directory, stderr=PIPE, stdout=PIPE) is 0


def _current_commit(directory):
    """
    :rtype: str
    """
    return check_output(
        ['git', '--no-pager', 'log', '-1', '--format=%H']
        , cwd=directory).strip()


def _current_branch(directory):
    """
    :rtype: str
    """
    return check_output(
        ['git', 'rev-parse', '--abbrev-ref', 'HEAD']
        , cwd=directory).strip()
    pass


def _commit_message(directory, commit):
    """
    :type directory: str
    :type commit: str
    :rtype: str
    """
    return check_output(
        ['git', 'log', '--format=%B', '-n', '1', commit]
        , cwd=directory).strip()


__ancestors = {}
def _is_ancestor(directory, ancestor, descendant):
    """
    :type directory: str
    :type ancestor: str
    :type descendant: str
    :rtype: bool
    """
    key = '%s:%s:%s' %(directory, ancestor, descendant)

    global __ancestors
    if key not in __ancestors:
        if ancestor == descendant:
            return False
        elif ancestor == "new":
            return True
        elif descendant == "new":
            return False
        else:
            __ancestors[key] = call(
                ['git', 'merge-base', '--is-ancestor', ancestor, descendant],
                cwd=directory, stdout=PIPE, stderr=PIPE) is 0
    return __ancestors[key]


__commit_diffs = {}
def _commit_diff(directory, a, b):
    """
    :type directory: str
    :type a: str
    :type b: str
    :rtype: list
    """
    key = '%s:%s:%s' % (directory, a, b)
    global __commit_diffs
    if key not in __commit_diffs:
        __commit_diffs[key] = check_output(
            ['git', '--no-pager', 'log', '--format=%H',
             a + '...' + b], cwd=directory).splitlines()
    return __commit_diffs[key]


__file_diffs = {}
def _file_diff(directory, a, b):
    """
    :type directory: str
    :type a: str
    :type b: str
    :rtype: list
    """
    key = '%s:%s:%s' % (directory, a, b)
    global __file_diffs
    if key not in __file_diffs:
        __file_diffs[key] = check_output(
            ['git', 'diff', '--name-only', a, b],
            cwd=directory).splitlines()
    return __file_diffs[key]
