import config
from git import Repository
import os
import yaml
from glob import glob
from fnmatch import fnmatch
import re


class Role:
    def __init__(self, name, meta):
        self.name = name
        self.__meta = meta

    @classmethod
    def list(cls):
        return get_roles()

    @property
    def includes(self):
        """
        :rtype: list[str]
        """
        if 'dependencies' in self.__meta and isinstance(self.__meta['dependencies'], list):
            for dep in self.__meta['dependencies']:
                if isinstance(dep, str):
                    yield dep
                if isinstance(dep, dict) and 'role' in dep:
                    yield dep['role']

    @property
    def patterns(self):
        """:rtype: dict[str,list]"""
        if 'matches' not in self.__meta['dork']:
            return {}
        patterns = self.__meta['dork']['matches']

        # if matches is a simple list, create a default pattern
        if not isinstance(patterns, dict):
            patterns = {'default': patterns}
        return patterns

    def matching_pattern(self, repository):
        """
        :type repository: Repository
        :rtype: str
        """
        matched_patterns = []
        # loop over defined patterns and return the first that matches
        for pattern, filepatterns in self.patterns.iteritems():
            fits = len(filepatterns) > 0
            for filepattern in filepatterns:
                if isinstance(filepattern, dict):
                    for contentpattern, regex in filepattern.iteritems():
                        f = "%s/%s" % (repository.directory, contentpattern)
                        matches = []
                        if '*' in f:
                            matches = glob(f)
                        elif os.path.exists(f):
                            matches.append(f)
                        m = False
                        expr = re.compile(regex)
                        for match in matches:
                            with open(match) as fp:
                                if expr.search(fp.read()):
                                    m = True
                        fits = fits and m
                else:
                    f = "%s/%s" % (repository.directory, filepattern)
                    if '*' in filepattern:
                        fits = fits and len(glob(f)) > 0
                    else:
                        fits = fits and os.path.exists(f)
            if fits:
                matched_patterns.append(pattern)

        # no pattern matched, return None to indicate this role isn't required
        return matched_patterns

    def matching_tags(self, changeset):
        """
        :type repository: Repository
        :type changeset: list[str]
        :rtype: list[str]
        """
        # skip if there are no tags patterns defined
        tags = []
        if 'tags' not in self.__meta['dork']:
            return []
        for tagpattern in self.__meta['dork']['tags']:
            for pattern, taglist in tagpattern.iteritems():
                for changed_file in changeset:
                    if fnmatch(changed_file, pattern):
                        tags += taglist
        return list(set(tags))


def get_roles():
    """
    :rtype: list[Role]
    """
    for roles_dir in config.config().ansible_roles_path:
        for role in os.listdir(roles_dir):
            meta_file = "%s/%s/meta/main.yml" % (roles_dir, role)

            # Skip if name starts with a . or meta file doesn't exist.
            if role.startswith('.') or not os.path.isfile(meta_file):
                continue
            meta = yaml.load(open(meta_file, 'r'))
            """:type: dict """

            # Skip if this is not a dork-aware role
            if 'dork' not in meta:
                continue

            yield Role(role, meta)
