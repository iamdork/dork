import inject
import Docker


class DNS:
    docker = inject.attr(Docker)

    def __init__(self):
        pass

    def update_hosts(self):
        hostsfile = []
        dork_section = False
        replaced = False
        with open('/etc/hosts') as f:
            for l in f.readlines():
                if '# DORK END' in l:
                    replaced = True
                    dork_section = False

                if dork_section:
                    hostsfile += self.__get_hosts()
                    continue

                hostsfile.append(l.strip())

                if '# DORK START' in l:
                    dork_section = True
        if not replaced:
            hostsfile.append('# DORK START')
            hostsfile += self.__get_hosts()
            hostsfile.append('# DORK END')

        with open('/etc/hosts', 'w+') as f:
            f.write('\n'.join(hostsfile) + '\n')

    def __get_hosts(self):
        lines = []
        for c in self.docker.containers:
            if not c.running:
                continue

            line = list()
            line.append(c.address)
            line.append('.'.join([c.project, c.instance, 'dork']))
            if c.project is c.instance:
                line.append('.'.join([c.project, 'dork']))
            lines.append(' '.join(line))
        return lines
