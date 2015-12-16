from config import ProjectConfig, config
from git import Repository, Commit
from docker import Container, Image, BaseImage, DockerException
from matcher import Role
import dns
import runner
import logging
from enum import Enum
import shutil
import subprocess
import colorclass
import time
import os


class State(Enum):
    REPOSITORY = 1
    IMAGE = 2
    CONTAINER = 3
    RUNNING = 4

    def __str__(self):
        return self.name

    def colored(self):
        colors = {
            1: 'autored',
            2: 'autoblack',
            3: 'autowhite',
            4: 'autogreen',
        }
        c = colors[self.value]
        return colorclass.Color("{%s}%s{/%s}" % (c, self.name, c))

class Status(Enum):
    NEW = 1
    DIRTY = 2
    CLEAN = 3
    def __str__(self):
        return self.name

    def colored(self):
        colors = {
            1: 'autoblack',
            2: 'autored',
            3: 'autogreen',
        }
        c = colors[self.value]
        return colorclass.Color("{%s}%s{/%s}" % (c, self.name, c))

class Mode(Enum):
    WORKSTATION = 1
    SERVER = 2
    MANUAL = 3
    def __str__(self):
        return self.name

    def colored(self):
        colors = {
            1: 'autoyellow',
            2: 'autored',
            3: 'autogreen',
        }
        c = colors[self.value]
        return colorclass.Color("{%s}%s{/%s}" % (c, self.name, c))


