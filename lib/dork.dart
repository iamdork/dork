/// Main library for managing Docker development containers.
library dork.dork;

import "dart:async";
import "dart:io";

import "package:glob/glob.dart";

import "package:dork/services/docker.dart";
import "package:dork/services/git.dart";
import "package:dork/services/environment.dart";
import "package:dork/services/ansible.dart";
import "package:dork/services/filesystem.dart";

/// Enumeration of the different states a [Dork] can be in.
///
/// The states follow a certain this order. A state can only be fullfilled if
/// its predecessor is.
///
/// [State.REPOSITORY]
/// : [Dork.directory] exists and is a valid git repository. There is no Docker
///   container with name [Dork.container].
///
/// [State.CONTAINER]
/// : A Docker container with name [Dork.container] exists, but it's not
///   running.
///
/// [State.DIRTY]
/// : The docker container with name [Dork.container] is running, but the image
///   tag match HEAD in [Dork.directory].
///
/// [State.CLEAN]
/// : The docker container with name [Dork.container] is running and
///   image tag matches HEAD in [Dork.directory].
enum State { REPOSITORY, CONTAINER, DIRTY, CLEAN }

/// Cleaning behavior types.
///
/// [Dork.update] automatically attempts to clean up existing containers. Based
/// on the the checkout directory, [Dork.mode] will determine different cleaning
/// behaviors.
///
/// [Mode.WORKSTATION]
/// : Assumes that there is always only one instance of a project at the same
///   time. If a dork is started, all other ones of the same project will be
///   halted. If [Dork.update] identifies a removable container, it will be
///   removed. Applies if the checkout directory is only one level deep.
///
/// [Mode.SERVER]
/// : If the checkout directory equals the git branch, [Dork.update] assumes
///   that it's an automatic CI-Server checkout, and will kill unnecessary
///   containers and *remove their work- and build directories*. Starting
///   one container does not affect any others.
///
/// [Mode.MANUAL]
/// : If the checkout directory is multiple levels deep but does not match
///   the git branch, [Dork.start] and [Dork.update] won't do any cleanups.
enum Mode { WORKSTATION, SERVER, MANUAL }

class Dork {

  final Environment env;
  final Git git;
  final Docker docker;
  final Ansible ansible;
  final FileSystem fs;

  State _state;
  Directory _dir;

  Repository _repository;
  Container _container;

  String _project;
  String _instance;

  Repository get repository {
    if (this._repository == null) throw new StateError('No repository found.');
    return this._repository;
  }

  Container get container {
    if (this._container == null) throw new StateError('No container found.');
    return this._container;
  }

  /// Default constructor.
  ///
  /// Creates a new [Dork] based on a directory.
  Dork(this.env, this.git, this.docker, this.ansible, this.fs) {
    this._dir = new Directory(this.env.currentDirectory);

    List<String> subdir = this._dir.absolute.path
      // Remove the base directory.
      .replaceAll(this.env.sourceDirectory + '/', '')
      // Remove any trailing slashes.
      .replaceAll(r'\/$', '')
      // Split it into segments
      .split('/');

    // The first directory below the source base is considered the project.
    this._project = subdir.first;

    // The last one is the instance. Project and instance may be the same.
    // Development machines probably run only one instance per project.
    this._instance = subdir.last;
  }

  /// Get the management mode.
  ///
  /// Determines the current management mode based on git branch and directory.
  Mode get mode {
    String dir = this._dir.absolute.path.replaceAll(this.env.sourceDirectory + '/', '');
    if (dir.split('/').length == 1) return Mode.WORKSTATION;
    if (dir.replaceAll(this.project + '/', '') == this.repository.branch) return Mode.SERVER;
    return Mode.MANUAL;
  }

  /// Get the current [State].
  ///
  /// Use [Dork.initialize] to update this information.
  State get state => this._state;

  /// The absolute source directory path of the project.
  String get directory => this._dir.absolute.path;

  /// The project identifier as [String].
  ///
  /// The name of first directory inside [Environment.sourceDirectory].
  String get project => this._project;

  /// The instance identifier.
  ///
  /// The instance identifier is generated from the last segment of
  /// [Dork.directory]. If there are no subdirectories below [Dork.project] it
  /// will be identical to [Dork.project].
  ///
  /// There may be multiple [Dork]s running the same branch of the same project,
  /// as long as they located in different directories.
  String get instance => this._instance;

