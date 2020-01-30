from types import MethodType
import io
import os


class MemoryView(io.RawIOBase):
    """
    Represents a cursor into the memory of a target, implementing 
    the io.RawIOBase protocol.
    """

    def __init__(self, target, offset=0):
        self.offset = offset
        self.target = target

    @property
    def avatar(self):
        """
        Back-reference to the avatar instance
        """
        return self.target.avatar

    def readable(self):
        """
        Returns if the memory range the cursor points into is
        readable 
        """
        memory_range = self.memory_range
        if memory_range is None:
            return False
        return "r" in memory_range.permissions

    def writeable(self):
        """
        Returns if the memory range the cursor points into is
        writeable
        """
        memory_range = self.memory_range
        if memory_range is None:
            return False
        return "w" in memory_range.permissions

    def seekable(self):
        """
        Always returns `True`.
        """
        return True

    def flush(self):
        """
        No-op. Writes are not buffered.
        """
        pass

    def isatty(self):
        """
        Always returns `False`.
        """
        return False

    def fileno(self):
        """
        raises an OSError; no file number is associated with this object 
        """
        raise OSError("No filedescriptor associated with this memory view")

    def truncate(self, size=None):
        """
        raises an io.UnsupportedOperation.
        """
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
        """
        Return the current position in the file
        """
        return self.offset

    @property
    def memory_range(self):
        """
        A property reflecting the memory range that the cursor currently
        points into.
        """
        return self.avatar.get_memory_range(self.offset)

    def read(self, size=-1):
        """
        Read a specified number of memory bytes.

        :param size: The number of bytes to read. `read` will read until
                     the end of the memory range the cursor points into if
                     left unspecified or -1.
        :returns:    A bytes-like object containing the memory read. May
                     be shorter than `size` if near the end of the current
                     memory range.
        """
        memory_range = self.memory_range
        if not self.readable():
            # From io.RawIOBase.readinto:
            # If the object is in non-blocking mode and no bytes
            # are available, None is returned.
            return None

        # By default, try to read as much as possible; if we are close
        # to the end of a memory range, read just the remaining memory.
        memory_range_end = memory_range.address + memory_range.size
        max_read = memory_range_end - self.offset
        to_read = max_read if size == -1 else min(size, max_read)

        read = self.target.read_memory(self.offset, size, raw=True)
        self.offset += size
        return read

    def readall(self):
        """
        Read memory until the end of the memory range the curser points
        into.
        """
        return self.read(-1)

    def readinto(self, b):
        """
        Read memory into a bytearray.

        :param b: a pre-allocated bytearray to read into
        :returns: the number of bytes written or `None` if nothing
                  could be read. This can be less than the length
                  of `b` if the cursor is near the end of a
                  memory range.
        """
        read = self.read(len(b))
        size = len(read)
        b[:size] = read
        return size

    def write(self, data):
        """
        Read memory from a bytes-like object to the current cursor
        position, overwriting any previous memory.

        :param data: a bytes-like object to be written
        :returns:    the number of bytes written or `None` if nothing
                     could be written. This can be less than the length
                     of `data` if the cursor is near the end of a
                     memory range.
        """
        memory_range = self.memory_range
        if not self.writeable():
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