class Dork:

    def __init__(self, repository):
        """
        :param
        :type repository: Repository
        """
        self.repository = repository
        self.conf = ProjectConfig(self.repository)
        levels = {
            'error': logging.ERROR,
            'warn': logging.WARNING,
            'info': logging.INFO,
            'debug': logging.DEBUG,
        }
        self.logger = logging.Logger(self.name, level=levels[config.log_level])
        self.logger.addHandler(logging.StreamHandler())

    @classmethod
    def scan(cls, directory):
        """
        :param str directory: the working directory
        :return iterator over a list of Dorks
        :type directory: str
        :rtype list[Dork]
        """
        def _compare(a, b):
            """
            :type a: Dork
            :type b: Dork
            """
            if a.project != b.project:
                if a.name < b.name:
                    return -1
                elif a.name > b.name:
                    return 1
                else:
                    return 0
            else:
                if a.repository.current_commit < b.repository.current_commit:
                    return -1
                elif a.repository.current_commit > b.repository.current_commit:
                    return 1
                else:
                    return 0

        return sorted([
            Dork (repo) for repo in Repository.scan(directory)], cmp=_compare)

    @classmethod
    def enforce_max_containers(cls):
        """
        Stop containers until the max_containers setting is satisfied.
        :return:
        """
        # Stop containers until maximum amount of simultaneous containers is
        # met.
        max_containers = config.max_containers
        stop_count = 0
        if max_containers > 0:
            running = [c for c in Container.list() if c.running]
            running.sort(key=lambda cont: cont.time_started)
            running.reverse()
            while len(running) > max_containers:
                stop = running.pop()
                logging.debug("Too many containers running. Stopping %s.", stop)
                stop.stop()
        logging.info("Stopped %s containers to respect limit of %s running containers.", stop_count, max_containers)

    # ======================================================================
    # DOCKER COMPONENTS
    # ======================================================================
    @property
    def container(self):
        """
        Retrieve the closest matching container.

        :rtype: Container
        """
        return self.__closest([
            c for c in Container.list()
            if c.project == self.project
            and c.instance == self.instance
        ])

    @property
    def image(self):
        """
        Retrieve the closes matching image.

        :rtype: Image
        """
        return self.__closest([
            i for i in Image.list()
            if i.project == self.project
        ])

    # ======================================================================
    # PROJECT & INSTANCE PROPERTIES
    # ======================================================================
    @property
    def project(self):
        return self.conf.project

    @property
    def instance(self):
        return self.conf.instance

    @property
    def name(self):
        if self.project == self.instance:
            return self.project
        else:
            return "%s.%s" % (self.project, self.instance)

    # ======================================================================
    # STATUS PROPERTIES
    # ======================================================================
    @property
    def mode(self):
        """
        :rtype: DorkMode
        """
        if self.project == self.instance:
            return Mode.WORKSTATION
        if self.repository.directory.replace("%s/%s/" % (self.conf.host_source_directory, self.project), '') == self.repository.branch:
            return Mode.SERVER
        return Mode.MANUAL

    @property
    def state(self):
        if not self.image and not self.container:
            return State.REPOSITORY
        if not self.container and self.image:
            return State.IMAGE
        if not self.container.running:
            return State.CONTAINER
        return State.RUNNING

    @property
    def status(self):
        if not self.container or self.container.hash == 'new':
            return Status.NEW
        if self.repository.current_commit.hash == self.container.hash:
            return Status.CLEAN
        return Status.DIRTY

    __roles = None

    @property
    def roles(self):
        """
        :rtype: dict[str, Role]
        """
        if not self.__roles:
            self.__roles = {r.name: r for r in Role.tree(self.repository) }
        return self.__roles

    @property
    def tags(self):
        """
        Retrieve the list of currently tags that are required to execute an
        update.

        :rtype: list[str]
        """
        changes = self.repository.current_commit % Commit(self.container.hash, self.repository)
        for name, role in self.roles.iteritems():
            tags = role.update_triggers(changes)
            for tag in tags:
                yield tag

    @property
    def triggers(self):
        """:rtype: list[str]"""
        patterns = []
        for name, role in self.roles.iteritems():
            for pattern in role.triggers():
                if pattern not in patterns:
                    patterns.append(pattern)
        return patterns

    @property
    def active_triggers(self):
        """:rtype: list[str]"""
        patterns = []
        for name, role in self.roles.iteritems():
            for pattern in role.active_triggers:
                if pattern not in patterns:
                    patterns.append(pattern)
        return patterns

    @property
    def disabled_triggers(self):
        """
        :rtype: list[str]
        """
        return [p for p in self.triggers if p not in self.active_triggers]

    # ======================================================================
    # LIFECYCLE INTERFACE
    # ======================================================================
    def clear(self):
        self.debug('clearing metadata caches')
        Role.clear(self.repository)

    def create(self, startimage=False):
        """
        If no matching container is found, a new one will be created. If
        a matching container already exists, nothing happens.

        :returns [True] if a container is ready.
        :rtype: bool
        """
        self.debug('Attempting to create container.')
        # Abort early if a container is available.
        if self.container:
            self.debug('Reusing existing container %s.', self.container)
            return True

        self.info('No container found, creating a new one.')

        if startimage:
            image = False
            for i in Image.list():
                if i.name == startimage:
                    image = i
                    break
            if not image:
                self.err('Image %s could not be found.', startimage)
                return False
            if Commit(image.hash, self.repository) <= self.repository.current_commit:
                self.info('Using %s as new starting point.', startimage)
                pass
            else:
                self.err('%s is not a valid starting point for this repository.', startimage)
                return False
        else:
            # Retrieve the closest image.
            image = self.image

            # Retrieve the closest container.
            container = self.__closest([
                c for c in Container.list()
                if c.project == self.project
            ])
            """:type: Container"""


            if image and container:
                # If both image and container exist, check if the container is newer
                # and commit if necessary.
                self.debug("Comparing %s with %s.", container, image)
                commit_container = Commit(container.hash, self.repository)
                commit_image = Commit(image.hash, self.repository)
                if commit_image.hash == 'new' or commit_container > commit_image:
                    image_name = "%s/%s" % (self.project, container.hash)
                    self.debug("%s is newer than %s", container, image)
                    self.info("Committing new image %s.", image_name)
                    container.commit(image_name)
                    image = self.image
                else:
                    self.debug("%s is older than %s.", container, image)
                    self.debug("Reusing existing image.")
            elif container:
                # Only a compatible container exists, commit it to create an image.
                self.info("No image found, committing %s.", container)
                image_name = "%s/%s" % (self.project, container.hash)
                container.commit(image_name)
                image = self.image
            elif image:
                # Only an image exists, simply use it.
                self.debug("No container found, building from %s", image)
            else:
                # No starting point available. Building from base image.
                if self.repository.branch in self.conf.root_branch:
                    base = self.conf.base_image
                    self.warn("No image or container, starting from %s", base)
                    image = BaseImage(self.project, base)
                else:
                    self.err(
                        "No valid starting point found. Either branch \"%s\" needs to be built first or \"%s\" has to be rebased.",
                        self.conf.root_branch, self.repository.branch)
                    return False

        # Build correct container name.
        container_name = "%s.%s.%s" % (self.project, self.instance, image.hash)

        # Define volume directories.
        host_src_dir = self.repository.directory

        host_bld_dir = "%s/%s/%s" % (
            self.conf.host_build_directory,
            self.project,
            self.instance
        )
        host_log_dir = "%s/%s/%s" % (
            self.conf.host_log_directory,
            self.project,
            self.instance
        )

        container_volumes = {
            host_src_dir: self.conf.dork_source_directory,
            host_bld_dir: self.conf.dork_build_directory,
            host_log_dir: self.conf.dork_log_directory,
        }

        # Create the container
        if self.project == self.instance:
            domain = "%s.dork" % self.project
        else:
            domain = "%s.%s.dork" % (self.project, self.instance)

        Container.create(container_name, image.name, container_volumes, domain)
        self.info("Successfully created %s from %s.", container_name, image.name)
        return True

    def start(self):
        """
        Tries to start the container. If there is no matching container [False]
        will be returned. If the container is already running, [True] will be
        returned and nothing happens.

        If a container with the same combination of [Container.project] and
        [Container.instance] exists it will be stopped. If the maximum amount
        of containers is reached, the longest running will be stopped.

        :return: Boolean value indicating if a matching container is running.
        """
        # Abort if there is no container
        self.debug('Attempting to start container.')
        if not self.container:
            self.err("Cannot start. No matching container found.")
            return False

        # Skip if container is already running
        if self.container.running:
            self.info("No need to start. Container already running.")
            return True

        # Stop containers within the same instance
        for c in Container.list():
            if c.project == self.project and c.instance == self.instance and c.running:
                self.info("Stopping sibling %s.", c)
                c.stop()

        # Start the container.
        self.container.start()

        start = time.time()
        while not self.container.accessible:
            self.debug('Container not accessible, retrying.')
            if time.time() - start > self.conf.startup_timeout:
                self.err("Could not connect to container.")
                return False
            time.sleep(1)

        dns.refresh()
        self.info("Successfully started container.")
        # Now, stop containers until limit is met.
        Dork.enforce_max_containers()
        return True

    def stop(self):
        """
        Stop the matching container. Returns [True] if actually a container
        has been stopped.

        :return: [True] if there is no more container running.
        :rtype: bool
        """
        self.debug("Attempting to stop container.")
        # Abort if there is no container
        if not self.container:
            self.err("Cannot stop. No matching container found.")
            return True

        # Skip if container is already running
        if not self.container.running:
            self.info("No need to stop. Container not running.")
            return True

        # Stop the container
        self.container.stop()
        dns.refresh()
        self.info("Successfully stopped container.")
        return True

    def update(self):
        """
        Execute necessary updates on this dork.

        :return: [True] if the update succeeded.
        :rtype: bool
        """
        self.debug('Attempting to run update.')
        if not self.container:
            self.err("Cannot update, container does not exist.")
            return False

        if not self.container.running:
            self.err("Cannot update, container not running.")
            return False

        # Get current HEAD commit hash.
        current_hash = self.repository.current_commit.hash

        # Iterate over matching roles to generate list of necessary tags.
        tags = []
        if not self.status == Status.NEW:
            container_commit = Commit(self.container.hash, self.repository)
            changes = self.repository.current_commit % container_commit
            self.info("Found %s changed files.", len(changes))
            for name, role in self.roles.iteritems():
                matched = role.update_triggers(changes)
                if matched:
                    self.debug("Matched %s in %s.", matched, role.name)
                    tags += matched
            self.info("Applying %s to update.", tags)
        else:
            Role.clear(self.repository)
            self.warn("Container is new, running full build.")

        # If there are no tags, execute 'always' tags.
        if not tags and self.status != Status.NEW:
            tags.append('always')

        # If there are any tags, run the update.
        if tags or self.status == Status.NEW:
            if self.__play(tags):
                self.info("Update successful.")
            else:
                self.err("Update failed.")
                return False
        else:
            self.warn("No tags found, update not necessary.")

        if current_hash != self.container.hash:
            # Rename the container to the current commit hash.
            self.info("Renaming to commit hash %s.", current_hash)
            self.container.rename("%s.%s.%s" % (
                self.project,
                self.instance,
                current_hash
            ))

            # Restart the container to ensure data docker metadata integrity.
            # Necessary due to a docker bug.
            self.info("Restarting container.")
            self.container.stop()
            self.container.start()
            dns.refresh()

            if self.repository.branch in self.conf.root_branch and self.mode == Mode.WORKSTATION:
                self.info('Branch %s updated. Committing new image.', self.repository.branch)
                self.commit()
            else:
                self.debug('%s != %s or %s != %s. NOT committing new image.',
                           self.conf.root_branch, self.repository.branch,
                           self.mode, Mode.WORKSTATION)

        self.info("Update successful.")
        return True

    def build(self, tags=None, skip_tags=None):
        """
        Run all necessary build instructions for this dork.

        :return: [True] if the build succeeded.
        :rtype: bool
        """
        Role.clear(self.repository)
        self.debug('Attempting to run full build.')
        if not self.container:
            self.err("Cannot build, container does not exist.")
            return False

        if not self.container.running:
            self.err("Cannot build, container not running.")
            return False

        self.__play(tags, skip_tags)
        self.debug("Build successful.")
        return True

    @property
    def variables(self):
        return self.conf.variables()

    def __play(self, tags=None, skip_tags=None):
        # Retrieve extra variables from configuration.
        extra_vars = self.variables
        self.debug("Variables: %s", extra_vars)

        # Iterate over matching roles and build a list of tags that have NOT
        # been matched, to be used as list of exclude tags.
        skip_tags = self.disabled_triggers + skip_tags if skip_tags else self.disabled_triggers
        self.debug("Skipping tags: %s", skip_tags)

        return runner.apply_roles(
            [name for name, role in self.roles.iteritems()],
            self.container.address, self.repository,
            extra_vars, tags, skip_tags) == 0

    def clean(self):
        """
        Remove all containers and images used by them that are valid ancestors
        of any other container, and therefore not tips of the git tree.
        If the current dork is running in server mode, the scope
        is expanded to all dorks withing the same project and their source
        and build directories will be removed too.

        :return: [True] if the cleanup was successfull.
        :rtype: bool
        """
        self.debug("Attempting cleanup.")

        # Select containers to operate on, based on current Mode.
        if self.mode == Mode.SERVER:
            self.info("Automatic server cleanup, using project scope.")
            containers = [c for c in Container.list()
                          if c.project == self.project]
        else:
            self.info("Instance scope cleanup.")
            containers = [c for c in Container.list()
                          if c.project == self.project
                          and c.instance == self.instance]

        # Add containers to removable that are ancestors of other ones.
        removable_containers = [c for c in containers
                     if c.id != self.container.id
                     and self.__is_removable(c, containers)]

        # Remove containers. If in Server mode, remove source and build
        # directories too.
        for remove in removable_containers:
            self.debug("Removing: %s", remove)
            # Never remove the root branch container in server mode.
            if remove.repository.branch in self.conf.root_branch and self.mode == Mode.SERVER:
                continue

            # Remove the container.
            self.debug("Removing %s", remove)
            remove.stop()
            remove.remove()

            if self.mode == Mode.SERVER:
                # Remove the source directory only if in server mode.
                if os.path.exists(remove.source):
                    self.debug("Removing directory %s.", remove.source)
                    shutil.rmtree(remove.source)
                # Try to remove the image if in server mode.
                for image in Image.list():
                    if image.id == remove.image and image.name != self.conf.base_image:
                        try:
                            image.delete()
                        except DockerException:
                            pass

                # Remove the build directory.
                if os.path.exists(remove.build):
                    self.debug("Removing directory %s.", remove.build)
                    call = ['sudo', 'rm', '-rf', remove.build]
                    if subprocess.call(call) != 0:
                        self.warn("Unable to remove build directory %s.", remove.build)

                # Remove the logs directory.
                if os.path.exists(remove.logs):
                    self.debug("Removing directory %s.", remove.logs)
                    call = ['sudo', 'rm', '-rf', remove.logs]
                    if subprocess.call(call) != 0:
                        self.warn("Unable to remove logs directory %s.", remove.logs)

        # Remove images that are ancestors of other images.
        images = [i for i in Image.list() if i.project == self.project]
        removable_images = [i for i in images if self.__is_removable(i, images)]

        for remove in removable_images:
            try:
                remove.delete()
            except DockerException:
                pass

        self.info("Cleanup successfull, removed %s containers and %s images.",
                  len(removable_containers), len(removable_images))
        return True

    def commit(self):
        """
        Commit the currently running container to create a new starting point
        for future containers.

        :return: [True] if a new image was commited.
        :rtype: bool
        """
        self.debug("Attempting to commit container.")
        if not self.container:
            self.err("No matching container for %s.%s found")
            return False

        if not self.status == Status.CLEAN:
            self.err("Can't commit dirty container.")
            return False

        image_name = '%s/%s' % (self.project, self.container.hash)
        self.container.commit(image_name)
        self.info("Successfully committed container to %s", image_name)
        return True

    def remove(self):
        """
        Remove all containers associated with this dork. If in workstation
        mode, all images will be removed tooo.

        :return: [True] if the removal was successfull.
        :rtype: bool
        """
        # Remove containers.
        self.debug("Removing all containers.")
        container_count = 0
        for c in Container.list():
            if c.project == self.project and c.instance == self.instance:
                c.remove()
                container_count += 1
                self.debug("Removed %s.", c)
        self.info("Removed %s containers.", container_count)

        # Remove images if in workstation mode.
        if self.mode == Mode.WORKSTATION:
            image_count = 0
            self.warn("Workstation mode, removing all images.")
            for i in Image.list():
                if i.project == self.project:
                    i.delete()
                    image_count += 1
                    self.debug("Removed %s.", i)
            self.info("Removed %s images.", image_count)

        # Remove dangling images.
        self.debug("Cleaning dangling images.")
        dangling_count = 0
        for i in Image.dangling():
            i.delete()
            self.debug("Removed %s.", i.id)

        self.info("Removed %s dangling images.", dangling_count)
        return True

    # ======================================================================
    # PRIVATE HELPERS
    # ======================================================================
    def __closest(self, items):
        """
        Retrieve the closest among a list of items.

        :param items:
        :rtype: object
        """
        closest_object = None
        closest_commit = None
        for item in items:
            commit = Commit(item.hash, self.repository)
            if commit <= self.repository.current_commit:
                if closest_object is None or closest_commit < commit:
                    closest_commit = commit
                    closest_object = item
        return closest_object

    def __is_removable(self, obj, siblings):
        commit = Commit(obj.hash, self.repository)
        for s in siblings:
            if Commit(s.hash, self.repository) > commit:
                return True
        return False

    # ======================================================================
    # LOGGING
    # ======================================================================
    def _log(self, msg, color):
        return colorclass.Color("{%s}[%s] %s{/%s}" % (color, self.name, msg, color))

    def debug(self, msg, *args):
        self.logger.debug(self._log(msg, 'autoblack'), *args)

    def info(self, msg, *args):
        self.logger.info(self._log(msg, 'autogreen'), *args)

    def warn(self, msg, *args):
        self.logger.warn(self._log(msg, 'autoyellow'), *args)

    def err(self, msg, *args):
        self.logger.error(self._log(msg, 'autored'), *args)