  /// The internal domain.
  ///
  /// The internal domain of this [Dork]. Used by the http proxy and to provide
  /// seamless ssh access. Consists of [Dork.project] and [Dork.instance].
  /// There may not be two running [Dork]s with the same [Dork.project] and
  /// [Dork.instance]. If a [Dork] is started, the current running instance will
  /// be stopped.
  String get domain => "${this.instance}.${this.project}.dork";

  /// The [Dork]s container name.
  ///
  /// Consists of [Dork.project], [Dork.branch] and [Dork.instance] to be unique
  /// for every combination of these.
  ///
  /// Available *after* [Dork.iniitalize].
  String get containerName {
    return "${this.project}.${this.instance}.${this.commit}";
  }

  String get imageName {
    return "${this.project}/${this.commit}";
  }

  /// Dirty status of the Dork.
  bool get dirty {
    return (this.container == null) || (this.container.hash == 'new') || (this.container.hash != this.commit);
  }

  /// The current commit this [Dork] has been updated to.
  ///
  /// If the current image tag and the current repository HEAD are not identical
  /// [null] is returned.
  ///
  /// Available *after* [Dork.iniitalize].
  String get commit {
    return this.repository.commit;
  }

  /// The [Dork] containers IP address.
  ///
  /// Throws an [StateError] if [Dork.state] is not [State.OUTDATED]
  /// or [State.CLEAN].
  ///
  /// Available *after* [Dork.iniitalize].
  String get address {
    return this.container.address;
  }

  bool matchContainer(Container c) => c.name == this.containerName;
  dynamic nullFallback() => null;

  /// Iniitalize this instance.
  ///
  /// Should be called directly after the constructor. Gather information about
  /// Docker container status and git repository. Most operations require these.
  /// Throws [RepositoryException] if the provided directory is not a git
  /// repository.
  Future initialize() async {

    this._container = null;
    this._repository = null;
    this._state = null;

    // Check if there is a repository and quit early if not.
    this._repository = await this.git.getRepository(this._dir);
    if (this._repository == null) return null;

    this._state = State.REPOSITORY;

    // Search for a container with the appropriate name.
    List<Container> containers = await this.docker.getContainers();
    containers.retainWhere((Container c) => c.project == this.project && c.instance == this.instance);

    if (containers.length > 0) {
      Map<String, String> hashes = {};
      containers.forEach((Container c) {
        hashes[c.name.split('.').last] = c.name.split('.').last;
      });

      this._container = containers.firstWhere((Container c) {
        return c.name == Container.naming(this.project, this.instance, this.commit);
      }, orElse: () => null);

      if (this._container == null) {
        String ancestor = await this.repository.closestAncestor(hashes);
        if (ancestor != null) {
          this._container = containers.firstWhere((Container c) {
            return c.name == Container.naming(this.project, this.instance, ancestor);
          }, orElse: () => null);
        }
      }

      if (this._container == null) {
        this._container = containers.firstWhere((Container c) {
          return c.name == Container.naming(this.project, this.instance, 'new');
        }, orElse: () =>  null);
      }
    }

    if (this._container == null) return this._state;

    this._state = State.CONTAINER;

    // If the container is not running, return now.
    if (!this._container.running) return this._state;

    // Set dirty or clean state.
    if (this.dirty) {
      this._state = State.DIRTY;
    }
    else {
      this._state = State.CLEAN;
    }
  }

