library dork.docker;

import "dart:async";
import "dart:io";
import "dart:convert";
import "package:dork/services/service.dart";
import "package:dork/services/environment.dart";
import "package:http/http.dart" as http;

/// Simple struct representing a Docker container.
class Container {
  String id;
  String image;
  String name;
  String address;
  String workDirectory;
  String buildDirectory;

  bool get running => address != null;
  operator == (Container item) {
    if (item.id != null && item.id != this.id) return false;
    if (item.image != null && item.image != this.image) return false;
    if (item.name != null && item.name != this.name) return false;
    if (item.address != null && item.address != this.address) return false;
    if (item.workDirectory != null && item.workDirectory != this.workDirectory) return false;
    if (item.buildDirectory != null && item.buildDirectory != this.buildDirectory) return false;
    return true;
  }

  String get hash {
    String hash = this.name.split('.').last;
    if (hash == 'new') hash = null;
    return hash;
  }

  String get project => this.name.split('.').first;

  String get instance => this.name.split('.').elementAt(1);

  static String naming(String project, String instance, String hash) => "${project}.${instance}.${hash}";

  String toString() {
    return JSON.encode({
      'id': this.id,
      'image': this.image,
      'name': this.name,
      'address': this.address,
      'workDirectory': this.workDirectory,
      'buildDirectory': this.buildDirectory,
    });
  }
}

/// Simple struct representing a Docker image.
class Image {
  String id;
  String name;
  operator == (Image item) {
    if (item.id != null && item.id != this.id) return false;
    if (item.name != null && item.name != this.name) return false;
    return true;
  }

  String get project => this.name.split('/').first;
  String get hash => this.name.split('/').last;
  static String naming(String project, String hash) => "${project}/${hash}";

  String toString() {
    return JSON.encode({
      'id': this.id,
      'name': this.name
    });
  }
}

class RawDocker extends Service {

  final Environment env;

  RawDocker(this.env);

  Future writeHosts(Map<String, String> hosts) {
    List<String> file = [];
    bool dork_hosts = false;
    bool writter = false;
    File hostsfile = new File('/etc/hosts');
    hostsfile.readAsLinesSync().forEach((String line){
      if (line == "# DORK START") dork_hosts = true;
      if (!dork_hosts) file.add(line);
      if (line == "# DORK END") dork_hosts == false;
    });
    if (hosts.length > 0) {
      file.add('# DORK START');
      hosts.forEach((String ip, String domain) {
        file.add("${ip} ${domain}");
      });
      file.add('# DORK END');
    }
    hostsfile.writeAsString(file.join('\n'));
    this.run('sudo', ['service', 'dnsmasq', 'restart']);
  }

  Future<dynamic> _apiGet(String url, [ List<int> accepted = Service.default_accepted ]) async {
    return JSON.decode(await this.get(this.env.dockerAddress + '/' + url, accepted));
  }

  Future<dynamic> _apiPost(String url, [ Map params = Service.default_params, List<int> accepted = Service.default_accepted ]) async {
    String req = this.env.dockerAddress + url;
    String result = await this.post(req, params, accepted);
    try {
      return JSON.decode(result);
    } catch (exception) {
      return null;
    }
  }

  Future<dynamic> _apiDelete(String url, [ List<int> accepted = Service.default_accepted ]) async {
    String req = this.env.dockerAddress + url;
    String result = await this.delete(req, accepted);
    try {
      return JSON.decode(result);
    } catch (exception) {
      return null;
    }
  }

  Future<List<Container>> getContainers() async {
    List<Container> containers = [];
    await Future.forEach(await this._apiGet('/containers/json?all=1'), (Map data) async {
      Map c = await this._apiGet("/containers/${data['Id']}/json");
      String id = c['Id'];
      String name = c['Name'];
      if (name.substring(0, 1) == '/') {
        name = name.substring(1);
      }
      String image = c['Image'];
      String address = c['NetworkSettings']['IPAddress'];
      bool running = c['State']['Running'];
      String workdir = null;
      String builddir = null;
      c['HostConfig']['Binds'].forEach((String bind) {
        try {
          String host = bind.split(':').first;
          String container = bind.split(':').last;
          if (container == this.env.dorkBuildDirectory) {
            builddir = host;
          }
          if (container == this.env.dorkSourceDirectory) {
            workdir = host;
          }
        } catch (exception) {}
      });
      if (workdir != null && builddir != null) {
        containers.add(new Container()
          ..id = id
          ..name = name
          ..image = image
          ..address = running ? address : null
          ..workDirectory = workdir
          ..buildDirectory = builddir
        );
      }
    });
    return containers;
  }

