import "dart:io";
import "dart:async";
import "package:di/di.dart";
import "package:glob/glob.dart";
import "package:mock/mock.dart";
import "package:dork/dork.dart";
import "package:dork/services/environment.dart";
import "package:dork/services/git.dart";
import "package:dork/services/docker.dart";
import "package:dork/services/ansible.dart";
import "package:dork/services/filesystem.dart";
import "testrunner.dart";

class MockTestRunner extends TestRunner {
  MockWorkspace ws;
  MockEnvironment env;
  MockFileSystem fs;
  MockAnsible ansible;
  MockGit git;
  MockDocker docker;
  Dork dork;

  MockTestRunner(String directory) {
    ModuleInjector injector = new ModuleInjector([new Module()
      ..bind(MockWorkspace, toImplementation: MockWorkspace)
      ..bind(Environment, toFactory: () => new MockEnvironment(new Directory(directory)))
      ..bind(Git, toImplementation: MockGit)
      ..bind(Docker, toImplementation: MockDocker)
      ..bind(Ansible, toImplementation: MockAnsible)
      ..bind(FileSystem, toImplementation: MockFileSystem)
      ..bind(Dork)
    ]);
    this.ws = injector.get(MockWorkspace);
    this.env = injector.get(Environment) as MockEnvironment;
    this.git = injector.get(Git) as MockGit;
    this.fs = injector.get(FileSystem) as MockFileSystem;
    this.docker = injector.get(Docker) as MockDocker;
    this.ansible = injector.get(Ansible) as MockAnsible;
    this.dork = injector.get(Dork);
  }

  Future teardown() {
    this.ws.clear();
    this.env.clearLogs();
    this.git.clearLogs();
    this.fs.clearLogs();
    this.docker.clearLogs();
    this.ansible.clearLogs();
  }
}

class MockWorkspace {
  List<MockProject> projects = [];
  Map<String, Map> roles = {};

  void clear() {
    this.projects = [];
    this.roles = {};
  }

  List<MockInstance> get instances {
    List<MockInstance> instances = [];
    this.projects.forEach((MockProject project) {
      instances.addAll(project.instances);
    });
    return instances;
  }

  List<MockImage> get images {
    List<MockImage> images = [];
    this.projects.forEach((MockProject project) {
      images.addAll(project.images);
    });
    return images;
  }

  List<MockContainer> get containers {
    List<MockContainer> containers = [];
    this.projects.forEach((MockProject project) {
      project.instances.forEach((MockInstance instance) {
        containers.addAll(instance.containers);
      });
    });
    return containers;
  }

  MockInstance findInstance(String project, String instance) {
    try {
      return this.projects.firstWhere((p) => p.name == project).instances.firstWhere((i) => i.name == instance);
    } catch (exc) {
      return null;
    }
  }
}

class MockProject {
  String name;
  List<MockInstance> instances = [];
  List<MockImage> images = [];

  void addInstance(MockInstance instance) {
    instance.project = this;
    this.instances.add(instance);
  }

  void addImage(MockImage image) {
    image.project = this;
    image.id = 1;
    if (this.images.length > 0) {
      MockImage latest = this.images.reduce((MockImage a, MockImage b) {
        return a.id > b.id ? a.id : b.id;
      });
      image.id = latest.id + 1;
    }
    this.images.add(image);
  }
}

class MockImage {
  int id;
  MockProject project;
  MockCommit commit;
}

class MockInstance {
  String name;
  MockProject project;
  List<MockContainer> containers = [];
  List<MockCommit> commits = [];
  Map<String, String> files = {};
  void addContainer(MockContainer container) {
    container.instance = this;
    container.id = 1;
    if (this.containers.length > 0) {
      MockContainer latest = this.containers.reduce((MockContainer a, MockContainer b) {
        return a.id > b.id ? a.id : b.id;
      });
      container.id = latest.id + 1;
    }
    this.containers.add(container);
  }
}

class MockContainer {
  int id;
  bool running = false;

  MockInstance instance;
  MockImage image;
  MockCommit commit;
}

class MockCommit {
  String branch;
  List<String> changed = [];
  int hash;
}

