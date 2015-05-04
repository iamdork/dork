import argparse
import os
import config

def main():
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
        print('Status!!!')
        print(params)

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
        pass

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
        pass

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
        pass

    cmd_start.set_defaults(func=func_update, full=False)

    # ======================================================================
    # stop command
    # ======================================================================
    cmd_stop = subparsers.add_parser(
        'stop',
        help="""
        Stop any currently running container in this repository.
        """)

    def func_stop(params):
        pass

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
        pass

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
        pass

    cmd_boot.set_defaults(func=func_boot)

    # parse arguments and execute 'func'
    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()