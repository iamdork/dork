"""
Simple API to docker.
"""

import requests
from paramiko import SSHClient, AutoAddPolicy
from git import Repository
from config import config
from subprocess import check_output
from datetime import datetime
from dateutil.parser import parse as parse_date
import socket
import json


class Container:
    """
    Class representing a container, providing the necessary information and
    operations.
    """
    def __init__(self, data):
        """
        :param dict data: dict data: The dataset returned by the Docker API.
        """
        self.__data = data

    def __str__(self):
        return self.name

    @classmethod
    def list(cls):
        return containers()

    @classmethod
    def create(cls, name, image, volumes, hostname):
        return create(name, image, volumes, hostname)

    @property
    def id(self):
        """
        The containers Id.

        :rtype: str
        """
        return self.__data['Id']

    @property
    def image(self):
        """
        The image's id the container was created from.

        :rtype: str
        """
        return self.__data['Image']

    @property
    def name(self):
        """
        The containers name.

        :rtype: str
        """
        return self.__data['Name']

    @property
    def project(self):
        """
        The containers project. First segment of [Container.name].

        :rtype: str
        """
        return self.name.split('.')[0].strip('/')

    @property
    def instance(self):
        """
        The containers instance. Second segment of [Container.name].

        :rtype: str
        """
        return self.name.split('.')[1]

    @property
    def hash(self):
        """
        The containers git hash. Second segment of [Container.name].

        :rtype: str
        """
        return self.name.split('.')[2]

    @property
    def domain(self):
        """
        The containers internal domain name.

        :rtype: str
        """
        if self.project == self.instance:
            return "%s.dork" % self.project
        else:
            return "%s.%s.dork" % (self.project, self.instance)

    @property
    def running(self):
        """
        Check if the container is running.

        :rtype: bool
        """
        return self.__data['State']['Running']

    @property
    def address(self):
        """
        The containers IP address, or [None] if the container is not running.

        :rtype: str
        """
        if self.running:
            return self.__data['NetworkSettings']['IPAddress']
        else:
            return None

    @property
    def source(self):
        """
        The directory on the host machine, mounted to the containers source
        directory.

        :rtype: str
        """
        directory = None
        for bind in self.__data['HostConfig']['Binds']:
            host = bind.split(':')[0]
            container = bind.split(':')[1]
            if container == config.dork_source_directory:
                directory = host
        return directory

    @property
    def repository(self):
        """
        Retrieve the containers source git repository.

        :rtype: Repository
        """
        return Repository(self.source)

    @property
    def build(self):
        """
        The directory on the host machine, mounted to the containers build
        directory.

        :rtype: str
        """
        directory = None
        for bind in self.__data['HostConfig']['Binds']:
            host = bind.split(':')[0]
            container = bind.split(':')[1]
            if container == config.dork_build_directory:
                directory = host
        return directory

    @property
    def logs(self):
        """
        The directory on the host machine, mounted to the containers build
        directory.

        :rtype: str
        """
        directory = None
        for bind in self.__data['HostConfig']['Binds']:
            host = bind.split(':')[0]
            container = bind.split(':')[1]
            if container == config.dork_log_directory:
                directory = host
        return directory

    @property
    def accessible(self):
        """:rtype: bool"""
        if not self.running:
            return False
        else:
            return _container_accessible(self.address)

    @property
    def time_created(self):
        """:rtype: datetime"""
        return parse_date(self.__data['Created'])

    @property
    def time_started(self):
        """:rtype: datetime"""
        if self.running:
            return parse_date(self.__data['State']['StartedAt'])
        else:
            return None

    @property
    def time_stopped(self):
        """:rtype: datetime"""
        if self.running:
            return None
        else:
            return parse_date(self.__data['State']['FinishedAt'])

    def start(self):
        _container_start(self.id)

    def stop(self):
        _container_stop(self.id)

    def remove(self):
        _container_remove(self.id)

    def rename(self, name):
        _container_rename(self.id, name)

    def commit(self, repo):
        _container_commit(self.id, repo)

    def execute(self, command):
        _container_execute(self.id, command)


