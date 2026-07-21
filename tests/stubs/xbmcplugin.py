_added = []
_resolved = []


def addDirectoryItem(handle, url, listitem, isFolder=False, totalItems=0):
    _added.append((handle, url, listitem, isFolder))
    return True


def addDirectoryItems(handle, items, totalItems=0):
    for url, li, folder in items:
        _added.append((handle, url, li, folder))
    return True


def setResolvedUrl(handle, succeeded, listitem):
    _resolved.append((handle, succeeded, listitem))


def endOfDirectory(handle, succeeded=True):
    pass


def reset():
    _added.clear()
    _resolved.clear()
