library dork.cli;
import "dart:io";
import "dart:async";
import "package:args/args.dart";
import "package:di/di.dart";

import "package:dork/dork.dart";

import "package:dork/services/environment.dart";
import "package:dork/services/git.dart";
import "package:dork/services/docker.dart";
import "package:dork/services/ansible.dart";
import "package:dork/services/filesystem.dart";

class CliGit extends RawGit with Git {}

class CliDocker extends RawDocker with Docker {
  CliDocker(Environment env) : super(env);
}

class CliAnsible extends RawAnsible with Ansible {
  FileSystem fs;
  CliAnsible(Environment env, this.fs) : super(env);
}

class CliFileSystem extends RawFileSystem with FileSystem {
  CliFileSystem(Environment env) : super(env);
}

class Cli {
  ModuleInjector _injector;
  Cli([Directory dir = null]) {
    if (dir == null) dir = Directory.current;
    this._injector = new ModuleInjector([new Module()
      ..bind(Directory, toFactory: () => dir)
      ..bind(Environment)
      ..bind(Git, toImplementation: CliGit)
      ..bind(Docker, toImplementation: CliDocker)
      ..bind(Ansible, toImplementation: CliAnsible)
      ..bind(FileSystem, toImplementation: CliFileSystem)
      ..bind(Dork)
    ]);
  }

  Future start() async {
    Dork dork = this._injector.get(Dork) as Dork;
    await dork.initialize();
    if (dork.state != State.REPOSITORY) {
      dork.start();
    }
  }

  Future run(List<String> arguments) async {
    ArgParser parser = new ArgParser();
    parser.addCommand('start');
    parser.addCommand('status');
    parser.addCommand('update');
    parser.addCommand('provision');
    parser.addCommand('stop');
    parser.addCommand('remove');
    parser.addCommand('boot');
    ArgResults results = parser.parse(arguments);

    if (arguments.length == 0) {
      print('Please choose a command:\n dork [start|stop|status|update|provision|remove|boot]');
      return null;
    }

    if (results.command == null) {
      print('Unknown command ${arguments[0]}.');
      return null;
    }

    if (results.command.name == 'boot') {
      FileSystem fs = this._injector.get(FileSystem);
      Environment env = this._injector.get(Environment);
      List<String> paths = await fs.glob('**/.git', env.sourceDirectory);
      List<String> dirs = [];
      RegExp reg = new RegExp('\/\.git\$');

      for (String path in paths) {
        dirs.add(path.replaceAll(reg, ''));
      }

      for (String dir in dirs) {
        // skip git sub-directories
        if (dirs.any((String d) => d != dir && dir.startsWith(d))) continue;
        Cli runner = new Cli(new Directory(dir));
        runner.start();
      }
      return null;
    }

    Dork dork = this._injector.get(Dork) as Dork;
    await dork.initialize();

    if (results.command.name == 'start') {
      await dork.create();
      await dork.start();
    }

    if (results.command.name == 'status') {
      print(dork.state);
      print(dork.mode);
      if (dork.state != State.REPOSITORY && dork.state != null) {
        print(dork.address);
      }
      print(dork.repository.commit);
      print(dork.repository.branch);
    }

    if (results.command.name == 'update') {
      await dork.create();
      await dork.start();
      await dork.update();
    }

    if (results.command.name == 'provision') {
      await dork.create();
      await dork.start();
      await dork.update(true);
      await dork.stop();
      await dork.start();
    }
    if (results.command.name == 'stop') {
      await dork.stop();
    }
    if (results.command.name == 'remove') {
      await dork.stop();
      await dork.remove();
    }
  }
}