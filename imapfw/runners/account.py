
from ..error import InternalError
from ..types.account import Account
from ..types.repository import RepositoryBase
#from ..constants import CTL


class AccountTaskRunnerInterface(object):
    def getTask(self):
        raise NotImplementedError

    def consume(self):
        raise NotImplementedError


class SyncAccount(AccountTaskRunnerInterface):
    """The runner to consume account names, one by one.

    Designed to be used by the generic ConsummerRunner.

    Prepare the environement inside the worker and run the engine.
    """

    def __init__(self, ui, rascal, tasks,
        accountEmitter, leftEmitter, rightEmitter):

        self._ui = ui
        self._rascal = rascal
        self._tasks = tasks
        self._accountEmitter = accountEmitter
        self._left = leftEmitter  # Control the left driver (emitter).
        self._rght = rightEmitter # Control the right driver (emitter).

        self._engine = None
        self._account = None
        self._continue = True
        self._syncFolders = []


    def getTask(self):
        return self._tasks.getTask()

    def consume(self, accountName):
        """The runner for syncing an account in a worker.

        :accountName: the account name to sync.
        """

        #
        # Really start here.
        #
        self._ui.infoL(2, "syncing %s"% accountName)

        self._account = self._rascal.get(accountName, [Account])
        leftRepository = self._rascal.get(
            self._account.left.__name__, [RepositoryBase])
        rghtRepository = self._rascal.get(
            self._account.right.__name__, [RepositoryBase])

        self._left.buildDriverForRepository(leftRepository.getName())
        self._rght.buildDriverForRepository(rghtRepository.getName())

        # Connect the drivers.
        self._left.connect()
        self._rght.connect()

        # Initialize the repository instances.
        leftRepository.fw_init(self._left)
        rghtRepository.fw_init(self._rght)

        # Fetch folders concurrently.
        self._left.fetchFolders()
        self._rght.fetchFolders()

        # Get the folders from both sides so we can feed the folder tasks.
        leftFolders = self._left.getFolders()
        rghtFolders = self._rght.getFolders()

        # Merge the folder lists.
        mergedFolders = []
        for sideFolders in [leftFolders, rghtFolders]:
            for folder in sideFolders:
                if folder not in mergedFolders:
                    mergedFolders.append(folder)

        # Pass the list to the account.
        rascalFolders = self._account.syncFolders(mergedFolders)

        # The rascal might request for non-existing folders!
        syncFolders = []
        ignoredFolders = []
        for folder in rascalFolders:
            if folder in mergedFolders:
                syncFolders.append(folder)
            else:
                ignoredFolders.append(folder)

        if len(ignoredFolders) > 0:
            self._ui.warn("rascal, you asked to sync non-existing folders"
                " for '%s': %s", self._account.getName(), ignoredFolders)

        if len(syncFolders) < 1:
            self._continue = False # Nothing to do, stop here.

        self._syncFolders = syncFolders
        self._continue = True

        ## Feed the folder tasks.
        #self._accountEmitter.startFolderWorkers(accountName, syncFolders)
        ## Block until all the folders are synced.
        #self._accountEmitter.serveFolderWorkers()

        #TODO: move out.
        # Leave the driver in Authenticated state.
        self._left.logout()
        self._rght.logout()

        self._left.stopServing()
        self._rght.stopServing()

        self._ui.infoL(3, "syncing %s done"% accountName)
