import requests
import inject
from config import Config
from subprocess import check_output


class Container:
    def __init__(self, data, docker):
        """
        :param: dict data:
        :param: Docker docker:
        :return:
        """
        self.__data = data
        self.__docker = docker

    @property
    def id(self):
        """:rtype: str"""
        return self.__data['Id']

    @property
    def image(self):
        """:rtype: str"""
        return self.__data['Image']

    @property
    def name(self):
        """:rtype: str"""
        return self.__data['Name']

    @property
    def project(self):
        """:rtype: str"""
        return self.name.split('.')[0]

    @property
    def instance(self):
        """:rtype: str"""
        return self.name.split('.')[1]

    @property
    def hash(self):
        """:rtype: str"""
        return self.name.split('.')[2]

    @property
    def domain(self):
        return "%s.%s.dork" % (self.project, self.instance)

    @property
    def running(self):
        """:rtype: bool"""
        return self.__data['State']['Running']

    @property
    def address(self):
        """:rtype: str"""
        if self.running:
            return self.__data['NetworkSettings']['IPAddress']
        else:
            return None

    @property
    def source(self):
        """:rtype: str"""
        directory = None
        for bind in self.__data['HostConfig']['Binds']:
            host = bind.split(':')[0]
            container = bind.split(':')[1]
            if container == '/var/source':
                directory = host
            pass
        return directory

    @property
    def build(self):
        """:rtype: str"""
        directory = None
        for bind in self.__data['HostConfig']['Binds']:
            host = bind.split(':')[0]
            container = bind.split(':')[1]
            if container == '/var/build':
                directory = host
            pass
        return directory

    @property
    def accessible(self):
        """:rtype: bool"""
        return self.__docker.container_accessible(self.id)

    def start(self):
        self.__docker.container_start(self.id)

    def stop(self):
        self.__docker.container_stop(self.id)

    def remove(self):
        self.__docker.container_remove(self.id)

    def rename(self, name):
        self.__docker.container_rename(self.id, name)

    def commit(self, image):
        self.__docker.container_rename(self.id, image)


class Image:
    def __init__(self, data, docker):
        """
        :type docker: Docker
        """
        self.__data = data
        self.__docker = docker

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

    def delete(self):
        self.__docker.image_remove(self.id)


class Docker:
    """
    :type config: Config
    """
    config = inject.attr(Config)

    def __init__(self):
        pass

    # ======================================================================
    # PUBLIC METHODS
    # ======================================================================
    @property
    def containers(self):
        for c in self.__get('containers/json', query={all: 1}):
            yield Container(self.__get('/containers/%s/json' % c['Id']), self)

    @property
    def images(self):
        for i in self.__get('images/json'):
            yield Image(self.__get('/images/%s/json' % i['Id']), self)

    def create(self, name, image, volumes):
        """:type volumes: dict"""
        data = {
            'Image': image,
            'Volumes': {},
            'HostConfig': {
                'Binds': [],
            },
        }
        for host, container in volumes:
            data['Volumes'][container] = {}
            data['HostConfig']['Binds'].append("%s:%s" % (host, container))
        self.__post(
            '/containers/create',
            query={'name': name},
            data=data,
            codes=(201,))

    def cleanup(self):
        image_ids = check_output([
            'docker', 'images', '-q', '-f', 'dangling=true'
        ]).splitlines()
        for iid in image_ids:
            Image(self.__get('/images/%s/json' % iid, self), self).delete()

    # ======================================================================
    # PROTECTED METHODS
    # ======================================================================
    def container_start(self, cid):
        self.__post('/containers/%s/start' % cid, codes=(204, 304))

    def container_stop(self, cid):
        self.__post('/containers/%s/stop' % cid, codes=(204, 304))

    def container_remove(self, cid):
        self.__delete('/containers/%s' % cid, codes=(204,))

    def container_rename(self, cid, name):
        self.__post(
            '/containers/%s/rename' % cid,
            query={'name': name}, codes=(204,))

    def container_commit(self, cid, repo):
        self.__post(
            '/commit',
            query={'container': cid, 'repo': repo},
            codes=(201,))

    def container_accessible(self, cid):
        return "sshd.pid" in self.__exec(cid, 'ls /var/run/ | grep sshd.pid')

    def image_remove(self, iid):
        self.__delete('/images/%s' % iid, codes=(200,))

    # ======================================================================
    # PRIVATE METHODS
    # ======================================================================
    def __get(self, path, query=(), codes=(200,)):
        """
        :param str path:
        :param dict[str,str] query:
        :param list[int] codes:
        :return: json
        """

        result = requests.get(
            "%s/%s" % (self.config.docker_address, path),
            params=query)

        if result.status_code in codes:
            return result.json()
        else:
            raise Exception(result.text)

    def __post(self, path, query=(), data=(), codes=(200,)):

        result = requests.post(
            "%s/%s" % (self.config.docker_address, path),
            params=query, data=data)

        if result.status_code not in codes:
            raise Exception(result.text)

    def __exec(self, cid, command, codes=(200,)):

        process = self.__post(
            'containers/%s/exec' % cid,
            data={
                'AttachStdin': False,
                'AttachStdout': True,
                'AttachStderr': True,
                'Tty': False,
                'Cmd': [command]},
            codes=(204,))

        result = requests.post(
            '%s/exec/%s/start' % (self.config.docker_address, process['Id']),
            data={'Detach': False, "Tty": False})

        if result.status_code is not codes:
            raise Exception(result.text)
        else:
            return result.text

    def __delete(self, path, query=(), codes=(200,)):

        result = requests.delete(
            "%s/%s" % (self.config.docker_address, path),
            params=query)

        if result.status_code not in codes:
            raise Exception(result.text)