  /// Create the Docker container.
  ///
  /// Ensures there is a git repository at [Dork.directory] and a container
  /// with name [Dork.container]. If there is none, Dork will search for the
  /// closes ancestor candidate based on git history to fork from. Else the
  /// dork/container will be used.
  Future create() async {
    if (this._container != null) return null;

    String image = this.env.baseImage;
    String name = Container.naming(this.project, this.instance, 'new');

    Map<String, String> container_hashes = {};
    List<Container> containers = await this.docker.getContainers();
    containers.where((Container c) => c.project == this.project).forEach((Container c) {
      container_hashes[c.name] = c.hash;
    });

    Map<String, String> image_hashes = {};
    List<Image> images = await this.docker.getImages();
    images.where((Image i) => i.project == this.project).forEach((Image i) {
      image_hashes[i.name] = i.hash;
    });

    String closest_container = await this.repository.closestAncestor(container_hashes);
    String closest_image = await this.repository.closestAncestor(image_hashes);

    if (closest_image != null) image = closest_image;

    if (closest_container != null) {
      bool new_commit = true;

      if (closest_image != null) {
        if (closest_container.split('.').last == 'new') {
          new_commit = false;
        }
        else {
          Map<String, int> dist = await this.repository.distances({
            'container': closest_container.split('.').last,
            'image': closest_image.split('/').last,
          });
          new_commit = dist['image'] < dist['container'];
        }
      }

      if (new_commit) {
        image = Image.naming(this.project, container_hashes[closest_container]);
        await this.docker.commit(containers.firstWhere((Container c) => c.name == closest_container).id, image);
      }
      else {
        image = closest_image;
      }
    }

    if (image != this.env.baseImage) {
      name = Container.naming(this.project, this.instance, image.split('/').last);
    }

    Map<String, String> volumes = {
      this._dir.absolute.path: this.env.dorkSourceDirectory,
      "${this.env.buildDirectory}/${this.project}/${this.instance}": this.env.dorkBuildDirectory,
    };

    await this.docker.create(name , image, volumes);

    await this.initialize();
  }

  /// Start the [Dork].
  ///
  /// Starts the container. If another [Dork] with the same [Dork.project]
  /// and [Dork.instance] combination is already running, it will be stopped.
  Future start() async {
    if (this.container.running) return null;

    // Search for other containers with same project/instance combination
    // and stop them.
    List<Container> containers = await this.docker.getContainers();
    containers.retainWhere((Container c) => (c.project == this.project) && (c.instance == this.instance));
    await Future.forEach(containers, (Container c) async {
      await this.docker.stop(c.id);
    });

    // Start the current container.
    await this.docker.start(this.container.id);
    await this.initialize();

    if (this.env.startupTimeout > 0) {
      DateTime start = new DateTime.now();
      while(!(await this.docker.isAccessible(this.container.id))) {
        print('failed!');
        if ((start.difference(new DateTime.now()).inSeconds) > this.env.startupTimeout) {
          throw new StateError('Could not connect to ${this.container.address}.');
        }
        await new Future.delayed(new Duration(milliseconds: 500));
      }
    }
    await (new Future.delayed(new Duration(seconds: 2)));
    await this.docker.updateHosts();
  }

  /// Stops the current [Dork].
  /// Expected result [State] is [State.STOPPED].
  Future stop() async {
    if (!this.container.running) return null;
    await this.docker.stop(this.container.id);
    await this.initialize();
    await this.docker.updateHosts();
  }

