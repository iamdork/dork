import argparse
import os
import config
from terminaltables import AsciiTable
from dork import Dork, Mode, State, Status
from git import Commit
import logging

def main():
    # logging.basicConfig(level=logging.DEBUG)
    """Dork CLI interface"""
    parser = argparse.ArgumentParser(
        prog="dork",
        description="Dork - intelligent development containers.")

    # Repository argument
    parser.add_argument(
        '--working-directory', '-d',
        help="""
        Change the working directory.
        """)
    parser.set_defaults(repository=os.getcwd())
    subparsers = parser.add_subparsers(help="command help")

    # ======================================================================
    # status command
    # ======================================================================
    cmd_status = subparsers.add_parser(
        'status',
        help='Display a summary of the dorks status.')

    def func_status(params):
        dorks = [do for do in Dork.scan(params.working_directory)]
        if len(dorks) == 1:
            d = dorks[0]
            data = [
                ['Project', d.project],
                ['Instance', d.instance],
                ['Roles', ', '.join([
                    "%s (%s)" % (role.name, ', '.join(patterns))
                    for role, patterns in d.roles.iteritems()])],
                ['Repository', d.repository.directory],
                ['Repository commit', d.repository.current_commit.message],
                ['Mode', d.mode.colored()],
                ['State', d.state.colored()],
                ['Status', d.status.colored()],
            ]
            if d.status == Status.DIRTY:
                current = d.repository.current_commit
                commit = Commit(d.container.hash, d.repository)
                data.append(['Container commit', commit.message])
                data.append(['Update distance', "%s" % len(commit - current)])
                tags = [t for t in d.tags]
                if len(tags) > 0:
                    data.append(['Update tags', ', '.join(d.tags)])
                else:
                    data.append(['Update tags', 'None'])

            table = AsciiTable(data)
            table.inner_row_border = True
            print(table.table)
        else:
            rows = [[
                'Name',
                'Directory',
                'Status',
                'State',
                'Mode',
            ]]
            directory = params.working_directory
            for d in Dork.scan(directory):
                rows.append([
                    d.name,
                    d.repository.directory,
                    d.status.colored(),
                    d.state.colored(),
                    d.mode.colored()
                ])
            table = AsciiTable(rows)
            print(table.table)
        return 0

    cmd_status.set_defaults(func=func_status)

    # ======================================================================
    # create command
    # ======================================================================
    cmd_create = subparsers.add_parser(
        'create',
        help="""
        Create a container for this repository if necessary. If a container
        already exists, nothing happens.
        """)

    def func_create(params):
        for d in Dork.scan(params.working_directory):
            if not d.create():
                return -1

    cmd_create.set_defaults(func=func_create)

    # ======================================================================
    # start command
    # ======================================================================
    cmd_start = subparsers.add_parser(
        'start',
        help="""
        Ensures there is a running container for this repository. Automatically
        calls [create] if necessary.
        """)

    def func_start(params):
        for d in Dork.scan(params.working_directory):
            if not d.start():
                return -1

    cmd_start.set_defaults(func=func_start)

    # ======================================================================
    # update command
    # ======================================================================
    cmd_update = subparsers.add_parser(
        'update',
        help="""
        Updates a the container to the current repository's HEAD and executes
        necessary steps based on the files changed.
        """)

    cmd_update.add_argument(
        '--full', '-f', action="store_true",
        help="""
        Run the full ansible scripts instead of only tags identified by
        the changed files. Automatically calls [create] if necessary.
        """)

    def func_update(params):
        for d in Dork.scan(params.working_directory):
            if not d.update():
                return -1


    cmd_update.set_defaults(func=func_update)

    # ======================================================================
    # stop command
    # ======================================================================
    cmd_stop = subparsers.add_parser(
        'stop',
        help="""
        Stop any currently running container in this repository.
        """)

    def func_stop(params):
        for d in Dork.scan(params.working_directory):
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
        for d in Dork.scan(params.working_directory):
            if not d.remove():
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
        for d in Dork.scan(params.working_directory):
            if d.container:
                if not d.start():
                    return -1

    cmd_boot.set_defaults(func=func_boot)

    # parse arguments and execute 'func'
    args = parser.parse_args()
    return args.func(args)

if __name__ == '__main__':
    main()