class Image:
    def __init__(self, data):
        self.__data = data

    def __str__(self):
        return self.name

    @classmethod
    def list(cls):
        return images()

    @classmethod
    def dangling(cls):
        return _dangling_images()

    @property
    def id(self):
        """:rtype: str"""
        return self.__data['Id']

    @property
    def name(self):
        """:rtype: str"""
        return self.__data['RepoTags'][0].split(':')[0]

    @property
    def project(self):
        """:rtype: str"""
        return self.name.split('/')[0]

    @property
    def hash(self):
        """:rtype: str"""
        return self.name.split('/')[1]

    @property
    def time_created(self):
        """:rtype: datetime"""
        return parse_date(self.__data['Created'])

    def delete(self):
        _image_remove(self.id)


class BaseImage:
    def __init__(self, project, base):
        self.project = project
        self.name = base
        self.hash = 'new'


# ======================================================================
# PUBLIC METHODS
# ======================================================================
__containers = None
def containers(clear=False):
    global __containers
    if __containers is None or clear:
        __containers = [Container(__get('containers/%s/json' % c['Id']))
                          for c in __get('containers/json', query={'all': 1})]
    return __containers


__images = None
def images(clear=False):
    global __images
    if __images is None or clear:
        __images = []
        for i in __get('images/json'):
            data = __get('images/%s/json' % i['Id'])
            if 'RepoTags' in i:
                data['RepoTags'] = i['RepoTags']
                __images.append(Image(data))
    return __images


def create(name, image, volumes, hostname):
    """:type volumes: dict"""
    data = {
        'Hostname': hostname,
        'Image': image,
        'Volumes': {},
        'HostConfig': {
            'Binds': [],
        },
    }
    for host in volumes:
        container = volumes[host]
        data['Volumes'][container] = {}
        data['HostConfig']['Binds'].append("%s:%s" % (host, container))
    __post(
        'containers/create',
        query={'name': name},
        data=data,
        codes=(201,))
    containers(True)


def _dangling_images():
    image_ids = check_output([
        'docker', 'images', '-q', '-f', 'dangling=true'
    ]).splitlines()
    for iid in image_ids:
        yield Image(__get('images/%s/json' % iid))


# ======================================================================
# PROTECTED METHODS
# ======================================================================
def _container_start(cid):
    __post('containers/%s/start' % cid, codes=(204, 304))
    containers(True)


def _container_stop(cid):
    __post('containers/%s/stop' % cid, codes=(204, 304))
    containers(True)


def _container_remove(cid):
    __delete('containers/%s' % cid, codes=(204,))
    containers(True)


def _container_rename(cid, name):
    __post(
        'containers/%s/rename' % cid,
        query={'name': name}, codes=(204,))
    containers(True)


def _container_commit(cid, repo):
    __post(
        'commit',
        query={'container': cid, 'repo': repo},
        codes=(201,))
    images(True)


def _container_accessible(address):
    client = SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(AutoAddPolicy())
    try:
        client.connect(address, username='root', key_filename='/etc/dork-keys/key')
        return True
    except socket.error:
        return False

def _container_execute(id, command):
    execute = json.loads(__post('containers/%s/exec' % id, data= {
        "AttachStdin": False,
        "AttachStdout": True,
        "AttachStderr": True,
        "Tty": False,
        "Cmd": command,
    }, codes=(201,)))
    return __post('exec/%s/start' % execute['Id'], data = {
        "Detach": False,
        "Tty": False,
    }, codes=(200,))



def _image_remove(iid):
    __delete('images/%s' % iid, codes=(200, 409))
    images(True)


# ======================================================================
# PRIVATE METHODS
# ======================================================================
class DockerException(Exception):
    def __init__(self, msg, code):
        super(DockerException, self).__init__(msg)
        self.code = code


def __get(path, query=(), codes=(200,)):
    """
    :param str path:
    :param dict[str,str] query:
    :param list[int] codes:
    :return: json
    """

    result = requests.get(
        "%s/%s" % (config.docker_address, path),
        params=query)

    if result.status_code in codes:
        return result.json()
    else:
        raise DockerException(result.status_code, result.text)


def __post(path, query=(), data=(), codes=(200,)):

    if data:
        result = requests.post(
            "%s/%s" % (config.docker_address, path),
            params=query, json=data)
    else:
        result = requests.post(
            "%s/%s" % (config.docker_address, path),
            params=query)

    if result.status_code not in codes:
        raise DockerException(result.status_code, result.text)
    return result.text


def __delete(path, query=(), codes=(200,)):

    result = requests.delete(
        "%s/%s" % (config.docker_address, path),
        params=query)

    if result.status_code not in codes:
        raise DockerException(result.status_code, result.text)
