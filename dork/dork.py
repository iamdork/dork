import config
from git import Repository, Commit
from docker import Container, Image, BaseImage
from matcher import Role
import dns
import runner
import logging
from enum import Enum
import shutil
import colorclass


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
        self.conf = config.config()
        levels = {
            'error': logging.ERROR,
            'warn': logging.WARNING,
            'info': logging.INFO,
            'debug': logging.DEBUG,
        }
        self.logger = logging.Logger(self.name, level=levels[self.conf.log_level])
        self.logger.addHandler(logging.StreamHandler())

    @classmethod
    def scan(cls, directory):
        """
        :param str directory: the working directory
        :return iterator over a list of Dorks
        :type directory: str
        :rtype list[Dork]
        """
        for repo in Repository.scan(directory):
            yield Dork(repo)

    @classmethod
    def enforce_max_containers(cls):
        """
        Stop containers until the max_containers setting is satisfied.
        :return:
        """
        # Stop containers until maximum amount of simultaneous containers is
        # met.
        max_containers = config.config().max_containers
        if max_containers > 0:
            running = [c for c in Container.list() if c.running]
            running.sort(key=lambda cont: cont.time_created.total_seconds())
            while len(running) > max_containers:
                running.pop().stop()

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
        return self.__segments[0]

    @property
    def instance(self):
        return self.__segments[-1]

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
        if self.instance == self.repository.branch:
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

    @property
    def roles(self):
        """
        Dictionary of matching [Role]s and the corresponding matched
        role patterns.

        :rtype: dict[Role, list[str]]
        """
        roles = {}
        """:type: dict[Role, list[str]]"""

        # Add all roles that match the pattern.
        for role in Role.list():
            patterns = role.matching_pattern(self.repository)
            if len(patterns) > 0:
                roles[role] = patterns

        # Create list of roles that are already included in other roles.
        redundant = []
        for role in roles.keys():
            for r in roles.keys():
                if role.name in r.includes:
                    redundant.append(role)

        # Remove all redundant roles.
        for r in redundant:
            del roles[r]
        return roles

    @property
    def tags(self):
        """
        Retrieve the list of currently tags that are required to execute an
        update.

        :rtype: list[str]
        """
        for role, patterns in self.roles.iteritems():
            commit = Commit(self.container.hash, self.repository)
            tags = role.matching_tags(self.repository.current_commit % commit)
            for tag in tags:
                yield tag

    # ======================================================================
    # LIFECYCLE INTERFACE
    # ======================================================================
    def create(self):
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
            base = self.conf.base_image
            self.warn("No image or container, starting from %s", base)
            image = BaseImage(self.project)

        # Build correct container name.
        container_name = "%s.%s.%s" % (self.project, self.instance, image.hash)

        # Define volume directories.
        host_src_dir = self.repository.directory

        host_bld_dir = "%s/%s/%s" % (
            self.conf.host_build_directory,
            self.project,
            self.instance
        )

        container_volumes = {
            host_src_dir: self.conf.dork_source_directory,
            host_bld_dir: self.conf.dork_build_directory,
        }

        # Create the container
        Container.create(container_name, image.name, container_volumes)
        self.info("Successfully created %s from %s.", container, image)
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
            if c.project == self.project and c.instance == self.instance:
                self.info("Stopping sibling %s.", c)
                c.stop()

        # Start the container.
        self.container.start()
        dns.refresh()
        self.info("Successfully started container.")
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

        if self.status == Status.CLEAN:
            self.info("Container is clean, update not necessary.")
            return True

        # Get current HEAD commit hash.
        current_hash = self.repository.current_commit.hash

        # Iterate over matching roles to generate list of necessary tags.
        tags = []
        if not self.status == Status.NEW:
            container_commit = Commit(self.container.hash, self.repository)
            changes = self.repository.current_commit % container_commit
            self.info("Found %s changed files.", len(changes))
            for role, patterns in self.roles.iteritems():
                matched = role.matching_tags(changes)
                if matched:
                    self.debug("Matched %s in %s.", matched, role.name)
                    tags += matched
            self.info("Applying % to update.", tags)
        else:
            self.warn("Container is new, running full build.")

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

        self.info("Update successful.")

    def build(self):
        """
        Run all necessary build instructions for this dork.

        :return: [True] if the build succeeded.
        :rtype: bool
        """
        self.debug('Attempting to run full build.')
        if not self.container:
            self.err("Cannot build, container does not exist.")
            return False

        if not self.container.running:
            self.err("Cannot build, container not running.")
            return False

        if not self.status == Status.CLEAN:
            self.err("Cannot build, dork has to be updated first.")
            return False

        self.__play()
        self.debug("Build successful.")
        return True

    def __play(self, tags=None):
        # Retrieve extra variables from configuration.
        extra_vars = self.conf.project_vars(self.project)
        self.debug("Variables: %s", extra_vars)

        # Iterate over matching roles and build a list of tags that have NOT
        # been matched, to be used as list of exclude tags.
        skip_tags = []
        for role, patterns in self.roles.iteritems():
            skip_tags += [p for p in role.patterns.keys() if p not in patterns]
        self.debug("Skipping tags: %s", skip_tags)

        return runner.apply_roles(
            [role.name for role in self.roles],
            self.container.address,
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
        removable = []
        """:type: list[Container]"""

        self.debug("Attempting cleanup.")

        # Select containers to operate on, based on current Mode.
        if self.mode == Mode.SERVER:
            self.info("Automatic server cleanup, using project scope.")
            containers = [c for c in Container.list()
                          if c.project == self.project
                          and c.instance == self.instance]
        else:
            self.info("Instance scope cleanup.")
            containers = [c for c in Container.list()
                          if c.project == self.project]

        # Add containers to removable that are ancestors of other ones.
        for container in containers:
            if self.__is_removable(container, containers):
                removable.append(container)

        self.debug("Removing: %s", removable)

        # Remove containers. If in Server mode, remove source and build
        # directories too.
        for remove in removable:
            if self.mode == Mode.SERVER:
                self.debug("Removing directory %s.", remove.source)
                shutil.rmtree(remove.source)
                self.debug("Removing directory %s.", remove.build)
                shutil.rmtree(remove.build)
            self.debug("Removing %s", remove)
            remove.remove()
        self.info("Cleanup successfull, removed %s containers.", len(removable))

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
                    self.debug("Removed %i.", i)
            self.info("Removed %s images.", image_count)

        # Remove dangling images.
        self.debug("Cleaning dangling images.")
        dangling_count = 0
        for i in Image.dangling():
            i.delete()
            self.debug("Removed %s.", i.id)

        self.info("Removed %s dangling images.", dangling_count)

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

    @property
    def __segments(self):
        """
        :rtype: list[string]
        """
        return self.repository.directory \
            .replace(self.conf.host_source_directory + '/', '') \
            .split('/')

    def __is_removable(self, container, containers):
        commit = Commit(container.hash, self.repository)
        for c in containers:
            if Commit(c.hash, self.repository) > commit:
                return True
        return False

    # ======================================================================
    # LOGGING
    # ======================================================================
    def _log(self, msg):
        return "[%s] %s" % (self.name, msg)

    def debug(self, msg, *args):
        self.logger.debug(self._log(msg), *args)

    def info(self, msg, *args):
        self.logger.info(self._log(msg), *args)

    def warn(self, msg, *args):
        self.logger.warn(self._log(msg), *args)

    def err(self, msg, *args):
        self.logger.error(self._log(msg), *args)

