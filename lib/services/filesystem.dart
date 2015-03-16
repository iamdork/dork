library dork.filesystem;
import "dart:async";
import "dart:io";
import "package:glob/glob.dart";
import "package:dork/services/service.dart";
import "package:dork/services/environment.dart";

class RawFileSystem extends Service {
  final Environment env;

  RawFileSystem(this.env);

  Future<List<String>> glob(String pattern, [String dir = null]) async {
    if (dir == null) dir = this.env.currentDirectory;
    if (pattern.contains('*')) {
      try {
        Glob glob = new Glob(pattern);
        List<String> files = [];
        for (FileSystemEntity en in glob.listSync(root: dir)) {
          files.add(en.path);
        }
        return files;
      } catch (exc) {
        return [];
      }
    } else {
      if (await (new File(dir + '/' + pattern)).exists()) {
        return [pattern];
      }
      else {
        return [];
      }
    }
  }

  Future<String> file(String path) async {
    File file = new File(path);
    return file.readAsString();
  }

  Future remove(String path) async {
    // check if file or directory, remove both
    Directory dir = new Directory(path);
    await dir.delete(recursive: true);
  }
}

abstract class FileSystem implements RawFileSystem {

}