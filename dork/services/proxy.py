from ..docker import containers, events
import quickproxy
from urlparse import urlparse
from ..config import config

registry = {}
address = urlparse(config.docker_address).hostname


def refresh():
    global registry
    registry = {}
    for container in containers(True):
        if container.running:
            registry[container.domain] = container.hostPort(80)


def resolve(req):
    if req.host in registry:
        req.headers['X-DORK-HOST'] = "%s:%s" % (req.host, registry[req.host])
        req.host = address
        req.port = registry[req.host]
    return req


def server(config):
    refresh()
    proxy = quickproxy.run_proxy(8080, req_callback=resolve)
    events().filter(lambda e: 'container' in e).filter(lambda e: e['event'] in ['start', 'stop']).subscribe(refresh)

