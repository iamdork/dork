import subprocess
import tempfile
import json


class Runner:
    def __init__(self):
        pass

    def apply_roles(self, roles, ip, vars=None, tags=None):
        # Create the temporary inventory
        inventory = tempfile.NamedTemporaryFile()
        inventory.write(ip)

        # Create the temporary playbook
        playbook = tempfile.NamedTemporaryFile()
        pblines = ['- hosts: all']
        pblines += '  roles:'
        for role in roles:
            pblines += '  - %s' % role
        playbook.write('\n'.join(pblines))

        command = ['ansible-playbook', '-i', inventory.name, playbook.name]

        # Process extra variables if provided
        variables = tempfile.NamedTemporaryFile()

        if (vars):
            json.dump(vars, variables)
            command.append('--extra-vars')
            command.append("@%s" % variables.name)

        # Process tags variables if provided
        if tags:
            command.append('--tags')
            command.append(','.join(tags))

        # Run ansible
        result = subprocess.call(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE)

        # Unlink temporary files
        inventory.unlink()
        playbook.unlink()
        variables.unlink()
        return result