  /// Build or update the [Dork].
  ///
  /// Runs the ansible build for this [Dork]. The roles executed are determined
  /// by patterns in every roles `meta/main.yml` file. If there is a property
  /// `dork` and a sub-property `matches` it will be used to determine if the
  /// role applies to the project.
  /// It uses [Glob](https://pub.dartlang.org/packages/glob) and (optionally)
  /// regular expressions to search for given content.
  ///
  /// ### Example
  ///
  ///     dork:
  ///       matches:
  ///       - "**.php"
  ///       - "*.info.yml": "core:\ 8\.x"
  ///
  /// The first matcher  will trigger the role if there are any PHP files in
  /// the source directory. The second additionally checks for specific content
  /// using a regular expression.
  ///
  /// If the [include] parameter is provided, the listed will be passed to the
  /// ansible playbook. The same goes for the [exclude].
  ///
  /// If no tags are provided, [Dork.commit] will be used to generate a list of
  /// changed files between the last update and current HEAD. This list is
  /// matched against a list of patterns in every roles `meta/main.yml` to
  /// check if certain tasks need to be executed or not.
  ///
  /// ### Example
  ///
  ///     dork:
  ///       tags:
  ///       - "**.scss": [scss, cache]
  ///       - "**.features.php": [features, cache, tests]
  ///
  /// If [Dork.commit] is empty and no tags are provided, the full ansible
  /// playbook will be execute. If [Dork.commit] is equal to current HEAD, no
  /// updates are necessary and the playbook won't be executed.
  ///
  /// Expected result [State] is [State.CLEAN].
  Future update([bool force = false]) async {

    // Build the list of matching roles.
    List<String> roles = await this.ansible.matchingRoles();

    // Build the list of tags based on git diff.
    List<String> changed = await this.repository.changedFiles(this.container.name.split('.').last, this.repository.commit);

    // Get the tags we need to process.
    // Initially empty, only set tags if container is not running on base image
    // in this case, the whole provisioning has to run.
    List<String> tags = [];
    if (this.container.hash != null) {
      tags = await this.ansible.matchingTags(changed);
    }

    // Abort early if nothing changed at all (unlikely).
    if (tags.length > 0 || this.container.name.split('.').last == 'new' || force) {
      // Build the inventory as string.
      String inventory = "${this.address} ansible_ssh_user=${this.env.dorkUser} dork_user=${this.env.dorkUser}";
      // Build the playbook as string.
      String playbook = '- hosts: all\n  roles:\n';
      roles.forEach((String role) => playbook += "  - ${role}\n");
      await this.ansible.play(playbook, inventory, tags);
    }


    if (this.container.hash != this.repository.commit) {
      await this.docker.rename(this.container.id, this.containerName);
      await this.docker.stop(this.container.id);
      await this.docker.start(this.container.id);
      if (this.container.hash == null) {
        await this.docker.commit(this.container.id, this.imageName);
      }
    }
    await this.initialize();

    // Search for merged branches.
    List<String> commits = [];
    List<Container> containers = await this.docker.getContainers();
    containers.retainWhere((Container c) => c.project == this.project);


    // Setup the dependency matrix
    Map<String, List<String>> ancestorOf = {};
    Map<String, List<String>> descendantOf = {};
    containers.forEach((Container c) {
      if (c.hash == null) return;
      ancestorOf[c.hash] = [];
      descendantOf[c.hash] = [];
    });

    // Fill the matrix.
    await Future.forEach(containers, (Container a) async {
      if (a.hash == null) return;
      Repository repo = await this.git.getRepository(new Directory(a.workDirectory));

      await Future.forEach(containers, (Container b) async {
        if (b.hash == null || b.hash == a.hash) return;
        if (await repo.isAncestor(a.hash, b.hash)) {
          ancestorOf[a.hash].add(b.hash);
          descendantOf[b.hash].add(a.hash);
        }
      });
    });

    // Remove all containers except the once that are not ancestors of anything.
    // We only keep the tips of the tree.
    await Future.forEach(containers, (Container c) async {
      if (ancestorOf[c.hash].length == 0) return;

      String dir = c.workDirectory.replaceAll(this.env.sourceDirectory + '/', '');
      if (dir.split('/').length == 1) {
        // Workstation mode, remove the container, leave source directory.
        await this.docker.remove(c.id);
      }
      else {
        String branch = (await this.git.getRepository(new Directory(c.workDirectory))).branch;
        String subdir = dir.replaceAll(this.project + '/', '');
        if (subdir == branch) {
          // Server mode, remove container and source directory.
          await this.docker.stop(c.id);
          await this.docker.remove(c.id);
          await this.fs.remove(c.workDirectory);
        }
        // Manual mode - don't remove anything
      }
    });

    await this.docker.updateHosts();
  }

  Future freeze() {
    if (this.state != State.CLEAN) {
      throw new StateError('Only running and clean containers can be commited.');
    }
    return this.docker.commit(this.container.id, "${this.project}/${this.repository.commit}");
  }

  /// Removes this [Dork].
  ///
  /// Deletes the Docker container and removes associated data from internal
  /// storage. *Does not remove the repository!*
  Future remove() async {
    List<Container> containers = await this.docker.getContainers();
    containers.retainWhere((Container c) => c.project == this.project && c.instance == this.instance);
    await Future.forEach(containers, (Container c) async => await this.docker.remove(c.id));

    if (this.mode == Mode.WORKSTATION) {
      List<Image> images = await this.docker.getImages();
      images.retainWhere((Image i) => i.project == this.project);
      await Future.forEach(images, (Image i) async => await this.docker.removeImage(i.id));
    }

    List<String> dangling = await this.docker.getDanglingImages();
    if (dangling != null) {
      await Future.forEach(await this.docker.getDanglingImages(), (String id) async => await this.docker.removeImage(id));
    }
    await this.initialize();
    await this.docker.updateHosts();
  }
}