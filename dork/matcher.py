import inject
from config import Config
from git import Repository
import os
import yaml
from glob import glob
from fnmatch import fnmatch


class Role:
    def __init__(self, meta):
        self.__meta = meta

    @property
    def includes(self):
        """
        :rtype: list[str]
        """
        if 'dependencies' in self.__meta and self.__meta['dependencies'] is list:
            for dep in self.__meta['dependencies']:
                if dep is str:
                    yield dep
                if dep is dict and 'role' in dep:
                    yield dep['role']

    def matching_pattern(self, repository):
        """
        :type repository: Repository
        :rtype: str
        """
        # skip if role has no match patterns
        if 'matches' not in self.__meta['dork']:
            return None

        patterns = self.__meta['dork']['matches']

        # if matches is a simple list, create a default pattern
        if patterns is not dict:
            patterns = {'default': patterns}

        # loop over defined patterns and return the first that matches
        for pattern, filepatterns in patterns:
            fits = len(filepatterns) > 0
            for filepattern in filepatterns:
                f = "%s/%s" % (repository.directory, filepattern)
                if '*' in filepattern:
                    fits = fits and len(glob(f)) > 0
                else:
                    fits = fits and os.path.exists(f)
            if fits:
                return pattern

        # no pattern matched, return None to indicate this role isn't required
        return None

    def matching_tags(self, repository, changeset):
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
            for pattern, taglist in tagpattern:
                for changed_file in changeset:
                    if fnmatch(changed_file, pattern):
                        tags += taglist
        return list(set(tags))


class Matcher:
    """
    :type config: Config
    """
    config = inject.attr(Config)

    def __init__(self):
        pass

    @property
    def roles(self):
        """
        :rtype: list[Role]
        """
        for roles_dir in self.config.ansible_roles_directories:
            for role in os.listdir(roles_dir):
                meta_file = "%s/%s/meta/main.yml" % (roles_dir, role)

                # Skip if name starts with a . or meta file doesn't exist.
                if role.startswith('.') or not os.path.isfile(meta_file):
                    continue
                meta = yaml.load(file(meta_file, 'r'))
                """:type: dict """

                # Skip if this is not a dork-aware role
                if 'dork' not in meta:
                    continue

                yield Role(meta)
