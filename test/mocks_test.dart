library dork.test.mocks;

import "dart:io";
import "dart:async";

import "package:unittest/unittest.dart";
import "package:di/di.dart";
import "src/mocks.dart";
import "src/testrunner.dart";

import "package:dork/services/environment.dart";
import "package:dork/services/git.dart";
import "package:dork/services/docker.dart";
import "package:dork/services/ansible.dart";
import "package:dork/services/filesystem.dart";

void main() => TestRunner.runAll();

@Test('Environment')
class EnvironmentTestCase extends MockTestRunner {
  EnvironmentTestCase() : super('/var/source');
  @Test('\'s current directory is "/var/source".')
  void currentDirectory() => expect(this.env.currentDirectory, '/var/source');
}

@Test('Git')
class GitTestRunner extends MockTestRunner {

  GitTestRunner() : super('/var/source');

  Repository simple;
  Repository nested;
  Repository ancestors;

  Future setup() async {
    this.ws.projects.add(new MockProject()
      ..name = 'test'
      ..addInstance(new MockInstance()
        ..commits.add(new MockCommit() ..branch = 'master' ..hash = 1)
        ..commits.add(new MockCommit() ..branch = 'master' ..hash = 2)
      )
      ..addInstance(new MockInstance()
        ..name = 'nested'
        ..commits.add(new MockCommit() ..branch = 'develop' ..hash = 1)
        ..commits.add(new MockCommit() ..branch = 'develop' ..hash = 2)
        ..commits.add(new MockCommit() ..branch = 'develop' ..hash = 3)
      )

      ..addInstance(new MockInstance()
        ..name = 'ancestors'
        ..commits.add(new MockCommit() ..branch = 'develop' ..hash = 1)
        ..commits.add(new MockCommit() ..branch = 'develop' ..hash = 2)
        ..commits.add(new MockCommit() ..branch = 'develop' ..hash = 3)
        ..commits.add(new MockCommit() ..branch = 'develop' ..hash = 4
          ..changed.add('index.php')
          ..changed.add('styles.scss')
        )
        ..commits.add(new MockCommit() ..branch = 'develop' ..hash = 5
          ..changed.add('index.php')
        )
      )
    );
    simple = await git.getRepository(new Directory('/var/source/test'));
    nested = await git.getRepository(new Directory('/var/source/test/nested'));
    ancestors = await git.getRepository(new Directory('/var/source/test/ancestors'));
  }


  @Test('simple branch is "master".')
  simpleBranch() => expect(simple.branch, 'master');

  @Test('simple hash is "2".')
  simpleHash() => expect(simple.commit, '2');

  @Test('nested branch is "develop".')
  nestedBranch() => expect(nested.branch, 'develop');

  @Test('nested hash is "3".')
  nestedHash() => expect(nested.commit, '3');

  @Test('1 is ancestor of 2')
  ancestor() async => expect(await ancestors.isAncestor('1', '2'), true);

  @Test('3 is not ancestor of 2')
  notAncestor() async => expect(await ancestors.isAncestor('3', '2'), false);

  @Test('2 not ancestor of 2')
  equalNotAncestor() async => expect(await ancestors.isAncestor('2', '2'), true);

  @Test('merged commits between 2 and 4')
  mergedCommits() async => expect(await ancestors.mergedCommits('2', '4'), unorderedEquals(['3', '4']));

  @Test('closest ancestor among [3, 1, 2]')
  closestAncestor () async => expect(await ancestors.closestAncestor({'3': '3', '1': '1'}), '3');

  @Test('changed files of one commit')
  changedFilesSingle() async => expect(await ancestors.changedFiles('4', '5'), unorderedEquals(['index.php']));

  @Test('changed files between 2 and 4')
  changedFilesMulti() async => expect(await ancestors.changedFiles('2', '4'), unorderedEquals(['index.php', 'styles.scss']));
}

@Test('Filesystem')
class FileSystemTestRunner extends MockTestRunner {

  FileSystemTestRunner() : super('/var/source/test');

  Future setup() async {
    this.ws.projects.add(new MockProject()
      ..name = "test"
      ..addInstance(new MockInstance()
        ..files = {
          'CHANGELOG.txt': 'VERSION: 8.x',
          'src/index.php': '',
          'src/test.php': '',
        }
      )
    );
  }

  @Test('file content')
  fileContents() async => expect(await fs.file('CHANGELOG.txt'), equals('VERSION: 8.x'));

