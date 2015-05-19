"""
Dork configuration system.
Reads system wide settings from various configuration files and provides them
to other components.
"""
from ConfigParser import ConfigParser, NoOptionError

__conf__ = {}


def config(clear=False):
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

__defaults__ = {}

def config_defaults(defaults):
    __defaults__.update(defaults)


class Config:
    def __init__(self, parser=None):
        """
        :param ConfigParser parser: The ConfigParser instance to use.
        """
        self.__p = parser

    def __default(self, key, default):
        if self.__p and 'dork' in self.__p.sections():
            try:
                return self.__p.get('dork', key)
            except NoOptionError:
                if key in __defaults__:
                    return __defaults__[key]
                return default
        else:
            return default

    @property
    def root_branch(self):
        """
        The branch considered as "stable".
        :rtype: str
        """
        return self.__default('root_branch', 'master')

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
    def docker_address(self):
        """
        The address used to access docker.

        :rtype: str
        """
        return self.__default('docker_address', 'http://127.0.0.1:2375')

    @property
    def dork_user(self):
        """
        The user name used for docker containers and management.

        :rtype: str
        """
        return self.__default('dork_user', 'root')

    @property
    def global_roles(self):
        """
        Name of a role that provides ssh functionality.
        :return:
        """
        roles = self.__default('global_roles', None)
        if roles is None:
            return []
        else:
            rlist = roles.split(',')
            map(str.strip, rlist)
            return rlist

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

    @property
    def global_vars(self):
        if self.__p and 'global' in self.__p.sections():
            return {key: value for key, value in self.__p.items('global')}
        else:
            return {}

    def project_vars(self, project):
        """
        Retrieve project specific settings as dictionary.

        :param str project:
        :rtype: dict[str,str]
        """
        vars = self.global_vars
        if self.__p and project in self.__p.sections():
            vars.update(self.__p.items(project))
        return vars
