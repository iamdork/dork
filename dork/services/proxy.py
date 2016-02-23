from ..docker import containers, events
from urlparse import urlparse
from ..config import config

from libmproxy import controller, proxy
from libmproxy.proxy.server import ProxyServer
from libmproxy.proxy.config import ServerSpec, Address
import threading

registry = {}
address = urlparse(config.docker_address).hostname


def refresh(*args):
    global registry
    registry = {}
    for container in containers(True):
        if container.running:
            registry[container.domain] = container.hostPort(80)


class DorkMaster(controller.Master):
    def __init__(self, server):
        controller.Master.__init__(self, server)

    def run(self):
        try:
            return controller.Master.run(self)
        except KeyboardInterrupt:
            self.shutdown()

    def handle_request(self, flow):
        global registry
        host = flow.request.headers['host'].split(':')[0]
        if host in registry:
            flow.request.port = int(registry[host])
            flow.request.headers['X-DORK-HOST'] = flow.request.headers['host']
            flow.request.headers['X-DORK-IP'] = '192.168.64.1'
            flow.request.headers['X-DORK-PORT'] = bytes(registry[host])
        flow.reply()


def server(config, eventstream, killsignal):
    refresh()
    p = DorkMaster(ProxyServer(proxy.ProxyConfig(
            port=8080,
            mode='reverse',
            upstream_server=ServerSpec('http', Address.wrap((address, 80))),
    )))
    thread = threading.Thread(target=p.run)
    thread.start()
    killsignal.subscribe(lambda v: p.shutdown())
    try:
        (eventstream
            .filter(lambda e: 'container' in e)
            .filter(lambda e: e['event'] in ['start', 'stop'])
            .subscribe(refresh))
    except Exception as exc:
        p.shutdown()


