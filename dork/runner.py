import subprocess
import os
import tempfile
import json
from git import Repository
from config import config


def apply_roles(roles, ip, repository, extra_vars=None, tags=None, skip=None):
    """
    :type roles: list[str]
    :type ip: str
    :type repository: Repository
    :type extra_vars: dict
    :type tags: list[str]
    :type skip: list[str]
    :rtype: int
    """
    # TODO: inject repo path and add .dork directory
    # Create the temporary inventory
    inventory = tempfile.NamedTemporaryFile(delete=False)
    inventory.write("%s ansible_ssh_user=root" % ip + '\n')
    inventory.close()

    # Create the temporary playbook
    playbook = tempfile.NamedTemporaryFile(delete=False)
    pblines = ['- hosts: all', '  roles:']
    for role in roles:
        pblines.append('  - { role: %s, tags:[\'%s\'] }' % (role, role))
    playbook.write('\n'.join(pblines) + '\n')
    playbook.close()

    result = run_playbook(inventory.name, playbook.name, repository, extra_vars, tags, skip)

    # Unlink temporary files
    os.unlink(inventory.name)
    os.unlink(playbook.name)
    return result


def run_playbook(inventory, playbook, repository, extra_vars=None, tags=None, skip=None):
    """
    :type inventory: str
    :type playbook: str
    :type repository: Repository
    :type extra_vars: dict
    :type tags: list[str]
    :type skip: list[str]
    :return:
    """

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
        command.append(','.join([ t for t in tags if t != 'default' ]))

    # Add --skip-tags flag if available.
    if skip:
        command.append('--skip-tags')
        command.append(','.join([s for s in skip if s != 'default' ]))

    # Run ansible
    ansible_library = config.ansible_roles_path
    project_library = repository.directory + '/.dork'
    if os.path.isdir(project_library):
        ansible_library.append(project_library)

    environment = os.environ.copy()
    environment['ANSIBLE_ROLES_PATH'] = ':'.join(ansible_library)
    result = subprocess.call(' '.join(command), shell=True, env=environment)
    os.unlink(variables.name)
    return result
