library dork.test.testrunner;
import "dart:mirrors";
import "dart:async";

import "package:unittest/unittest.dart";

class Test {
  final String label;
  const Test(this.label);
}

class TestRunner {
  Future run() async {
    ClassMirror mirror = reflectClass(this.runtimeType);
    InstanceMirror instance = reflect(this);
    String grouplabel = mirror.simpleName.toString();

    mirror.metadata.forEach((InstanceMirror el) {
      if (el.reflectee is Test) grouplabel = (el.reflectee as Test).label;
    });

    group(grouplabel, () {
      setUp(() async {
        await this.setup();
      });
      tearDown(() async {
        await this.teardown();
      });
      mirror.instanceMembers.forEach((Symbol key, MethodMirror method) {
        String label = null;

        method.metadata.forEach((InstanceMirror el) {
          if (el.reflectee is Test) label = (el.reflectee as Test).label;
        });

        if (label != null) {
          test(label, () async => await instance.invoke(method.simpleName, []).reflectee);
        }
      });
    });
  }

  Future setup() async {}

  Future teardown() async {}

  static runAll() {
    MirrorSystem ms = currentMirrorSystem();
    ms.libraries.forEach((Uri key, LibraryMirror lib) {
      lib.declarations.forEach((Symbol key, DeclarationMirror dec){
        if (dec is ClassMirror && dec.metadata.where((InstanceMirror md) => md.reflectee is Test).length > 0) {
          InstanceMirror instance = (dec as ClassMirror).newInstance(new Symbol(''), []);
          instance.invoke(new Symbol('run'), []);
        }
      });
    });
  }
}
