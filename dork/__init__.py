import argparse
import os
import config
from terminaltables import AsciiTable
from dork import Dork, Mode, State, Status
from git import Commit
import json


def main():
    """Dork CLI interface"""
    parser = argparse.ArgumentParser(
        prog="dork",
        description="Dork - development workflow for everyone")

    # Repository argument
    parser.add_argument(
        '--directory', '-d',
        help="""
        Set the working directory.
        """)
    parser.set_defaults(directory=os.getcwd())

    # Repository argument
    parser.add_argument(
        '--logging', '-l',
        help="""
        Set the loglevel: error, warn, info, debug
        """)
    parser.set_defaults(logging='warn')

    subparsers = parser.add_subparsers(help="command help")

    # ======================================================================
    # status command
    # ======================================================================
    cmd_status = subparsers.add_parser(
        'status',
        help='Display a summary of the current status.')

    def func_status(params):
        rows = [[
            'Name',
            'Directory',
            'Branch',
            'Status',
            'State',
            'Mode',
        ]]
        for d in Dork.scan(os.path.abspath(params.directory)):
            rows.append([
                d.name,
                d.repository.directory,
                d.repository.branch,
                d.status.colored(),
                d.state.colored(),
                d.mode.colored()
            ])
        table = AsciiTable(rows)
        table.outer_border = False
        table.inner_column_border = False
        print("\n" + table.table + "\n")
        return 0

    cmd_status.set_defaults(func=func_status)

    # ======================================================================
    # info command
    # ======================================================================
    cmd_info = subparsers.add_parser(
        'info',
        help='Display detailed information.')

    def func_info(params):
        data = []
        for d in Dork.scan(os.path.abspath(params.directory)):
            data.append(['---------------'])
            data.append(['Project', d.project])
            data.append(['Instance', d.instance])
            data.append(['Roles', ', '.join([
                name for name, role in d.roles.iteritems()])])
            data.append(['Variables', json.dumps(d.variables)])
            data.append(['Patterns', ', '.join(d.active_triggers)])
            data.append(['Skip tags', ', '.join(d.disabled_triggers)])
            data.append(['Directory', d.repository.directory])
            data.append(['Branch', d.repository.branch])
            data.append(['HEAD', d.repository.current_commit.message])
            data.append(['Mode', d.mode.colored()])
            data.append(['State', d.state.colored()])
            if d.state == State.RUNNING:
                data.append(['Address', d.container.address])
            data.append(['Status', d.status.colored()])
            if d.status == Status.DIRTY:
                current = d.repository.current_commit
                commit = Commit(d.container.hash, d.repository)
                data.append(['Container HEAD', commit.message])
                data.append(['Update distance', "%s" % len(commit - current)])
                data.append(['Changed files', '\n'.join(commit % current)])
                tags = [t for t in d.tags]
                if len(tags) > 0:
                    data.append(['Update tags', ', '.join(d.tags)])
                else:
                    data.append(['Update tags', 'None'])
            data.append([''])

        table = AsciiTable(data)
        table.outer_border = False
        table.inner_column_border = False
        table.inner_heading_row_border = False
        print("\n" + table.table)
        return 0

    cmd_info.set_defaults(func=func_info)

    # ======================================================================
    # inventory command
    # ======================================================================
    cmd_inventory = subparsers.add_parser(
        'inventory',
        help="""
        Print a dynamic ansible inventory for all matched running dorks.
        """)

    def func_inventory(params):
        inventory = {}
        for d in Dork.scan(os.path.abspath(params.directory)):
            if d.state == State.RUNNING:
                if d.project not in inventory:
                    inventory[d.project] = {
                        'hosts': [],
                        'vars': config.ProjectConfig(d.repository).variables()
                    }
                    inventory[d.project]['vars']['ansible_ssh_user'] = 'root'
                inventory[d.project]['hosts'].append(d.container.address)
        print(json.dumps(inventory))

    cmd_inventory.set_defaults(func=func_inventory)

    # ======================================================================
    # cache clear command
    # ======================================================================
    cmd_clear = subparsers.add_parser(
        'clear',
        help="""
        Clear the meta information cache for this dork.
        """)

    def func_clear(params):
        for d in Dork.scan(os.path.abspath(params.directory)):
            d.clear()

    cmd_clear.set_defaults(func=func_clear)


    # ======================================================================
    # create command
    # ======================================================================
    cmd_create = subparsers.add_parser(
        'create',
        help="""
        Create a container for this repository if necessary. If a container
        already exists, nothing happens.
        """)

    # Repository argument
    cmd_create.add_argument(
        '--image', '-i',
        help="""
        Use a different image to start from.
        """)

    def func_create(params):
        for d in Dork.scan(os.path.abspath(params.directory)):
            if not d.create(params.image):
                return -1

    cmd_create.set_defaults(func=func_create, image=False)

    # ======================================================================
    # start command
    # ======================================================================
    cmd_start = subparsers.add_parser(
        'start',
        help="""
        Ensures there is a running container for this repository. Automatically
        calls [create] if necessary.
        """)

    # Repository argument
    cmd_start.add_argument(
        '--image', '-i',
        help="""
        Use a different image to start from.
        """)

    def func_start(params):
        for d in Dork.scan(os.path.abspath(params.directory)):
            if not (d.create(params.image) and d.start()):
                return -1

    cmd_start.set_defaults(func=func_start, image=False)

    # ======================================================================
    # clean command
    # ======================================================================
    cmd_clean = subparsers.add_parser(
        'clean',
        help="""
        Clean unused containers.
        """)

    def func_clean(params):
        for d in Dork.scan(os.path.abspath(params.directory)):
            if d.container:
                d.clean()

    cmd_clean.set_defaults(func=func_clean)

    # ======================================================================
    # update command
    # ======================================================================
    cmd_update = subparsers.add_parser(
        'update',
        help="""
        Updates a the container to the current repository's HEAD and executes
        necessary steps based on the files changed.
        """)

    # Repository argument
    cmd_update.add_argument(
        '--image', '-i',
        help="""
        Use a different image to start from.
        """)

    def func_update(params):
        for d in Dork.scan(os.path.abspath(params.directory)):
            if not (d.create(params.image) and d.start() and d.update() and d.clean()):
                return -1

    cmd_update.set_defaults(func=func_update, image=False)

    # ======================================================================
    # build command
    # ======================================================================
    cmd_build = subparsers.add_parser(
        'build',
        help="""
        Runs the full build procedure.
        """)

    # Base image
    cmd_build.add_argument(
        '--image', '-i',
        help="""
        Use a different image to start from.
        """)

    # Tags to execute
    cmd_build.add_argument(
        '--tags',
        help="""
        Provide a list of ansible tags to execute.
        """)

    # Skip tags
    cmd_build.add_argument(
        '--skip-tags',
        help="""
        Provide a list of ansible tags to skip.
        """)

    def func_build(params):
        tags = params.tags.split(' ') if params.tags else []
        skip_tags = params.skip_tags.split(' ') if params.skip_tags else []
        for d in Dork.scan(os.path.abspath(params.directory)):
            if not (d.create() and d.start() and d.build(tags, skip_tags)):
                return -1


    cmd_build.set_defaults(func=func_build, image=False)
    # ======================================================================
    # commit command
    # ======================================================================
    cmd_commit = subparsers.add_parser(
        'commit',
        help="""
        Commit an image with the current state.
        """)

    def func_commit(params):
        for d in Dork.scan(os.path.abspath(params.directory)):
            if not d.commit():
                return -1

    cmd_commit.set_defaults(func=func_commit)
    # ======================================================================
    # stop command
    # ======================================================================
    cmd_stop = subparsers.add_parser(
        'stop',
        help="""
        Stop any currently running container in this repository.
        """)

    def func_stop(params):
        for d in Dork.scan(os.path.abspath(params.directory)):
            if not d.stop():
                return -1

    cmd_stop.set_defaults(func=func_stop)

    # ======================================================================
    # remove command
    # ======================================================================
    cmd_remove = subparsers.add_parser(
        'remove',
        help="""
        Remove all containers in this repository.
        """)

    def func_remove(params):
        for d in Dork.scan(os.path.abspath(params.directory)):
            if not (d.stop() and d.remove()):
                return -1

    cmd_remove.set_defaults(func=func_remove)

    # ======================================================================
    # boot command
    # ======================================================================
    cmd_boot = subparsers.add_parser(
        'boot',
        help="""
        Start all created containers, but don't create new ones.
        """)

    def func_boot(params):
        for d in Dork.scan(os.path.abspath(params.directory)):
            if d.container:
                if not d.start():
                    return -1

    cmd_boot.set_defaults(func=func_boot)

    # parse arguments and execute 'func'
    args = parser.parse_args()
    return args.func(args)

if __name__ == '__main__':
    main()