  Future<List<Image>> getImages() async {
    List<Image> images = [];
    (await this._apiGet('/images/json')).forEach((Map i) {
      if (!i.containsKey('RepoTags') || i['RepoTags'].length == 0 ) {
        return;
      }
      String name = i['RepoTags'][0].split(':').first;
      String id = i['Id'];
      images.add(new Image()
        ..id = id
        ..name = name
      );
    });
    return images;
  }

  Future<List<String>> getDanglingImages() async {
    return this.run('docker', ['images', '-q', '-f', 'dangling=true']);
  }

  Future create(String name, String image, Map<String, String> volumes) async {
    Map conf = {
      'Image': image,
      'Volumes': {},
      'HostConfig': {
        'Binds': []
      },
    };
    volumes.forEach((String host, String container) {
      conf['Volumes'][container] = {};
      conf['HostConfig']['Binds'].add("${host}:${container}");
    });
    String url = '/containers/create?name=' + name;
    await this._apiPost(url , conf, [201]);
  }

  Future start(String container) async {
    await this._apiPost('/containers/${container}/start', null, [204, 304]);
  }

  Future stop(String container) async {
    await this._apiPost('/containers/${container}/stop', null, [204, 304]);
  }

  Future remove(String container) async {
    await this._apiDelete('/containers/${container}', [204]);
  }

  Future removeImage(String image) async {
    await this._apiDelete('/images/${image}', [200]);
  }

  Future rename(String container, String name) async {
    await this._apiPost('/containers/${container}/rename?name=${name}', null, [204]);
  }

  Future commit(String container, String repository) async {
    await this._apiPost('/commit?container=${container}&repo=${repository}', {}, [201]);
  }

  Future<bool> isAccessible(String container) async {
    Map params = {
      "AttachStdin": false,
      "AttachStdout": true,
      "AttachStderr": true,
      "Tty": false,
      "Cmd": [ "ps -A | grep sshd" ],
    };
    Map exec = await this._apiPost('/containers/${container}/exec', params, [201]);
    String result = await this.post(this.env.dockerAddress + '/exec/${exec['Id']}/start', { 'Detach': false, "Tty": false }, [200]);
    return result.contains('sshd');
  }
}

abstract class Docker implements RawDocker {
  Future<Container> containerById(String id) async {
    Container c = (await this.getContainers()).firstWhere((Container c) => c.id == id, orElse: () => null);
    if (c == null) throw new StateError('Container with id ${id} doesn\'t exist.');
    return c;
  }

  Future<Container> containerByName(String name) async {
    Container c = (await this.getContainers()).firstWhere((Container c) => c.name == name, orElse: () => null);
    if (c == null) throw new StateError('Container with name ${name} doesn\'t exist.');
    return c;
  }

  Future<Image> imageById(String id) async {
    Image i = (await this.getImages()).firstWhere((Image i) => i.id == id, orElse: () => null);
    if (i == null) throw new StateError('Image with id ${id} doesn\'t exist.');
    return i;
  }

  Future<Image> imageByName(String name) async {
    Image i = (await this.getImages()).firstWhere((Image i) => i.name == name, orElse: () => null);
    if (i == null) throw new StateError('Image with name ${name} doesn\'t exist.');
    return i;
  }

  Future updateHosts() async{
    Map<String, String> hosts = {};
    (await this.getContainers()).forEach((Container c) {
      String project = c.name.split('.').elementAt(0);
      String instance = c.name.split('.').elementAt(1);
      hosts[c.address] = "${project}.${instance}.dork";
      if (instance == project) {
        hosts[c.address] += " ${project}.dork";
      }
    });
    this.writeHosts(hosts);
  }
}