"""
Dynamic host file management.
"""
from __future__ import absolute_import, print_function

from ..docker import Container, events

from dnslib import RR, QTYPE, TXT, RCODE
from dnslib.server import DNSServer, BaseResolver
from urlparse import urlparse
from ..config import config

"""
Dynamic host file management.
"""

registry = {}


def __resolve(domain):
    return registry[domain] if domain in registry else None


def __refresh(*args):
    global registry
    registry = {}
    for container in Container.list():
        if container.running:
            registry[container.domain] = '127.0.0.1'


class DorkResolver(BaseResolver):
    def resolve(self, request, handler):
        reply = request.reply()
        qname = request.q.qname
        domain = qname.__str__().strip('.')
        global registry

        if domain in registry:
            reply.add_answer(RR(qname, QTYPE.TXT, rdata=TXT(registry[domain])))
        else:
            reply.header.rcode = RCODE.NXDOMAIN

        return reply


def __filter_container(event):
    return 'container' in event


def server(conf):
    __refresh()
    dnsserver = DNSServer(
            resolver=DorkResolver(),
            address="127.0.0.1",
            port=5354
    )
    dnsserver.start_thread()

    try:
        events().filter(lambda e: 'container' in e).filter(lambda e: e['event'] in ['start', 'stop']).subscribe(__refresh)
    except Exception as exc:
        pass
    finally:
        dnsserver.stop()
