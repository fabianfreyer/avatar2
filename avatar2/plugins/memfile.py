from types import MethodType
import io
import os


class MemoryView(io.RawIOBase):
    def __init__(self, target, offset=0):
        self.offset = offset
        self.target = target

    @property
    def avatar(self):
        return self.target.avatar

    def readable(self):
        return True

    def writeable(self):
        return True

    def seekable(self):
        return True

    def flush(self):
        pass

    def isatty(self):
        return False

    def fileno(self):
        raise OSError("No filedescriptor associated with this memory view")

    def truncate(self, size=None):
        raise io.UnsupportedOperation("Cannot truncate memory view")

    def seek(self, offset, whence=os.SEEK_SET):
        if whence == os.SEEK_SET:
            self.offset = offset
        if whence == os.SEEK_CUR:
            self.offset += offset
        if whence == os.SEEK_END:
            self.offset = self.avatar.memory_ranges.end()
        return self.offset

    def tell(self):
        return self.offset


def add_methods(target):
    target.memory = MethodType(MemoryView, target)


def target_added_callback(avatar, *args, **kwargs):
    target = kwargs["watched_return"]
    add_methods(target)


def load_plugin(avatar):
    if "gdb_memory_map_loader" not in avatar.loaded_plugins:
        avatar.load_plugin("gdb_memory_map_loader")

    avatar.watchmen.add_watchman(
        "AddTarget", when="after", callback=target_added_callback
    )
    for target in avatar.targets.values():
        add_methods(target)
