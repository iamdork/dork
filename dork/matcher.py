import config
from git import Repository
import os
import yaml
from glob2 import glob
from fnmatch import fnmatch
import re


class Role:
    def __init__(self, name, meta):
        self.name = name
        self.__meta = meta
        if 'dork' not in self.__meta:
            self.__meta['dork'] = {}

    @classmethod
    def list(cls):
        return [Role(name, meta) for name, meta in get_roles().iteritems()]

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
        if 'build_triggers' not in self.__meta['dork']:
            return {}
        patterns = self.__meta['dork']['build_triggers']

        # if matches is a simple list, create a default pattern
        if not isinstance(patterns, dict):
            patterns = {'default': patterns}
        return patterns

    def matches(self, repository, global_roles = ()):
        return self.name in global_roles or len(self.matching_patterns(repository)) > 0

    __matching_patterns = None

    def matching_patterns(self, repository):
        """
        :type repository: Repository
        :rtype: list[str]
        """
        if self.__matching_patterns is None:
            self.__matching_patterns = []
            # loop over defined patterns and return a list of matches.
            included_matches = []
            for pattern, filepatterns in self.patterns.iteritems():
                if isinstance(filepatterns, list):
                    # If filepatterns is a list, check them all.
                    fits = len(filepatterns) > 0
                    for filepattern in filepatterns:
                        # If it's a dictionary, use key as filepattern and
                        # value as content regex.
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
                        self.__matching_patterns.append(pattern)
                elif isinstance(filepatterns, bool):
                    # If filepatterns is a boolean value, match the pattern accordingly.
                    if filepatterns and pattern == 'global':
                        self.__matching_patterns.append(pattern)
                    elif filepatterns:
                        included_matches.append(pattern)

            if len(self.__matching_patterns) > 0:
                self.__matching_patterns += included_matches

        return self.__matching_patterns

    def matching_tags(self, changeset):
        """
        :type repository: Repository
        :type changeset: list[str]
        :rtype: list[str]
        """
        # skip if there are no tags patterns defined
        tags = []
        if 'update_triggers' not in self.__meta['dork']:
            return []
        for tagpattern in self.__meta['dork']['update_triggers']:
            for pattern, taglist in tagpattern.iteritems():
                for changed_file in changeset:
                    if fnmatch(changed_file, pattern):
                        tags += taglist
        return list(set(tags))


__roles = None
def get_roles(clear=True):
    """
    :rtype: dict[str, dict]
    """
    global __roles
    if __roles is None or clear:
        __roles = {}
        for roles_dir in config.config().ansible_roles_path:
            for role in os.listdir(roles_dir):
                meta_file = "%s/%s/meta/main.yml" % (roles_dir, role)

                # Skip if name starts with a . or meta file doesn't exist.
                if role.startswith('.') or not os.path.isfile(meta_file):
                    continue
                __roles[role] = yaml.load(open(meta_file, 'r'))

                # if any(role == s for s in config.config().global_roles):
                #     if 'dork' not in meta:
                #         meta['dork'] = {}
                #
                #     if 'build_triggers' not in meta['dork']:
                #         meta['dork']['build_triggers'] = {}
                #
                #     if not isinstance(meta['dork']['build_triggers'], dict):
                #         meta['dork']['build_triggers'] = {
                #             'default': meta['dork']['build_triggers']
                #         }
                #
                #     meta['dork']['build_triggers']['global'] = True

                # Skip if this is not a dork-aware role
                # if 'dork' not in meta:
                #     continue
    return __roles
