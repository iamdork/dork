library dork.git;

import "dart:io";
import "dart:async";
import "package:dork/services/service.dart";

/// Simple struct representing a git repository.
class Repository {
  final String branch;
  final String commit;
  final Directory dir;
  final Git git;
  Repository(this.branch, this.commit, this.dir, this.git);
  Future<bool> isAncestor(String a, String b) => git._isAncestor(this.dir, a, b);
  Future<List<String>> mergedCommits(String a, String b) => git._mergedCommits(this.dir, a, b);
  Future<List<String>> changedFiles(String a, String b) => git._changedFiles(this.dir, a, b);
  Future<Map<String, int>> distances(Map<String, String> hashes) => git._distances(this.dir, hashes);
  Future<String> closestAncestor(Map<String, String> hashes) => git._closestAncestor(this.dir, hashes);
}

/// Simple shell-based implementation of the [Git] interface.
class RawGit extends Service {

  Future<Repository> getRepository(Directory dir) async {
    String commit = (await this.run('git', ['--no-pager', 'log', '-1', '--format=%H'], dir.path)).first;
    String branch = (await this.run('git', ['rev-parse', '--abbrev-ref', 'HEAD'], dir.path)).first;
    return new Repository(branch, commit, dir, this);
  }

  Future<bool> _isAncestor(Directory dir, String a, String b) async {
    try {
      await this.run('git', ['merge-base', '--is-ancestor', a, b], dir.path);
    } catch (exc) {
      return false;
    }
    return true;
  }

  Future<List<String>> _mergedCommits(Directory dir, String a, String b) async {
    if (a == 'new' || b == 'new') return [];
    return this.run('git', ['--no-pager', 'log', '--format="%H"', '${a}...${b}'], dir.path);
  }

  Future<List<String>> _changedFiles(Directory dir, String from, String to) async {
    if (from == 'new' || to == 'new') return [];
    return this.run('git', ['diff', '--name-only', from, to], dir.path);
  }
}

abstract class Git implements RawGit {
  Future<Map<String, int>> _distances(Directory dir, Map<String, String> hashes) async {
    String commit = (await this.getRepository(dir)).commit;
    Map<String, int> distances = {};
    await Future.forEach(hashes.keys, (String key) async {
      if (hashes[key] == commit || await this._isAncestor(dir, hashes[key], commit)) {
        List<String> merged = await this._mergedCommits(dir, hashes[key], commit);
        distances[key] = merged.length;
      }
    });
    return distances;
  }

  Future<String> _closestAncestor(Directory dir, Map<String, String> hashes) async {
    Map<String, int> distances = await this._distances(dir, hashes);
    List<String> ancestors = new List<String>.from(distances.keys);
    if (ancestors.length > 0) {
      ancestors.sort((String a, String b) => distances[a] - distances[b]);
      return ancestors.first;
    }
    else {
      return null;
    }
  }
}
