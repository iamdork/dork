library dork.test.cli;

import "dart:io";
import "dart:async";

import "package:unittest/unittest.dart";
import "package:di/di.dart";
import "package:mock/mock.dart";
import "src/mocks.dart";
import "src/testrunner.dart";

import "package:dork/services/environment.dart";
import "package:dork/services/git.dart";
import "package:dork/services/docker.dart";
import "package:dork/services/ansible.dart";
import "package:dork/services/filesystem.dart";
import "package:dork/dork.dart";

void main() => TestRunner.runAll();

@Test('no repository')
class VoidDorkTestCase extends MockTestRunner {
  VoidDorkTestCase() : super('/var/void');

  Future setup() async {
    await this.dork.initialize();
  }

  @Test('state is null')
  dorkState() => expect(this.dork.state, null);

}

@Test('full lifecycle')
class LifecycleTestCase extends MockTestRunner {
  LifecycleTestCase() : super('/var/source/test');

  Future setup() async {
    this.ws.clear();
    this.ws.projects.add(new MockProject()
      ..name = 'test'
      ..addInstance(new MockInstance()
        ..commits.add(new MockCommit() ..branch = 'master' ..hash = 1)
        ..files = {'index.html': '<h1>Test</h1>'}
      )
    );
    this.ws.roles = {
      'html': {
        'matches': 'index.html',
        'tags': [{ '*.html': ['cache'] }]
      }
    };
    await this.dork.initialize();
  }

  @Test('state is State.REPOSITORY')
  dorkState() => expect(this.dork.state, State.REPOSITORY);

  @Test('create')
  create() async {
    await this.dork.create();
    expect(this.ws.containers.length, 1);
  }

  @Test('start')
  start() async {
    await this.create();
    await this.dork.start();
    Container container = await this.docker.containerById('1');
    expect(container.address, '172.17.0.1');
    expect(container.name, 'test.test.new');
    expect(await this.docker.isAccessible('1'), true);
    expect(this.dork.state, State.DIRTY);
  }

  @Test('update')
  update() async {
    await this.start();
    await this.dork.update();
    Container container = await this.docker.containerById('1');
    expect(this.dork.state, State.CLEAN);
    this.ansible.getLogs(callsTo('play', '- hosts: all\n  roles:\n  - html\n', '172.17.0.1 ansible_ssh_user=dork dork_user=dork', [])).verify(happenedOnce);
    expect(container.name, 'test.test.1');
  }

  @Test('change')
  change() async {
    await this.update();
    MockInstance instance = this.ws.findInstance('test', null);
    instance.commits.add(new MockCommit()
      ..branch = 'master' ..hash = 2 ..changed = ['index.html']
    );
    await this.dork.initialize();
    expect(this.dork.state, State.DIRTY);
    await this.dork.update();
    Container container = await this.docker.containerById('1');
    expect(this.dork.state, State.CLEAN);
    this.ansible.getLogs(callsTo('play', '- hosts: all\n  roles:\n  - html\n', '172.17.0.1 ansible_ssh_user=dork dork_user=dork', ['cache'])).verify(happenedOnce);
    expect(container.name, 'test.test.2');
  }

  @Test('stop')
  stop() async {
    await this.start();
    await this.dork.stop();
    Container container = await this.docker.containerById('1');
    expect(container.address, null);
    expect(await this.docker.isAccessible('1'), false);
  }

  @Test('remove')
  remove() async {
    await this.stop();
    await this.dork.remove();
    expect(this.ws.containers.length, 0);
  }
}

@Test('reuse existing container')
class ReuseContainerTestCase extends MockTestRunner {
  ReuseContainerTestCase() : super('/var/source/test');

  setup() async {
    MockCommit commit_a = new MockCommit()
      ..branch = 'master'
      ..hash = 1;

    MockCommit commit_b = new MockCommit()
      ..branch = 'master'
      ..hash = 2;

    this.ws.projects.add(new MockProject()
      ..name = 'test'
      ..addInstance(new MockInstance()
        ..commits.add(commit_a)
        ..commits.add(commit_b)
        ..addContainer(new MockContainer()
          ..image = (new MockImage() ..commit = commit_a)
          ..commit = commit_a
        )
        ..addContainer(new MockContainer()
          ..running = true
          ..image = (new MockImage() ..commit = commit_a)
          ..commit = commit_b
        )
      )
    );
    await this.dork.initialize();
  }

  @Test('status is clean')
  testStatus() => expect(this.dork.state, State.CLEAN);
}

@Test('reuse existing image')
class ReuseImageTestCase extends MockTestRunner {
  ReuseImageTestCase() : super('/var/source/test');

  setup() async {
    MockCommit commit_a = new MockCommit()
      ..branch = 'master'
      ..hash = 1;

    MockCommit commit_b = new MockCommit()
      ..branch = 'master'
      ..hash = 2;

    MockCommit commit_c = new MockCommit()
      ..branch = 'master'
      ..hash = 3;

    MockImage image = new MockImage() ..commit = commit_b;

    this.ws.projects.add(new MockProject()
      ..name = 'test'
      ..addImage(image)
      ..addInstance(new MockInstance()
        ..commits.add(commit_a)
        ..commits.add(commit_b)
        ..commits.add(commit_c)
      )
    );
    await this.dork.initialize();
  }

  @Test('dirty after create, clean after update')
  cleanAfterInitialize() async {
    await this.dork.create();
    await this.dork.start();
    expect(this.dork.state, State.DIRTY);
    await this.dork.update();
    expect(this.dork.state, State.CLEAN);
  }
}

@Test('server testcase')
class ServerTestCase extends MockTestRunner {
  ServerTestCase() : super('/var/source/test/master');

  Future setup() async {
    MockCommit commit_a = new MockCommit() ..branch = 'master' ..hash = 1;
    MockCommit commit_b = new MockCommit() ..branch = 'master' ..hash = 2;
    MockCommit commit_c = new MockCommit() ..branch = 'master' ..hash = 3;
    MockCommit commit_d = new MockCommit() ..branch = 'develop' ..hash = 1;
    MockCommit commit_e = new MockCommit() ..branch = 'develop' ..hash = 2;

    MockImage image = new MockImage() ..commit = commit_a;

    this.ws.projects.add(new MockProject()
      ..name = 'test'
      ..addImage(image)
      ..addInstance(new MockInstance()
        ..name = 'master'
        ..commits.add(commit_a)
        ..commits.add(commit_b)
        ..commits.add(commit_c)
        ..addContainer(new MockContainer()
          ..image = image
          ..commit = commit_a
          ..running = true
        )
      )
      ..addInstance(new MockInstance()
        ..name = 'develop'
        ..commits.add(commit_d)
        ..commits.add(commit_e)
        ..addContainer(new MockContainer()
          ..image = image
          ..commit = commit_e
          ..running = true
        )
      )
    );
    await this.dork.initialize();
  }

  @Test('check state')
  state() async {
    expect(this.dork.state, State.DIRTY);
  }

  @Test('update')
  update() async {
    await this.dork.update();
    this.ansible.getLogs(callsTo('play')).verify(neverHappened);
    this.docker.getLogs(callsTo('rename')).verify(happenedOnce);
    this.docker.getLogs(callsTo('rename', '1', 'test.master.3')).verify(happenedOnce);
    this.docker.getLogs(callsTo('remove', '1')).verify(happenedOnce);
    this.fs.getLogs(callsTo('remove', '/var/source/test/develop')).verify(happenedOnce);
  }
}
