import os
import sys
import time


def _for_archive(self, archive):
    """Resolve suitable defaults from the archive.

    Resolve the date_time, compression attributes, and external attributes
    to suitable defaults as used by :method:`ZipFile.writestr`.

    Return self.
    """
    # gh-91279: Set the SOURCE_DATE_EPOCH to a specific timestamp
    epoch = os.environ.get('SOURCE_DATE_EPOCH')
    get_time = int(epoch) if epoch else time.time()
    self.date_time = time.localtime(get_time)[:6]

    self.compress_type = archive.compression
    self.compress_level = archive.compresslevel
    if self.filename.endswith('/'):  # pragma: no cover
        self.external_attr = 0o40775 << 16  # drwxrwxr-x
        self.external_attr |= 0x10  # MS-DOS directory flag
    else:
        self.external_attr = 0o600 << 16  # ?rw-------
    return self


ForArchive = type(
    'ForArchive',
    (),
    dict(_for_archive=_for_archive) if sys.version_info < (3, 14) else dict(),
)
