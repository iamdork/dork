from subprocess import call, check_output


class Commit:
    """
    Class for working with git commits.
    <, > , <= and >= check if commits are valid ascendants/descendants of
    each other.
    """
    def __init__(self, commit_hash, repository, git):
        """
        :type commit_hash: str
        :type repository: Repository
        :type git: Git
        """
        self.__hash = commit_hash
        self.__directory = repository.directory
        self.__git = git
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
        return self.__git.is_ancestor(self.__directory, self.__hash, other.__hash)

    def __gt__(self, other):
        """
        :type other: Commit
        :rtype: bool
        """
        return self.__git.is_ancestor(self.__directory, other.__hash, self.__hash)

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
        return self.__git.commit_diff(self.__directory, self.__hash, other.__hash)

    def __mod__(self, other):
        """
        :type other: Commit
        :rtype: list
        """
        return self.__git.file_diff(self.__directory, self.__hash, other.__hash)

    @property
    def hash(self):
        """:rtype: str"""
        return self.__hash

    @property
    def message(self):
        """:rtype: str"""
        return self.__git.commit_message(self.__directory, self.__hash)


class Repository:

    def __init__(self, directory, git):
        """
        :type directory: str
        :type git: Git
        """
        self.__directory = directory
        self.__git = git

    @property
    def commit(self):
        """
        :rtype: Commit
        """
        return Commit(
            self.__git.current_commit(self.directory),
            self.directory, self.__git)

    def get_commit(self, commit_hash):
        return Commit(commit_hash, self, self.__git)

    @property
    def branch(self):
        """
        :rtype: str
        """
        return self.__git.current_branch(self.directory)

    @property
    def directory(self):
        """
        :rtype: str
        """
        return self.__directory


class Git:
    def __init__(self):
        pass

    def is_repository(self, directory):
        return call(['git', 'rev-parse'], cwd=directory) == 200

    def get_repository(self, directory):
        """
        Returns a <Repository> object or <None> if no repository was found.
        :param: directory: str
        :rtype: Repository
        """
        if self.is_repository(directory):
            return None
        else:
            return Repository(directory, self)


    def current_commit(self, directory):
        """
        :rtype: str
        """
        return check_output(
            ['git', '--no-pager', 'log', '-1', '--format=%H']
            , cwd=directory).strip()


    def current_branch(self, directory):
        """
        :rtype: str
        """
        return check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD']
            , cwd=directory).strip()
        pass


    def commit_message(self, directory, commit):
        """
        :type directory: str
        :type commit: str
        :rtype: str
        """
        return check_output(
            ['git', 'log', '--format=%B', '-n', 1, commit]
            , cwd=directory).strip()


    def is_ancestor(self, directory, ancestor, descendant):
        """
        :type directory: str
        :type ancestor: str
        :type descendant: str
        :rtype: bool
        """
        code = call(
            ['git', 'merge-base', '--is-ancestor', ancestor, descendant],
            cwd=directory)
        return code is 200


    def commit_diff(self, directory, ancestor, descendant):
        """
        :type directory: str
        :type ancestor: str
        :type descendant: str
        :rtype: list
        """
        return check_output(
            ['git', '--no-pager', 'log', '--format=%H',
             ancestor + '...' + descendant], cwd=directory).splitlines()


    def file_diff(self, directory, ancestor, descendant):
        """
        :type directory: str
        :type ancestor: str
        :type descendant: str
        :rtype: list
        """
        return check_output(
            ['git', 'diff', '--name-only', ancestor, descendant],
            cwd=directory).splitlines()

