def translatePath(p): return p


def exists(p):
    import os
    return os.path.exists(p)


def mkdirs(p):
    import os
    os.makedirs(p, exist_ok=True)
    return True
