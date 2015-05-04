import subprocess
import os
import tempfile
import json


def apply_roles(roles, ip, extra_vars=None, tags=None, skip=None):
    # Create the temporary inventory
    inventory = tempfile.NamedTemporaryFile(delete=False)
    inventory.write(ip + '\n')
    inventory.close()

    # Create the temporary playbook
    playbook = tempfile.NamedTemporaryFile(delete=False)
    pblines = ['- hosts: all', '  roles:']
    for role in roles:
        pblines.append('  - %s' % role)
    playbook.write('\n'.join(pblines) + '\n')
    playbook.close()

    result = run_playbook(inventory.name, playbook.name, extra_vars, tags, skip)

    # Unlink temporary files
    os.unlink(inventory.name)
    os.unlink(playbook.name)
    return result


def run_playbook(inventory, playbook, extra_vars=None, tags=None, skip=None):

    command = ['ansible-playbook', '-i', inventory, playbook]

    # Process extra variables if provided
    variables = tempfile.NamedTemporaryFile(delete=False)

    if extra_vars:
        json.dump(extra_vars, variables)
        variables.close()
        command.append('--extra-vars')
        command.append("@%s" % variables.name)

    # Add --tags flag if available.
    if tags:
        command.append('--tags')
        command.append(','.join(tags))

    # Add --skip-tags flag if available.
    if skip:
        command.append('--skip-tags')
        command.append(','.join(skip))

    # Run ansible
    result = subprocess.call(command)
    os.unlink(variables.name)
    return result
