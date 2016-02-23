"""
Simple API to docker.
"""

import requests
from git import Repository
from config import config
from subprocess import check_output, call, Popen, PIPE
from dateutil.parser import parse as parse_date
import json
import os
import rx
import rx.subjects
import threading
import re
from rx import Observable


def __eventstream(stream, killsignal):
    process = Popen('docker events', stdout=PIPE, shell=True)
    killsignal.subscribe(lambda v: process.kill())
    for line in iter(process.stdout.readline, ''):
        stream.on_next(line)

eventpattern = re.compile('(.*?) (.*):.*?([a-z]*)$')


def __parseevent(line):
    return {
        'timestamp': eventpattern.match(line).group(1),
        'id': eventpattern.match(line).group(2),
        'event': eventpattern.match(line).group(3),
    }


def __event_object(event):
    for c in containers(True):
        if c.id == event['id']:
            event['container'] = c
    for i in images(True):
        if i.id == event['id']:
            event['image'] = i
    return event


_docker_events = None


def events(killsignal):
    """
    :rtype: Observable
    """
    global _docker_events
    if not _docker_events:
        _docker_events = rx.subjects.Subject()
        thread = threading.Thread(target=__eventstream, args=(_docker_events, killsignal))
        thread.start()
    return _docker_events.map(__parseevent).map(__event_object)


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
    def list(cls, clear=False):
        return containers(clear)

    @classmethod
    def create(cls, name, image, volumes, hostname):
        return create(name, image, volumes, hostname)

    def export(self, filename):
        """
        Export container to a file.
        """
        call('docker export %s > %s' % (self.id, filename), shell=True, stdout=open(os.devnull, 'w'))

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

    def hostPort(self, port):
        return self.__data['NetworkSettings']['Ports']['80/tcp'][0]['HostPort'] if '80/tcp' in self.__data['NetworkSettings']['Ports'] else None

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
    def list(cls, clear=False):
        return images(clear)

    @classmethod
    def fromFile(cls, file, name):
        call('cat %s | docker import - %s' % (file, name), shell=True, stdout=open(os.devnull, 'w'))
        images(True)

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
        __containers = []
        for cid in check_output(['docker', 'ps', '-aq']).splitlines():
            data = json.loads(check_output(['docker', 'inspect', cid]))
            __containers.append(Container(data[0]))
    return __containers


__images = None
def images(clear=False):
    global __images
    if __images is None or clear:
        __images = []
        for i in check_output(['docker', 'images', '-q']).splitlines():
            data = json.loads(check_output(['docker', 'inspect', i]))
            if (data[0]['RepoTags']):
                __images.append(Image(data[0]))
    return __images


def create(name, image, volumes, hostname):
    """:type volumes: dict"""
    cmd = ['docker', 'create', '--name=%s' % name, '-h', hostname, '-P']
    for host in volumes:
        cmd.append('-v')
        cmd.append("%s:%s" % (host, volumes[host]))

    cmd.append(image)
    cmd.append('/usr/bin/supervisord')
    check_output(cmd)
    containers(True)


def _dangling_images():
    image_ids = check_output([
        'docker', 'images', '-q', '-f', 'dangling=true'
    ]).splitlines()
    for iid in image_ids:
        yield Image(json.loads(check_output(['docker', 'inspect', iid]))[0])


# ======================================================================
# PROTECTED METHODS
# ======================================================================
def _container_start(cid):
    check_output(['docker', 'start', cid])
    containers(True)


def _container_stop(cid):
    check_output(['docker', 'stop', cid])
    containers(True)


def _container_remove(cid):
    check_output(['docker', 'rm', cid])
    containers(True)


def _container_rename(cid, name):
    check_output(['docker', 'rename', cid, name])
    containers(True)


def _container_commit(cid, repo):
    check_output(['docker', 'commit', cid, repo])
    images(True)


def _container_accessible(address):
    return call(['ssh', '-F', os.path.expanduser('~/.ssh/config'), address, '/bin/true']) == 0

def _container_execute(id, command):
    check_output(['docker', 'exec', id, command])



def _image_remove(iid):
    call(['docker', 'rmi', iid])
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
