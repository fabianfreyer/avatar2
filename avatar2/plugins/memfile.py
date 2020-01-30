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

    @property
    def memory_range(self):
        return self.avatar.get_memory_range(self.offset)

    def readinto(self, b):
        memory_range = self.memory_range
        if memory_range is None:
            # From io.RawIOBase.readinto:
            # If the object is in non-blocking mode and no bytes
            # are available, None is returned.
            return None

        memory_range_end = memory_range.address + memory_range.size

        # By default, try to read as much as possible; if we are close
        # to the end of a memory range, read just the remaining memory.
        size = min(len(b), memory_range_end - self.offset)

        read = self.target.read_memory(self.offset, size, raw=True)
        b[:size] = read
        self.offset += size
        return size

    def write(self, data):
        memory_range = self.memory_range
        if memory_range is None:
            # From io.RawIOBase.write:
            # None is returned if the raw stream is set not to block
            # and no single byte could be readily written to it
            return None

        memory_range_end = memory_range.address + memory_range.size

        size = min(len(data), memory_range_end - self.offset)
        to_write = data[:size]

        ret = self.target.write_memory(self.offset, size, to_write, raw=True)
        if ret == False:
            # write failed; return None.
            return None

        return size


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
