import unittest
from mock import patch
import requests_mock
import json
from dork.docker import *
from config import config

_containers = [{
    "Id": "1",
    "Image": "1",
    "Name": "test.a.1",
    "Created": "2013-05-07T14:51:42.041847+02:00",
    "State": {
        "Running": True,
    },
    "NetworkSettings": {
        "IPAddress": "172.17.0.1",
    },
    "HostConfig": {
        "Binds": [
            "/var/source/test/a:/var/source",
            "/var/build/test/a:/var/build",
        ]
    }
}, {
    "Id": "2",
    "Image": "1",
    "Name": "test.b.2",
    "State": {
        "Running": False,
    },
    "HostConfig": {
        "Binds": [
            "/var/source/test/a:/var/source",
            "/var/build/test/a:/var/build",
        ]
    }
}, {
    "Id": "3",
    "Image": "2",
    "Name": "test.a.3",
    "State": {
        "Running": False,
    },
    "HostConfig": {
        "Binds": [
            "/var/source/test/a:/var/source",
            "/var/build/test/a:/var/build",
        ]
    }
}]

_images = [{
    "Id": "1",
    "RepoTags": ["test/1"]
}, {
    "Id": "2",
    "RepoTags": ["test/2"]
}]


def fill_mock(rm):
    docker = config().docker_address
    rm.get("%s/containers/json" % docker, text=json.dumps(_containers))
    rm.get("%s/images/json" % docker, text=json.dumps(_images))
    for c in _containers:
        rm.get("%s/containers/%s/json" % (docker, c['Id']), text=json.dumps(c))
    for i in _images:
        rm.get("%s/images/%s/json" % (docker, i['Id']), text=json.dumps(i))


@requests_mock.mock()
class TestListings(unittest.TestCase):
    def test_containers(self, rm):
        fill_mock(rm)
        self.assertEqual(3, len([c for c in containers()]))

    def test_images(self, rm):
        fill_mock(rm)
        self.assertEqual(2, len([c for c in images()]))


@requests_mock.mock()
class TestCreate(unittest.TestCase):
    def test_success(self, rm):
        address = config().docker_address + '/containers/create?name=test.a.2'
        rm.post(address, status_code=201)
        create('test.a.2', 'test/1', {'/var/source/test/a': '/var/source'})
        self.assertTrue(rm.called)

    def test_failure(self, rm):
        address = config().docker_address + '/containers/create?name=test.a.2'
        rm.post(address, status_code=500, text="Something went wrong.")
        self.assertRaises(
            DockerException, create,
            'test.a.2', 'test/1', {'/var/source/test/a': '/var/source'})
        self.assertTrue(rm.called)


@requests_mock.mock()
@patch('dork.docker.check_output')
class TestCleanup(unittest.TestCase):
    def test_success(self, rm, co):
        fill_mock(rm)
        rm.delete(config().docker_address + '/images/1', status_code=200)
        rm.delete(config().docker_address + '/images/2', status_code=200)
        co.side_effect = '1\n2\n'
        cleanup()


@requests_mock.mock()
class TestContainer(unittest.TestCase):
    def test_properties(self, rm):
        fill_mock(rm)
        c = containers().next()
        self.assertEqual('1', c.id)
        self.assertEqual('1', c.image)
        self.assertEqual('test.a.1', c.name)
        self.assertEqual('test', c.project)
        self.assertEqual('a', c.instance)
        self.assertEqual('1', c.hash)
        self.assertEqual('test.a.dork', c.domain)
        self.assertTrue(c.running)
        self.assertEqual('172.17.0.1', c.address)
        self.assertEqual('/var/source/test/a', c.source)
        self.assertEqual('/var/build/test/a', c.build)

    def test_dates(self, rm):
        fill_mock(rm)
        c = containers().next()
        self.assertEqual(7, c.time_created.day)

    @patch('dork.docker.SSHClient.connect')
    def test_accessible(self, rm, ssh_mock):
        fill_mock(rm)
        c = containers().next()
        self.assertTrue(c.accessible)

    @patch('dork.docker.SSHClient.connect')
    def test_not_accessible(self, rm, ssh_mock):
        fill_mock(rm)
        ssh_mock.side_effect = SSHException('Thou shall not pass!')
        c = containers().next()
        self.assertFalse(c.accessible)

    def test_start(self, rm):
        fill_mock(rm)
        rm.post('/containers/1/start', status_code=204)
        c = containers().next()
        c.start()

    def test_stop(self, rm):
        fill_mock(rm)
        rm.post('/containers/1/stop', status_code=204)
        c = containers().next()
        c.stop()

    def test_remove(self, rm):
        fill_mock(rm)
        rm.delete('/containers/1', status_code=204)
        c = containers().next()
        c.remove()

    def test_rename(self, rm):
        fill_mock(rm)
        rm.post('/containers/1/rename?name=test.a.3', status_code=204)
        c = containers().next()
        c.rename('test.a.3')

    def test_commit(self, rm):
        fill_mock(rm)
        rm.post('/commit?repo=test%2F5&container=1', status_code=201)
        c = containers().next()
        c.commit('test/5')


@requests_mock.mock()
class TestImage(unittest.TestCase):
    def test_properties(self, rm):
        fill_mock(rm)
        i = images().next()
        self.assertEqual('1', i.id)
        self.assertEqual('test/1', i.name)
        self.assertEqual('test', i.project)
        self.assertEqual('1', i.hash)

    def test_delete(self, rm):
        fill_mock(rm)
        i = images().next()
        rm.delete('/images/1', status_code=200)
        i.delete()
