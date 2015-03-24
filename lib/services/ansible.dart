library dork.ansible;

import "dart:async";
import "dart:io";
import "dart:convert";
import "package:dork/services/service.dart";
import "package:dork/services/environment.dart";
import "package:dork/services/filesystem.dart";
import "package:yaml/yaml.dart";
import "package:glob/glob.dart";

class RawAnsible extends Service {

  final Environment env;

  RawAnsible(this.env);

  Future<Map<String, Map>> getRoles() async {
    Map<String, Map> roles = {};
    await Future.forEach(this.env.ansibleRolesDirectory, (d) async {
      Directory dir = new Directory(d);
      await Future.forEach(dir.listSync(), (FileSystemEntity child) async {
        String name = child.path.split('/').last;
        if (name.startsWith('.')) return;
        File yamlfile = new File("${dir.path}/${name}/meta/main.yml");
        if (!(await yamlfile.exists())) return;
        String fc = yamlfile.readAsStringSync();
        dynamic yaml = loadYaml(fc);
        dynamic content = JSON.decode(JSON.encode(yaml));
        if (content != null) {
          roles[name] = {'includes': []};
          if (content.containsKey('dork')) {
            roles[name] = content['dork'];
            roles[name]['includes'] = [];
          }
          if (content.containsKey('dependencies')) {
            content['dependencies'].forEach((dep) {
              if (dep is String) roles[name]['includes'].add(dep);
              if (dep is Map) roles[name]['includes'].add(dep['role']);
            });
          }
        }
      });
    });
    return roles;
  }

  Future play(String playbook, String inventory, List<String> tags) async {
    File tempPlaybook = new File('.tempPlaybook');
    File tempInventory = new File('.tempInventory');
    await tempPlaybook.writeAsString(playbook);
    await tempInventory.writeAsString(inventory);
    List<String> args = ['-s', '-i', '.tempInventory', '.tempPlaybook'];
    if (tags != null && tags.length > 0) {
      args..add('--tags')..add(tags.join(','));
    }
    List<String> output = await this.run('ansible-playbook', args);
    await tempPlaybook.delete();
    await tempInventory.delete();
    // TODO: pass somewhere else
    print(output.join('\n'));
  }
}

abstract class Ansible implements RawAnsible {
  FileSystem fs;
  Future<List<String>> matchingRoles() async {
    List<String> roles = [];
    Map<String, Map> available = await this.getRoles();
    await Future.forEach(available.keys, (String key) async {
      Map role = available[key];
      if (!role.containsKey('matches')) return;
      Map matches = {};
      if (role['matches'] is Map) {
        matches = role['matches'];
      }
      else if (role['matches'] is String) {
        matches = {
          role['matches']: null,
        };
      }
      else if (role['matches'] is List) {
        role['matches'].forEach((String p) => matches[p] = null);
      }

      bool match = matches.length > 0;

      await Future.forEach(matches.keys, (String pattern) async {
        List<String> matched = await this.fs.glob(pattern);
        String match_content = matches[pattern];
        match = match && (matched.length > 0);
        await Future.forEach(matched, (String file) async {
          if (match_content != null) {
            match = match && (new RegExp(match_content)).hasMatch(await this.fs.file(file));
          }
        });
      });
      if (match == true) {
        roles.add(key);
      }
    });

    List<String> remove = [];
    recurseExcludes(String key) {
      if (!available.containsKey(key)) {
        return;
      }
      available[key]['includes'].forEach((includes) {
        remove.add(includes);
        recurseExcludes(includes);
      });
    }

    roles.forEach((String role) {
      recurseExcludes(role);
    });

    roles.removeWhere((role) => remove.contains(role));
    return roles;
  }

  Future<List<String>> matchingTags(List<String> files) async {
    List<String> result = [];
    Map<String, Map> available = await this.getRoles();
    List<String> matching = await this.matchingRoles();
    // TODO: search for tags in depending roles
    List<String> active = [];
    recurseRoles(String key) {
      active.add(key);
      if (available.containsKey(key) && available[key].containsKey('includes')) {
        available[key]['includes'].forEach((String sub) {
          recurseRoles(sub);
        });
      }
    }

    matching.forEach((String key) => recurseRoles(key));

    active.forEach((String key) {
      Map role = available[key];
      if (!role.containsKey('tags')) return;
      role['tags'].forEach((Map<String, List<String>> t) {
        t.forEach((String pattern, List<String> tags) {
          Glob glob = new Glob(pattern);
          if (files.where((f) => glob.matches(f)).length > 0) {
            result.addAll(tags.where((t) => !result.contains(t)));
          }
        });
      });
    });
    return result;
  }
}