@proxy
class MockEnvironment extends Mock implements Environment {
  MockEnvironment(Directory dir) {
    when(callsTo('get currentDirectory')).alwaysReturn(dir.absolute.path);
    when(callsTo('get sourceDirectory')).alwaysReturn('/var/source');
    when(callsTo('get buildDirectory')).alwaysReturn('/var/build');
    when(callsTo('get ansibleRolesDirectory')).alwaysReturn([
      '/opt/dork/ansible/roles',
      '/opt/roles',
    ]);
    when(callsTo('get dorkSourceDirectory')).alwaysReturn('/var/source');
    when(callsTo('get dorkBuildDirectory')).alwaysReturn('/var/build');
    when(callsTo('get baseImage')).alwaysReturn('dork/container');
    when(callsTo('get startupTimeout')).alwaysReturn(0);
    when(callsTo('get dockerAddress')).alwaysReturn('http://127.0.0.1:2375');
    when(callsTo('get dorkUser')).alwaysReturn('dork');
  }
}

@proxy
class MockGit extends Mock with Git implements RawGit {
  MockWorkspace _ws;
  Environment _env;
  int parse(String hash) {
    try {
      return int.parse(hash);
    } catch (exc) {
      return -1;
    }
  }

  MockGit(this._ws, this._env) {

    when(callsTo('getRepository')).alwaysCall((Directory dir) async {
      List<String> path = dir.absolute.path.replaceAll(this._env.sourceDirectory + '/', '').split('/');
      MockInstance instance = this._ws.findInstance(path.first, path.length > 1 ? path.last : null);
      if (instance == null || instance.commits.length == 0) return null;
      return new Repository(instance.commits.last.branch, instance.commits.last.hash.toString(), dir, this);
    });

    when(callsTo('_isAncestor')).alwaysCall((Directory dir, String a, String b) async {
      return this.parse(a) <= this.parse(b);
    });

    when(callsTo('_mergedCommits')).alwaysCall((Directory dir, String a, String b) async {
      int from = this.parse(a);
      int to = this.parse(b);
      List<String> result = [];
      while(++from <= to) result.insert(0, from.toString());
      return result;
    });

    when(callsTo('_changedFiles')).alwaysCall((Directory dir, String a, String b) async {
      List<String> path = dir.absolute.path.replaceAll(this._env.sourceDirectory + '/', '').split('/');
      MockInstance instance = this._ws.instances.firstWhere((MockInstance i) {
        return i.project.name == path.first && i.name == (path.length > 1 ? path.last : null);
      });
      if (instance == null || instance.commits.length == 0) return null;

      int from = this.parse(a);
      int to = this.parse(b);
      List<String> changed = [];
      instance.commits.where((MockCommit c) => c.hash > from && c.hash <= to).forEach((MockCommit c) {
        c.changed.forEach((String file) {
          if (!changed.contains(file)) changed.add(file);
        });
      });
      return changed;
    });

  }
}

@proxy
class MockFileSystem extends Mock with FileSystem implements RawFileSystem {
  final Environment env;
  final MockWorkspace ws;

  MockInstance _getInstance() {
    List<String> path = this.env.currentDirectory.replaceAll(this.env.sourceDirectory + '/', '').split('/');
    String project = path.first;
    String instance = (path.length > 1) ? path.last : null;
    return this.ws.instances.firstWhere((i) => i.project.name == project && i.name == instance);
  }

  MockFileSystem(this.env, this.ws) {
    // List<String>
    when(callsTo('glob')).alwaysCall((String pattern) async {
      Glob glob = new Glob(pattern);
      List<String> files = [];
      this._getInstance().files.forEach((String name, String content) {
        if (glob.matches(name)) files.add(name);
      });
      return files;
    });

    // String
    when(callsTo('file')).alwaysCall((String path) async {
      return this._getInstance().files[path];
    });
  }
}

@proxy
class MockAnsible extends Mock with Ansible implements RawAnsible {
  final Environment env;
  final MockWorkspace ws;
  final FileSystem fs;
  MockAnsible(this.env, this.ws, this.fs) {
    // Map<String, Map>
    when(callsTo('getRoles')).alwaysCall(() async => this.ws.roles);
  }
}

