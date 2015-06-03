"""
Dork configuration system.
Reads system wide settings from various configuration files and provides them
to other components.
"""
from ConfigParser import ConfigParser, NoOptionError

__conf__ = {}


def config(clear=False, project=None):
    """
    Retrieve the configuration settings for the current environment. The
    settings object is cached, as long as the [clear] argument is not True.

    :param bool clear: Boolean value to clear the cached configuration.
      Default ist [True]
    :rtype: Config
    :return: A prepared configuration object.
    """
    global __conf__
    if not __conf__ or clear:
        parser = ConfigParser()
        parser.read([
            '/vagrant/dork.ini',
            '/etc/dork/dork.ini',
            '~/.dork.ini',
        ])
        __conf__ = Config(parser)
    return __conf__

__overrides__ = {}

def override(overrides):
    __overrides__.update(overrides)


class Config:
    def __init__(self, parser=None):
        """
        :param ConfigParser parser: The ConfigParser instance to use.
        """
        self.__parser = parser
        self.__project = None

    def set_project(self, project):
        self.__project = project

    def __default(self, key, default):
        # Abort if key is in overrides
        if key in __overrides__:
            return __overrides__[key]

        value = None
        # If there is a parser, search for variables there
        if self.__parser:
            # First try to set from global section
            if 'global' in self.__parser.sections():
                try:
                    value = self.__parser.get('global', key)
                except NoOptionError:
                    pass
            # Override from project section, if it exists.
            if self.__project is not None:
                section = "project:%s" % self.__project
                if section in self.__parser.sections():
                    try:
                        value = self.__parser.get(section, key)
                    except NoOptionError:
                        pass
        # If nothing was found, search in
        if value is None and key in __overrides__:
            value = __overrides__[key]

        return value if value is not None else default

    # ======================================================================
    # GLOBAL CONFIGURATION PROPERTIES
    # ======================================================================
    @property
    def host_source_directory(self):
        """
        The directory containing the project sources on the host.

        :rtype: str
        """
        return self.__default('host_source_directory', '/var/source')

    @property
    def host_build_directory(self):
        """
        The directory containing the project builds on the host.

        :rtype: str
        """
        return self.__default('host_build_directory', '/var/build')

    @property
    def host_log_directory(self):
        """
        The directory containing the project logs on the host.

        :rtype: str
        """
        return self.__default('host_log_directory', '/var/log/dork')

    @property
    def ansible_roles_path(self):
        """
        A list of directories that are scanned for Ansible roles.

        :rtype: list[str]
        """
        return self.__default('ansible_roles_path',
                              '/etc/ansible/roles:/opt/roles').split(':')


    @property
    def docker_address(self):
        """
        The address used to access docker.

        :rtype: str
        """
        return self.__default('docker_address', 'http://127.0.0.1:2375')

    @property
    def max_containers(self):
        """
        The maximum amount of containers running simultaneously.

        :rtype: int
        """
        return self.__default('max_containers', 0)

    @property
    def startup_timeout(self):
        """
        Number of seconds startup process tries to ssh-connect to a
        container before it fails.
        If set to 0, connection check is omitted.

        :rtype: int
        """
        return self.__default('startup_timeout', 5)

    @property
    def log_level(self):
        """
        The loglevel for dork interal logs.

        :return: string
        """
        return self.__default('log_level', 'warn')

    # ======================================================================
    # PROJECT CONFIGURATION PROPERTIES
    # ======================================================================
    @property
    def root_branch(self):
        """
        The branch considered as "stable".
        :rtype: str
        """
        return self.__default('root_branch', 'master')

    @property
    def dork_source_directory(self):
        """
        Returns the directory containing the project source inside a
        container.

        :rtype: str
        """
        return self.__default('dork_source_directory', '/var/source')

    @property
    def dork_build_directory(self):
        """
        Returns the directory containing the project build inside a
        container.

        :rtype: str
        """
        return self.__default('dork_build_directory', '/var/build')

    @property
    def dork_log_directory(self):
        """
        Returns the directory containing the logs inside a
        container.

        :rtype: str
        """
        return self.__default('dork_log_directory', '/var/log/dork')

    @property
    def base_image(self):
        """
        The base image a container will be created from if no
        valid ancestor is found.

        :rtype: str
        """
        return self.__default('base_image', 'dork/container')

    @property
    def global_roles(self):
        """
        List of roles that are applied on every container, no matter if
        build triggers match or not.
        :return:
        """
        roles = self.__default('global_roles', None)
        if roles is None:
            return []
        else:
            rlist = roles.split(',')
            return map(str.strip, rlist)
    @property
    def skip_tags(self):
        """
        List of tags that should not be executed.
        :return:
        """
        tags = self.__default('skip_tags', None)
        if tags is None:
            return []
        else:
            taglist = tags.split(',')
            return map(str.strip, taglist)

    def variables(self):
        """
        Retrieve project specific settings as dictionary.

        :param str project:
        :rtype: dict[str,str]
        """
        variables = {}
        if self.__parser and 'global' in self.__parser.sections():
            variables.update({key: value for key, value
                              in self.__parser.items('global')
                              if getattr(self, key, None) is None})


        if self.__project is not None:
            section = "project:%s" % self.__project
            if self.__parser and section in self.__parser.sections():
                variables.update({key: value for key, value
                                  in self.__parser.items(section)
                                  if getattr(self, key, None) is None})

        variables.update({key: value for key, value in __overrides__.iteritems()
                         if getattr(self, key, None) is None})
        return variables
