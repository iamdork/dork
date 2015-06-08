import config
from git import Repository
import os
import yaml
import shelve
from fnmatch import fnmatch

cache = shelve.open(os.path.expanduser('~/.dork.cache'))

class Role:
    @classmethod
    def tree(cls, repository):
        if repository.directory not in cache:
            matching_roles = []
            for name in get_roles_metadata(repository):
                role = get_role(name, repository)
                if role.triggered:
                    matching_roles.append(role)
            included_roles = []
            for role in matching_roles:
                if any([r.includes(role.name) for r in matching_roles]):
                    included_roles.append(role.name)

            cache[repository.directory] = [r for r in matching_roles if r.name not in included_roles]
            cache.sync()
        return cache[repository.directory]

    @classmethod
    def clear(cls, repository):
        if cache.has_key(repository.directory):
            del cache[repository.directory]
            cache.sync()

    def __init__(self, name, meta, repository):
        """
        :type name: str
        :type meta: dict
        :type repository: Repository
        :return:
        """
        self.repo = repository
        self.name = name

        self.__meta = meta
        if 'dork' not in self.__meta:
            self.__meta['dork'] = {}

        self.__dependencies = []

        if 'dependencies' in self.__meta and isinstance(self.__meta['dependencies'], list):
            for dep in self.__meta['dependencies']:
                if isinstance(dep, str):
                    self.__dependencies.append(dep)
                if isinstance(dep, dict) and 'role' in dep:
                    self.__dependencies.append(dep['role'])


        if 'build_triggers' in self.__meta['dork']:
            self.__triggers = self.__meta['dork']['build_triggers']

            # if matches is a simple list, create a default pattern
            if not isinstance(self.__triggers, dict):
                self.__triggers = {'default': self.__triggers}
        else:
            self.__triggers = {}

        self.__matched_triggers = []
        self.__enabled_triggers = []
        self.__disabled_triggers = []

        for trigger, patterns in self.__triggers.iteritems():
            if isinstance(patterns, list):
                # If filepatterns is a list, check them all.
                fits = len(patterns) > 0
                for pattern in patterns:
                    # If it's a dictionary, use key as filepattern and
                    # value as content regex.
                    if isinstance(pattern, dict):
                        fits = fits and all([repository.contains_file(gp, cp)
                                             for gp, cp in pattern.iteritems()])
                    elif isinstance(pattern, str):
                        fits = fits and repository.contains_file(pattern)
                if fits:
                    self.__matched_triggers.append(trigger)

            elif isinstance(patterns, bool):
                # If filepatterns is a boolean value, match the pattern accordingly.
                if patterns and trigger == 'global':
                    self.__matched_triggers.append(trigger)
                elif patterns:
                    self.__enabled_triggers.append(trigger)
                else:
                    self.__disabled_triggers.append(trigger)


    @property
    def dependencies(self):
        """
        :rtype: list[str]
        """
        return self.__dependencies

    def includes(self, name):
        """
        Check if this role somehow includes another role.
        :type name:
        :rtype: bool
        """
        return name in self.__dependencies or any([get_role(dep, self.repo).includes(name) for dep in self.__dependencies])

    def triggers(self):
        """
        Recursively get all defined triggers.
        :return:
        """
        triggers = self.__triggers
        for dep in self.__dependencies:
            role = get_role(dep, self.repo)
            triggers.update(role.triggers())
        return triggers

    @property
    def triggered(self):
        return len(self.active_triggers) > 0

    @property
    def active_triggers(self):
        """
        Get a list of triggers that are active for this repository.
        :rtype: list[str]
        """
        if len(self.__matched_triggers) == 0:
            return[]

        triggers = self.__matched_triggers + self.__enabled_triggers
        for dep in self.__dependencies:
            role = get_role(dep, self.repo)
            triggers += role.active_triggers
        return list(set(triggers) - set(self.__disabled_triggers))

    def update_triggers(self, changeset):
        """
        Get a list of required update triggers.
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

    @property
    def settings(self):
        settings = {}
        for dep in self.dependencies:
            settings.update(get_role(dep, self.repo).settings)
        if 'settings' in self.__meta['dork']:
            settings.update(self.__meta['dork']['settings'])
        return settings


__roles = {}

def get_role(name, repository, clear=False):
    """
    :type name: str
    :type repository: Repository
    :rtype: Role
    """
    directory = repository.directory
    if directory in __roles and name in __roles[directory] and not clear:
        return __roles[directory][name]

    __roles[directory] = {}

    if not directory in __metadata:
        get_roles_metadata(repository, clear=True)

    if name not in __metadata[directory]:
        return None

    if not directory in __roles:
        __roles[directory] = {}

    __roles[directory][name] = Role(name, __metadata[directory][name], repository)

    return __roles[directory][name]


__metadata = {}

def get_roles_metadata(repository, clear=False):
    """
    :rtype: dict[str, dict]
    """
    directory = repository.directory
    if directory in __metadata and not clear:
        return __metadata[directory]

    __metadata[directory] = {}
    role_directories = config.config.ansible_roles_path
    project_role_path = repository.directory + '/.dork'
    if os.path.isdir(project_role_path):
        role_directories.append(project_role_path)

    for roles_dir in role_directories:
        for role in os.listdir(roles_dir):
            meta_file = "%s/%s/meta/main.yml" % (roles_dir, role)

            # Skip if name starts with a . or meta file doesn't exist.
            if role.startswith('.') or not os.path.isfile(meta_file):
                continue
            meta = yaml.load(open(meta_file, 'r'))
            if roles_dir == project_role_path:
                if 'dork' not in meta:
                    meta['dork'] = {}
                if 'build_triggers' not in meta['dork']:
                    meta['dork']['build_triggers'] = {}
                meta['dork']['build_triggers']['global'] = True
            # Write metadata back into the cache
            __metadata[directory][role] = meta

    return __metadata[directory]
