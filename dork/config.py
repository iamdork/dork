"""
Dork configuration system.
Reads system wide settings from various configuration files and provides them
to other components.
"""
from ConfigParser import ConfigParser, NoOptionError
from git import Repository
from matcher import Role

# Initialize the configuration parser.
_parser = ConfigParser()
_parser.read([
    '/vagrant/dork.ini',
    '/etc/dork/dork.ini',
    '~/.dork.ini',
])


class Config:
    def __init__(self):
        self.parser = _parser

    def get_value(self, key, default):
        # First try to set from global section
        if 'global' in self.parser.sections():
            try:
                return self.parser.get('global', key)
            except NoOptionError:
                return default
        return default

    # ======================================================================
    # GLOBAL CONFIGURATION PROPERTIES
    # ======================================================================
    @property
    def ansible_roles_path(self):
        """
        A list of directories that are scanned for Ansible roles.

        :rtype: list[str]
        """
        return self.get_value('ansible_roles_path',
                              '/etc/ansible/roles:/opt/roles').split(':')

    @property
    def host_source_directory(self):
        """
        The directory containing the project sources on the host.

        :rtype: str
        """
        return self.get_value('host_source_directory', '/var/source')

    @property
    def host_build_directory(self):
        """
        The directory containing the project builds on the host.

        :rtype: str
        """
        return self.get_value('host_build_directory', '/var/build')

    @property
    def host_log_directory(self):
        """
        The directory containing the project logs on the host.

        :rtype: str
        """
        return self.get_value('host_log_directory', '/var/log/dork')

    @property
    def dork_source_directory(self):
        """
        Returns the directory containing the project source inside a
        container.

        :rtype: str
        """
        return self.get_value('dork_source_directory', '/var/source')

    @property
    def dork_build_directory(self):
        """
        Returns the directory containing the project build inside a
        container.

        :rtype: str
        """
        return self.get_value('dork_build_directory', '/var/build')

    @property
    def dork_log_directory(self):
        """
        Returns the directory containing the logs inside a
        container.

        :rtype: str
        """
        return self.get_value('dork_log_directory', '/var/log/dork')

    @property
    def docker_address(self):
        """
        The address used to access docker.

        :rtype: str
        """
        return self.get_value('docker_address', 'http://127.0.0.1:2375')

    @property
    def max_containers(self):
        """
        The maximum amount of containers running simultaneously.

        :rtype: int
        """
        return self.get_value('max_containers', 0)

    @property
    def startup_timeout(self):
        """
        Number of seconds startup process tries to ssh-connect to a
        container before it fails.
        If set to 0, connection check is omitted.

        :rtype: int
        """
        return self.get_value('startup_timeout', 5)

    @property
    def log_level(self):
        """
        The loglevel for dork interal logs.

        :return: string
        """
        return self.get_value('log_level', 'warn')

config = Config()

class ProjectConfig(Config):

    def __init__(self, repository):
        """
        :type repository: Repository
        :return:
        """
        Config.__init__(self)
        # Split the directory path.
        self.__segments = repository.directory \
            .replace(config.host_source_directory + '/', '') \
            .split('/')
        self.__settings = {}
        for role in Role.tree(repository):
            self.__settings.update(role.settings)

    def get_value(self, key, default):
        section = "project:%s" % self.project
        if section in self.parser.sections():
            try:
                return self.parser.get(section, key)
            except NoOptionError:
                return Config.get_value(self, key, default)
        else:
            # Override from project section, if it exists.
            if key in self.__settings:
                return self.__settings[key]
            return Config.get_value(self, key, default)

    # ======================================================================
    # PROJECT CONFIGURATION PROPERTIES
    # ======================================================================
    @property
    def project(self):
        return self.__segments[0]

    @property
    def instance(self):
        return self.__segments[-1]

    @property
    def root_branch(self):
        """
        The branch considered as "stable".
        :rtype: list[str]
        """
        return self.get_value('root_branch', ['master', 'develop'])

    @property
    def base_image(self):
        """
        The base image a container will be created from if no
        valid ancestor is found.

        :rtype: str
        """
        return self.get_value('base_image', 'iamdork/container')

    def variables(self):
        """
        Retrieve project specific settings as dictionary.

        :param str project:
        :rtype: dict[str,str]
        """
        variables = {key: value for key, value in self.__settings.iteritems()
                     if getattr(self, key, None) is None}

        if self.parser and 'global' in self.parser.sections():
            variables.update({key: value for key, value
                              in self.parser.items('global')
                              if getattr(self, key, None) is None})


        if self.project is not None:
            section = "project:%s" % self.project
            if self.parser and section in self.parser.sections():
                variables.update({key: value for key, value
                                  in self.parser.items(section)
                                  if getattr(self, key, None) is None})
        return variables
