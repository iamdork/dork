from mock import patch
import unittest
from dork.config import config
from io import BytesIO


class TestDefaultValues(unittest.TestCase):

    def setUp(self):
        self.__config = config(clear=True)

    def test_host_source_directory(self):
        self.assertEqual(self.__config.host_source_directory, '/var/source')

    def test_ansible_roles_path(self):
        self.assertEqual(self.__config.ansible_roles_path, [
            '/etc/ansible/roles', '/opt/roles'])

    def test_project_variables(self):
        self.assertEqual(self.__config.variables('test'), {})

simple_config_files = dict()

simple_config_files['~/.dork.ini'] = """
[dork]
host_source_directory: /var/overridden

[test]
variable: test
"""


def simple_config_file(name):
    if name not in simple_config_files:
        raise IOError
    else:
        return BytesIO(simple_config_files[name])


class TestSimpleConfig(unittest.TestCase):

    @patch('__builtin__.open', side_effect=simple_config_file)
    def setUp(self, *args):
        self.__config = config(clear=True)

    def test_overridden(self):
        self.assertEqual('/var/overridden', self.__config.host_source_directory)

    def test_not_overridden(self):
        self.assertEqual('/var/build', self.__config.host_build_directory)

    def test_project_variable(self):
        self.assertEqual({'variable': 'test'}, self.__config.variables('test'))

multi_config_files = dict()

multi_config_files['/vagrant/dork.ini'] = """
[dork]
host_source_directory: /custom/source
host_build_directory: /custom/build

[test]
variable_one: a
variable_two: b
"""

multi_config_files['~/.dork.ini'] = """
[dork]
host_build_directory: /custom/build/subdir

[test]
variable_two: c
"""


def multi_config_file(name):
    if name not in multi_config_files:
        raise IOError
    else:
        return BytesIO(multi_config_files[name])


class TestMultiConfig(unittest.TestCase):
    @patch('__builtin__.open', side_effect=multi_config_file)
    def setUp(self, *args):
        self.__config = config(clear=True)

    def test_single_override(self):
        self.assertEqual('/custom/source', self.__config.host_source_directory)

    def test_double_override(self):
        self.assertEqual('/custom/build/subdir', self.__config.host_build_directory)

    def test_variable_override(self):
        self.assertEqual({'variable_one': 'a', 'variable_two': 'c'}, self.__config.variables('test'))
