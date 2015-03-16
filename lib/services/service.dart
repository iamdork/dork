library dork.service;
import "dart:async";
import "dart:io";
import "dart:convert";

import "package:http/http.dart" as http;

class HttpException implements Exception {
  final int error;
  final String message;
  HttpException(this.error, this.message);
  String toString() => "HTTP Error: ${this.error}\n${this.message}";
}

class ShellException implements Exception {
  int status;
  final String message;
  ShellException(this.status, this.message);
  String toString() => "Exit status: ${this.status}\n${this.message}";
}

class Service {
  static const default_params = const {};
  static const default_accepted = const [200];

  Future<String> get(String url, [ List<int> accepted = Service.default_accepted ]) async {
    http.Response response = await http.get(url);
    if (accepted.contains(response.statusCode)) return response.body;
    throw new HttpException(response.statusCode, response.body);
  }

  Future<String> post(String url, [ Map body = Service.default_params, List<int> accepted = Service.default_accepted ]) async {
    http.Response response = await http.post(url, headers: {'Content-Type': 'application/json'}, body: JSON.encode(body));
    if (accepted.contains(response.statusCode)) return response.body;
    throw new HttpException(response.statusCode, response.body);
  }

  Future<String> delete(String url, [ List<int> accepted = Service.default_accepted ]) async {
    http.Response response = await http.delete(url);
    if (accepted.contains(response.statusCode)) return response.body;
    throw new HttpException(response.statusCode, response.body);
  }

  Future<List<String>> run(String executable, List<String> arguments, [ String workingDirectory = '.' ]) async {
    ProcessResult result = await Process.run(executable, arguments, workingDirectory: workingDirectory, runInShell: true);
    if (result.exitCode != 0) {
      throw new ShellException(result.exitCode, result.stdout + '\n' + result.stderr);
    }
    return (new LineSplitter()).convert(result.stdout);
  }
}