@proxy
class MockDocker extends Mock with Docker implements RawDocker {
  final Environment env;
  final MockWorkspace ws;
  int parse(String hash) {
    try {
      return int.parse(hash);
    } catch (exc) {
      return -1;
    }
  }
  MockDocker(this.env, this.ws) {

    // List<Container>
    when(callsTo('getContainers')).alwaysCall(() async {
      List<Container> containers = [];
      this.ws.containers.forEach((MockContainer c) {
        int subnet = (c.id / 255).floor();
        int num = c.id - subnet * 255;
        String path = '/' + c.instance.project.name + (c.instance.name != null ? '/' + c.instance.name : '');
        String iname = c.instance.name != null ? c.instance.name : c.instance.project.name;
        String image = c.image != null ? "${c.instance.project.name}/${c.image.commit.hash}" : this.env.baseImage;
        String hash = c.commit.hash >= 0 ? c.commit.hash.toString() : 'new';
        containers.add(new Container()
          ..id = c.id.toString()
          ..image = image
          ..name = "${c.instance.project.name}.${iname}.${hash}"
          ..address = c.running ? "172.17.${subnet}.${num}" : null
          ..workDirectory = this.env.sourceDirectory + path
          ..buildDirectory = this.env.buildDirectory + path
        );
      });
      return containers;
    });

    // List<Image>
    when(callsTo('getImages')).alwaysCall(() async {
      List<Image> images = [];
      this.ws.images.forEach((MockImage i) {
        images.add(new Image()
          ..id = i.id.toString()
          ..name = "${i.project.name}/${i.commit.hash}"
        );
      });
      return images;
    });

    // void
    when(callsTo('create')).alwaysCall((String name, String img, Map<String, String> volumes) async {
      String pname = name.split('.').elementAt(0);
      String iname = name.split('.').elementAt(1);
      if (iname == pname) iname = null;
      int hash = this.parse(name.split('.').elementAt(2));

      MockProject project = this.ws.projects.firstWhere((MockProject p) => p.name == pname);
      if (project == null) {
        throw new StateError('Unknown project ${pname}.');
      }

      MockInstance instance = project.instances.firstWhere((MockInstance i) => i.name == iname);
      if (instance == null) {
        throw new StateError('Unknown instance ${pname}.${iname}.');
      }

      MockImage image = null;
      if (img != this.env.baseImage) {
        String img_project = img.split('/').elementAt(0);
        int img_hash = int.parse(img.split('/').elementAt(1));
        image = project.images.firstWhere((MockImage i) => i.commit.hash == img_hash);
        if (image == null) {
          throw new StateError('Unknown image ${img}.');
        }
      }

      MockContainer container = new MockContainer()
        ..image = image
        ..commit = (new MockCommit()..hash = hash);
      instance.addContainer(container);
    });

    // void
    when(callsTo('start')).alwaysCall((String container) async {
      MockContainer c = this.ws.containers.firstWhere((MockContainer c) => c.id == int.parse(container));
      if (c == null) throw new StateError('Container with id ${id} doesn\'t exist.');
      c.running = true;
    });

    // void
    when(callsTo('stop')).alwaysCall((String container) async {
      MockContainer c = this.ws.containers.firstWhere((MockContainer c) => c.id == int.parse(container));
      if (c == null) throw new StateError('Container with id ${id} doesn\'t exist.');
      c.running = false;
    });

    // void
    when(callsTo('remove')).alwaysCall((String container) async {
      MockContainer c = this.ws.containers.firstWhere((MockContainer c) => c.id == int.parse(container));
      if (c == null) throw new StateError('Container with id ${id} doesn\'t exist.');
      c.instance.containers.remove(c);
    });

    // void
    when(callsTo('rename')).alwaysCall((String container, String name) async {
      MockContainer c = this.ws.containers.firstWhere((MockContainer c) => c.id == int.parse(container));
      if (c == null) throw new StateError('Container with id ${id} doesn\'t exist.');
      int hash =  this.parse(name.split('.').elementAt(2));
      c.commit.hash = hash;
    });

    // void
    when(callsTo('commit')).alwaysCall((String container, String repository) async {
      MockContainer c = this.ws.containers.firstWhere((MockContainer c) => c.id == int.parse(container));
      if (c == null) throw new StateError('Container with id ${id} doesn\'t exist.');
      int hash = this.parse(repository.split('/').elementAt(1));
      c.instance.project.addImage(new MockImage()..commit=(new MockCommit()..hash=hash));
    });

    // bool
    when(callsTo('isAccessible')).alwaysCall((String container) async {
      MockContainer c = this.ws.containers.firstWhere((MockContainer c) => c.id == int.parse(container));
      if (c == null) throw new StateError('Container with id ${id} doesn\'t exist.');
      return c.running;
    });
  }
}

