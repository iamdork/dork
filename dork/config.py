class Config(object):
    """
    Configuration data component.
    """

    @property
    def host_source_directory(self):
        """
        :rtype: str
        """
        return '/var/source'

    @property
    def host_build_directory(self):
        """
        :rtype: str
        """
        return '/var/build'

    @property
    def ansible_roles_directories(self):
        """
        :rtype: list
        """
        return '/etc/ansible/roles:/opt/roles'.split(':')

    @property
    def dork_source_directory(self):
        """
        :rtype: str
        """
        return '/var/source'

    @property
    def dork_build_directory(self):
        """
        :rtype: str
        """
        return '/var/source'

    @property
    def base_image(self):
        """
        :rtype: str
        """
        return 'dork/container'

    @property
    def docker_address(self):
        """
        :rtype: str
        """
        return 'http://127.0.0.1:2375'

    @property
    def dork_user(self):
        """
        :rtype: str
        """
        return 'dork'
