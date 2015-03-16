library dork.environment;

import "dart:io";

/// Environmental information interfaces.
///
/// Gives access to environmental/configuration information. Directories, global
/// settings and similiar.
class Environment {
  Directory _current_directory;
  Environment(this._current_directory);

  String _env(String key, String fallback) {
    if (Platform.environment.containsKey(key)) return Platform.environment[key];
    return fallback;
  }

  /// The the current execution directory.
  String get currentDirectory => this._current_directory.absolute.path;

  /// The root source directory.
  /// All [Dork] project sources are stored here, and this path will be used
  /// to generate [Dork.project] and [Dork.instance].
  String get sourceDirectory => this._env('SOURCE', '/var/source');

  /// The root build directory.
  ///
  /// Build results generated/update by [Dork.update]
  String get buildDirectory => this._env('BUILDS', '/var/build');

  /// The directory containing all ansible roles to be checked for project
  /// compatibility.
  List<String> get ansibleRolesDirectory {
    return this._env('ROLES', '/opt/dork/ansible/roles:/opt/roles').split(':');
  }

  /// The directory inside a dork where sources are mounted.
  String get dorkSourceDirectory => this._env('CONTAINER_SOURCE', '/var/source');

  /// The build directory inside a dork.
  String get dorkBuildDirectory => this._env('CONTAINER_BUILD', '/var/build');

  /// The base image to be used if no appropriate ancestor is found.
  String get baseImage => this._env('BASE_IMAGE', 'dork/container');

  /// The number of seconds Dork tries to verify the ssh connection to a
  /// newly started container.
  int get startupTimeout => int.parse(this._env('SSH_TIMEOUT', '10'));

  /// The HTTP address to reach the docker api.
  String get dockerAddress => this._env('DOCKER', 'http://127.0.0.1:2375');

  /// The user account to connect to a dork.
  String get dorkUser => 'dork';
}
