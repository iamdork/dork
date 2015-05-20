"""
Dynamic host file management.
"""
import docker
from subprocess import call
import re


def refresh():
    """
    Ensure that all running containers have a valid entry in /etc/hosts.
    """
    containers = docker.containers()
    hosts = '\n'.join(['%s %s.%s.dork %s' % (c.address, c.project, c.instance, c.domain) for c in [d for d in containers if d.running]])
    hosts = '# DORK START\n%s\n# DORK END' % hosts

    expr = re.compile('# DORK START\n(.*\n)*# DORK END')
    with open('/etc/hosts', 'r') as f:
        content = f.read()

    if len(expr.findall(content)) > 0:
        content = expr.sub(hosts, content)
    else:
        content += hosts + '\n'

    with open('/etc/hosts', 'w') as f:
        f.write(content)
    call(['sudo', 'service', 'dnsmasq', 'restart'])