  @Test('match subdirectory')
  subdirectory() async => expect(await fs.glob('src/*'), unorderedEquals(['src/index.php', 'src/test.php']));

  @Test('match extension')
  extension() async => expect(await fs.glob('**.php'), unorderedEquals(['src/index.php', 'src/test.php']));
}

@Test('Ansible')
class AnsibleTestRunner extends MockTestRunner {
  AnsibleTestRunner() : super('/var/source/test');
  Future setup() async {
    this.ws.projects.add(new MockProject()
      ..name = 'test'
      ..addInstance(new MockInstance()..files = {
        'styles/config.rb': '',
        'VERSION.txt': 'Drupal 8.x',
        'info.php': '<? phpinfo(); ?>',
      })
    );
    this.ws.roles = {
      'php': {
        'matches': '**.php',
      },
      'drupal': {
        'matches': {
          'VERSION.txt': '[D|d]rupal',
        },
      },
      'wordpress': {
        'matches': {
          'VERSION.txt': '[W|o]rdpress',
        }
      },
      'compass': {
        'matches': '**config.rb',
        'tags': [
          { '**.scss': ['compass', 'cache'] },
          { '**.sass': ['compass', 'cache'] },
          { '**.jpg': ['cache'] },
        ],
      },
    };
  }

  @Test('matches drupal and compass role')
  matchRole() async => expect(await this.ansible.matchingRoles(), unorderedEquals(['php', 'drupal', 'compass']));

  @Test('matches sass and cache tag')
  matchTags() async => expect(await this.ansible.matchingTags(['styles/test.sass', 'logo.jpg']), unorderedEquals(['compass', 'cache']));

  @Test('matches no tag')
  matchNoTags() async => expect(await this.ansible.matchingTags(['index.php']), unorderedEquals([]));
}

@Test('Docker')
class DockerTestRunner extends MockTestRunner {
  DockerTestRunner() : super('/var/source/test');

  Future setup() {
    MockProject project = new MockProject() ..name = 'test';
    MockInstance instance = new MockInstance();
    project.addInstance(instance);

    MockCommit commit = new MockCommit()
      ..branch = 'master'
      ..hash = 1;

    MockImage image = new MockImage()
      ..commit = commit;
    project.addImage(image);

    MockContainer container = new MockContainer()
      ..image = image
      ..commit = commit;
    instance.addContainer(container);

    this.ws.projects.add(project);
  }

  @Test('container info.')
  containerInfo() async {
    Container expected = new Container()
      ..id = '1'
      ..image = 'test/1'
      ..name = 'test.test.1'
      ..workDirectory = '/var/source/test'
      ..buildDirectory = '/var/build/test';
    Container actual = await this.docker.containerById('1');
    expect(actual,expected);
  }

  @Test('image info.')
  imageInfo() async {
    Image expected = new Image()
      ..id = '1'
      ..name = 'test/1';
    Image actual = await this.docker.imageById('1');
    expect(actual, expected);
  }

  @Test('create container')
  createContainer() async {
    await this.docker.create('test.test.2', 'test/1', {'/var/source/test':'/var/source'});
    expect((await this.docker.getContainers()).length, 2);
    Container expected = new Container()
      ..id = '2'
      ..image = 'test/1'
      ..name = 'test.test.2'
      ..workDirectory = '/var/source/test'
      ..buildDirectory = '/var/build/test';
    Container actual = await this.docker.containerById('2');
    expect(actual,expected);
  }

  @Test('start a container')
  startContainer()  async {
    await this.docker.start('1');
    expect((await this.docker.containerById('1')).address, '172.17.0.1');
    expect((await this.docker.isAccessible('1')), true);
  }

  @Test('stop a container')
  stopContainer()  async {
    await this.startContainer();
    expect((await this.docker.isAccessible('1')), true);
    await this.docker.stop('1');
    expect((await this.docker.containerById('1')).address, null);
    expect((await this.docker.isAccessible('1')), false);
  }

  @Test('remove a container')
  removeContainer() async {
    await this.docker.remove('1');
    expect((await this.docker.getContainers()).length, 0);
  }

  @Test('commit a container')
  commitContainer() async {
    await this.docker.commit('1', 'test/2');
    Image expected = new Image()
      ..id = '2'
      ..name = 'test/2';
    expect((await this.docker.getImages()).length, 2);
    expect((await this.docker.imageById('2')), expected);
  }
}
