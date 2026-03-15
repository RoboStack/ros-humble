# Copyright (c) 2009, Willow Garage, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the Willow Garage, Inc. nor the names of its
#       contributors may be used to endorse or promote products derived from
#       this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# Author Tully Foote/tfoote@willowgarage.com, Ken Conley/kwc@willowgarage.com

"""
Library for detecting the current OS, including detecting specific
Linux distributions.
"""

import codecs
# to be removed after Ubuntu Xenial is out of support
import sys
if sys.version_info >= (3, 8):
    import distro
else:
    import platform as distro
import locale
import os
import platform
import subprocess


def _read_stdout(cmd):
    try:
        pop = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (std_out, std_err) = pop.communicate()
        return std_out.decode(encoding='UTF-8').strip()
    except:
        return None


def uname_get_machine():
    """
    Linux: wrapper around uname to determine if OS is 64-bit
    """
    return _read_stdout(['uname', '-m'])


def read_issue(filename="/etc/issue"):
    """
    :returns: list of strings in issue file, or None if issue file cannot be read/split
    """
    if os.path.exists(filename):
        with codecs.open(filename, 'r', encoding=locale.getpreferredencoding()) as f:
            return f.read().split()
    return None


def read_os_release(filename=None):
    """
    :returns: Dictionary of key value pairs from /etc/os-release or fallback to 
      /usr/lib/os-release, with quotes stripped from values
    """
    if filename is None:
        filename = '/etc/os-release'
        if not os.path.exists(filename):
            filename = '/usr/lib/os-release'

    if not os.path.exists(filename):
        return None

    release_info = {}
    with codecs.open(filename, 'r', encoding=locale.getpreferredencoding()) as f:
        for line in f:
            key, val = line.rstrip('\n').partition('=')[::2]
            release_info[key] = val.strip('"')
    return release_info


class OsNotDetected(Exception):
    """
    Exception to indicate failure to detect operating system.
    """
    pass


class OsDetector(object):
    """
    Generic API for detecting a specific OS.
    """
    def is_os(self):
        """
        :returns: if the specific OS which this class is designed to
          detect is present.  Only one version of this class should
          return for any version.
        """
        raise NotImplementedError("is_os unimplemented")

    def get_version(self):
        """
        :returns: standardized version for this OS. (aka Ubuntu Hardy Heron = "8.04")
        :raises: :exc:`OsNotDetected` if called on incorrect OS.
        """
        raise NotImplementedError("get_version unimplemented")

    def get_codename(self):
        """
        :returns: codename for this OS. (aka Ubuntu Hardy Heron = "hardy").  If codenames are not available for this OS, return empty string.
        :raises: :exc:`OsNotDetected` if called on incorrect OS.
        """
        raise NotImplementedError("get_codename unimplemented")


class LsbDetect(OsDetector):
    """
    Generic detector for Debian, Ubuntu, Mint, and Pop! OS
    """
    def __init__(self, lsb_name, get_version_fn=None):
        self.lsb_name = lsb_name
        if distro.__name__ == "distro":
            self.lsb_info = (distro.id(), distro.version(), distro.codename())
        elif hasattr(distro, "linux_distribution"):
            self.lsb_info = distro.linux_distribution(full_distribution_name=0)
        elif hasattr(distro, "dist"):
            self.lsb_info = distro.dist()
        else:
            self.lsb_info = None

    def is_os(self):
        if self.lsb_info is None:
            return False
        # Work around platform returning 'Ubuntu' and distro returning 'ubuntu'
        return self.lsb_info[0].lower() == self.lsb_name.lower()

    def get_version(self):
        if self.is_os():
            return self.lsb_info[1]
        raise OsNotDetected('called in incorrect OS')

    def get_codename(self):
        if self.is_os():
            return self.lsb_info[2]
        raise OsNotDetected('called in incorrect OS')


class Debian(LsbDetect):

    def __init__(self, get_version_fn=None):
        super(Debian, self).__init__('debian', get_version_fn)

    def get_codename(self):
        if self.is_os():
            v = self.get_version().split('.', 1)[0]
            return {
                '7': 'wheezy',
                '8': 'jessie',
                '9': 'stretch',
                '10': 'buster',
                '11': 'bullseye',
                '12': 'bookworm',
                '13': 'trixie',
                '14': 'forky',
                '15': 'duke',
                'unstable': 'sid',
                'rodete': 'trixie',
            }.get(v, '')


class FdoDetect(OsDetector):
    """
    Generic detector for operating systems implementing /etc/os-release, as defined by the os-release spec hosted at Freedesktop.org (Fdo):
    http://www.freedesktop.org/software/systemd/man/os-release.html
    Requires that the "ID", and "VERSION_ID" keys are set in the os-release file.

    Codename is parsed from the VERSION key if available: either using the format "foo, CODENAME" or "foo (CODENAME)."
    If the VERSION key is not present, the VERSION_ID is value is used as the codename.
    """
    def __init__(self, fdo_id):
        release_info = read_os_release()
        if release_info is not None and "ID" in release_info and release_info["ID"] == fdo_id:
            self.release_info = release_info
        else:
            self.release_info = None

    def is_os(self):
        return self.release_info is not None and "VERSION_ID" in self.release_info

    def get_version(self):
        if self.is_os():
            return self.release_info["VERSION_ID"]
        raise OsNotDetected("called in incorrect OS")

    def get_codename(self):
        if self.is_os():
            if "VERSION" in self.release_info:
                version = self.release_info["VERSION"]
                # FDO style: works with Fedora, Debian, Suse.
                if '(' in version:
                    codename = version[version.find("(") + 1:version.find(")")]
                # Ubuntu style
                elif '"' in version:
                    codename = version[version.find(",") + 1:].lstrip(' ').split()[0]
                # Indeterminate style
                else:
                    codename = version
                return codename.lower()
            else:
                return self.get_version()
        raise OsNotDetected("called in incorrect OS")


class OpenEmbedded(OsDetector):
    """
    Detect OpenEmbedded.
    """
    def is_os(self):
        return "ROS_OS_OVERRIDE" in os.environ and os.environ["ROS_OS_OVERRIDE"] == "openembedded"

    def get_version(self):
        if self.is_os():
            return ""
        raise OsNotDetected('called in incorrect OS')

    def get_codename(self):
        if self.is_os():
            return ""
        raise OsNotDetected('called in incorrect OS')


class Conda(OsDetector):
    """
    Detect Conda.
    """
    def is_os(self):
        return "ROS_OS_OVERRIDE" in os.environ and \
            (os.environ["ROS_OS_OVERRIDE"].lower().startswith("robostack") or
             os.environ["ROS_OS_OVERRIDE"].lower().startswith("conda"))

    def get_version(self):
        if self.is_os():
            return ""
        raise OsNotDetected('called in incorrect OS')

    def get_codename(self):
        if self.is_os():
            return ""
        raise OsNotDetected('called in incorrect OS')


class OpenSuse(OsDetector):
    """
    Detect OpenSuse OS.
    """
    def __init__(self, brand_file="/etc/SuSE-brand", release_file="/etc/SuSE-release"):
        self._brand_file = brand_file
        self._release_file = release_file

    def is_os(self):
        os_list = read_issue(self._brand_file)
        return os_list and os_list[0] == "openSUSE"

    def get_version(self):
        if self.is_os() and os.path.exists(self._brand_file):
            with open(self._brand_file, 'r') as fh:
                os_list = fh.read().strip().split('\n')
                if len(os_list) == 2:
                    os_list = os_list[1].split(' = ')
                    if os_list[0] == "VERSION":
                        return os_list[1]
        raise OsNotDetected('cannot get version on this OS')

    def get_codename(self):
        # /etc/SuSE-release is deprecated since 13.1
        if self._release_file is None:
            return ""
        if self.is_os() and os.path.exists(self._release_file):
            with open(self._release_file, 'r') as fh:
                os_list = fh.read().strip().split('\n')
                for line in os_list:
                    kv = line.split(' = ')
                    if kv[0] == "CODENAME":
                        return kv[1]
        raise OsNotDetected('called in incorrect OS')


# Source: https://en.wikipedia.org/wiki/MacOS#Versions
_osx_codename_map = {
 '10.4': 'tiger',
 '10.5': 'leopard',
 '10.6': 'snow',
 '10.7': 'lion',
 '10.8': 'mountain lion',
 '10.9': 'mavericks',
 '10.10': 'yosemite',
 '10.11': 'el capitan',
 '10.12': 'sierra',
 '10.13': 'high sierra',
 '10.14': 'mojave',
 '10.15': 'catalina',
 '11': 'big sur',
 '12': 'monterey',
 '13': 'ventura',
 '14': 'sonoma',
 '15': 'sequoia',
 '26': 'tahoe',
}


def _osx_codename(major, minor):
    if major == 10:
        key = '%s.%s' % (major, minor)
    else:
        key = '%s' % (major)        
    if key not in _osx_codename_map:
         raise OsNotDetected("unrecognized version: %s" % key)
    return _osx_codename_map[key]


class OSX(OsDetector):
    """
    Detect OS X
    """
    def __init__(self, sw_vers_file="/usr/bin/sw_vers"):
        self._sw_vers_file = sw_vers_file

    def is_os(self):
        return os.path.exists(self._sw_vers_file)

    def get_codename(self):
        if self.is_os():
            version = self.get_version()
            import distutils.version  # To parse version numbers
            try:
                ver = distutils.version.StrictVersion(version).version
            except ValueError:
                raise OsNotDetected("invalid version string: %s" % (version))
            return _osx_codename(*ver[0:2])
        raise OsNotDetected('called in incorrect OS')

    def get_version(self):
        if self.is_os():
            return _read_stdout([self._sw_vers_file, '-productVersion'])
        raise OsNotDetected('called in incorrect OS')


class QNX(OsDetector):
    '''
    Detect QNX realtime OS.
    @author: Isaac Saito
    '''
    def __init__(self, uname_file='/bin/uname'):
        '''
        @param uname_file: An executable that can be used for detecting
                           OS name and version.
        '''
        self._os_name_qnx = 'QNX'
        self._uname_file = uname_file

    def is_os(self):
        if os.path.exists(self._uname_file):
            std_out = _read_stdout([self._uname_file])
            return std_out.strip() == self._os_name_qnx
        else:
            return False

    def get_codename(self):
        if self.is_os():
            return ''
        raise OsNotDetected('called in incorrect OS')

    def get_version(self):
        if self.is_os() and os.path.exists(self._uname_file):
            return _read_stdout([self._uname_file, "-r"])
        raise OsNotDetected('called in incorrect OS')


class Arch(OsDetector):
    """
    Detect Arch Linux.
    """
    def __init__(self, release_file='/etc/arch-release'):
        self._release_file = release_file

    def is_os(self):
        return os.path.exists(self._release_file)

    def get_version(self):
        if self.is_os():
            return ""
        raise OsNotDetected('called in incorrect OS')

    def get_codename(self):
        if self.is_os():
            return ""
        raise OsNotDetected('called in incorrect OS')


class Manjaro(Arch):
    """
    Detect Manjaro.
    """
    def __init__(self, release_file='/etc/manjaro-release'):
        super(Manjaro, self).__init__(release_file)


class Cygwin(OsDetector):
    """
    Detect Cygwin presence on Windows OS.
    """
    def is_os(self):
        return os.path.exists("/usr/bin/cygwin1.dll")

    def get_version(self):
        if self.is_os():
            return _read_stdout(['uname', '-r'])
        raise OsNotDetected('called in incorrect OS')

    def get_codename(self):
        if self.is_os():
            return ''
        raise OsNotDetected('called in incorrect OS')


class Gentoo(OsDetector):
    """
    Detect Gentoo OS.
    """
    def __init__(self, release_file="/etc/gentoo-release"):
        self._release_file = release_file

    def is_os(self):
        os_list = read_issue(self._release_file)
        return os_list and os_list[0] == "Gentoo" and os_list[1] == "Base"

    def get_version(self):
        if self.is_os():
            os_list = read_issue(self._release_file)
            return os_list[4]
        raise OsNotDetected('called in incorrect OS')

    def get_codename(self):
        if self.is_os():
            return ''
        raise OsNotDetected('called in incorrect OS')


class Funtoo(Gentoo):
    """
    Detect Funtoo OS, a Gentoo Variant.
    """
    def __init__(self, release_file="/etc/gentoo-release"):
        Gentoo.__init__(self, release_file)

    def is_os(self):
        os_list = read_issue(self._release_file)
        return os_list and os_list[0] == "Funtoo" and os_list[1] == "Linux"


class FreeBSD(OsDetector):
    """
    Detect FreeBSD OS.
    """
    def __init__(self, uname_file="/usr/bin/uname"):
        self._uname_file = uname_file

    def is_os(self):
        if os.path.exists(self._uname_file):
            std_out = _read_stdout([self._uname_file])
            return std_out.strip() == "FreeBSD"
        else:
            return False

    def get_version(self):
        if self.is_os() and os.path.exists(self._uname_file):
            return _read_stdout([self._uname_file, "-r"])
        raise OsNotDetected('called in incorrect OS')

    def get_codename(self):
        if self.is_os():
            return ''
        raise OsNotDetected('called in incorrect OS')


class Slackware(OsDetector):
    """
    Detect SlackWare Linux.
    """
    def __init__(self, release_file='/etc/slackware-version'):
        self._release_file = release_file

    def is_os(self):
        return os.path.exists(self._release_file)

    def get_version(self):
        if self.is_os():
            os_list = read_issue(self._release_file)
            return os_list[1]
        raise OsNotDetected('called in incorrect OS')

    def get_codename(self):
        if self.is_os():
            return ''
        raise OsNotDetected('called in incorrect OS')


class Windows(OsDetector):
    """
    Detect Windows OS.
    """
    def is_os(self):
        return platform.system() == "Windows"

    def get_version(self):
        if self.is_os():
            return platform.version()
        raise OsNotDetected('called in incorrect OS')

    def get_codename(self):
        if self.is_os():
            return platform.release()
        raise OsNotDetected('called in incorrect OS')


class OsDetect:
    """
    This class will iterate over registered classes to lookup the
    active OS and version
    """

    default_os_list = []

    def __init__(self, os_list=None):
        if os_list is None:
            os_list = OsDetect.default_os_list
        self._os_list = os_list
        self._os_name = None
        self._os_version = None
        self._os_codename = None
        self._os_detector = None
        self._override = False

    @staticmethod
    def register_default(os_name, os_detector):
        """
        Register detector to be used with all future instances of
        :class:`OsDetect`.  The new detector will have precedence over
        any previously registered detectors associated with *os_name*.

        :param os_name: OS key associated with OS detector
        :param os_detector: :class:`OsDetector` instance
        """
        OsDetect.default_os_list.insert(0, (os_name, os_detector))

    def detect_os(self, env=None):
        """
        Detect operating system.  Return value can be overridden by
        the :env:`ROS_OS_OVERRIDE` environment variable.

        :param env: override ``os.environ``
        :returns: (os_name, os_version, os_codename), ``(str, str, str)``
        :raises: :exc:`OsNotDetected` if OS could not be detected
        """
        if env is None:
            env = os.environ
        if 'ROS_OS_OVERRIDE' in env:
            splits = env["ROS_OS_OVERRIDE"].split(':')
            self._os_name = splits[0]
            if len(splits) > 1:
                self._os_version = splits[1]
                if len(splits) > 2:
                    self._os_codename = splits[2]
                else:
                    self._os_codename = ''
            else:
                self._os_version = self._os_codename = ''
            self._override = True
        else:
            for os_name, os_detector in self._os_list:
                if os_detector.is_os():
                    self._os_name = os_name
                    self._os_version = os_detector.get_version()
                    self._os_codename = os_detector.get_codename()
                    self._os_detector = os_detector
                    break

        if self._os_name:
            return self._os_name, self._os_version, self._os_codename
        else:  # No solution found
            attempted = [x[0] for x in self._os_list]
            raise OsNotDetected("Could not detect OS, tried %s" % attempted)

    def get_detector(self, name=None):
        """
        Get detector used for specified OS name, or the detector for this OS if name is ``None``.

        :raises: :exc:`KeyError`
        """
        if name is None:
            if not self._os_detector:
                self.detect_os()
            return self._os_detector
        else:
            try:
                return [d for d_name, d in self._os_list if d_name == name][0]
            except IndexError:
                raise KeyError(name)

    def add_detector(self, name, detector):
        """
        Add detector to list of detectors used by this instance.  *detector* will override any previous
        detectors associated with *name*.

        :param name: OS name that detector matches
        :param detector: :class:`OsDetector` instance
        """
        self._os_list.insert(0, (name, detector))

    def get_name(self):
        if not self._os_name:
            self.detect_os()
        return self._os_name

    def get_version(self):
        if not self._os_version:
            self.detect_os()
        return self._os_version

    def get_codename(self):
        if not self._os_codename:
            self.detect_os()
        return self._os_codename


OS_ALMALINUX = 'almalinux'
OS_ALPINE = 'alpine'
OS_AMAZON = 'amazon'
OS_ARCH = 'arch'
OS_BUILDROOT = 'buildroot'
OS_MANJARO = 'manjaro'
OS_CENTOS = 'centos'
OS_EULEROS = 'euleros'
OS_CYGWIN = 'cygwin'
OS_DEBIAN = 'debian'
OS_ELEMENTARY = 'elementary'
OS_ELEMENTARY_OLD = 'elementary'
OS_FEDORA = 'fedora'
OS_FEDORA_ASAHI = 'fedora-asahi'
OS_FREEBSD = 'freebsd'
OS_FUNTOO = 'funtoo'
OS_GENTOO = 'gentoo'
OS_LINARO = 'linaro'
OS_MINT = 'mint'
OS_MX = 'mx'
OS_NEON = 'neon'
OS_OPENEMBEDDED = 'openembedded'
OS_OPENSUSE = 'opensuse'
OS_OPENSUSE13 = 'opensuse'
OS_ORACLE = 'oracle'
OS_CONDA = 'conda'
OS_TIZEN = 'tizen'
OS_SAILFISHOS = 'sailfishos'
OS_OSX = 'osx'
OS_POP = 'pop'
OS_QNX = 'qnx'
OS_RASPBIAN = 'raspbian'
OS_RHEL = 'rhel'
OS_ROCKY = 'rocky'
OS_SLACKWARE = 'slackware'
OS_UBUNTU = 'ubuntu'
OS_CLEARLINUX = 'clearlinux'
OS_NIXOS = 'nixos'
OS_WINDOWS = 'windows'
OS_ZORIN =  'zorin'
OS_OPENEULER = 'openeuler'

OsDetect.register_default(OS_ALMALINUX, FdoDetect("almalinux"))
OsDetect.register_default(OS_ALPINE, FdoDetect("alpine"))
OsDetect.register_default(OS_AMAZON, FdoDetect("amzn"))
OsDetect.register_default(OS_ARCH, Arch())
OsDetect.register_default(OS_BUILDROOT, FdoDetect("buildroot"))
OsDetect.register_default(OS_MANJARO, Manjaro())
OsDetect.register_default(OS_CENTOS, FdoDetect("centos"))
OsDetect.register_default(OS_EULEROS, FdoDetect("euleros"))
OsDetect.register_default(OS_OPENEULER, FdoDetect("openeuler"))
OsDetect.register_default(OS_OPENEULER, FdoDetect("openEuler"))
OsDetect.register_default(OS_CYGWIN, Cygwin())
OsDetect.register_default(OS_DEBIAN, Debian())
OsDetect.register_default(OS_ELEMENTARY, LsbDetect("elementary"))
OsDetect.register_default(OS_ELEMENTARY_OLD, LsbDetect("elementary OS"))
OsDetect.register_default(OS_FEDORA, FdoDetect("fedora"))
OsDetect.register_default(OS_FEDORA_ASAHI, FdoDetect("fedora-asahi-remix"))
OsDetect.register_default(OS_FREEBSD, FreeBSD())
OsDetect.register_default(OS_FUNTOO, Funtoo())
OsDetect.register_default(OS_GENTOO, Gentoo())
OsDetect.register_default(OS_LINARO, LsbDetect("Linaro"))
OsDetect.register_default(OS_MINT, LsbDetect("LinuxMint"))
OsDetect.register_default(OS_MX, LsbDetect("MX"))
OsDetect.register_default(OS_NEON, LsbDetect("neon"))
OsDetect.register_default(OS_OPENEMBEDDED, OpenEmbedded())
OsDetect.register_default(OS_OPENSUSE, OpenSuse())
OsDetect.register_default(OS_OPENSUSE13, OpenSuse(brand_file='/etc/SUSE-brand', release_file=None))
OsDetect.register_default(OS_OPENSUSE, FdoDetect("opensuse-tumbleweed"))
OsDetect.register_default(OS_OPENSUSE, FdoDetect("opensuse-leap"))
OsDetect.register_default(OS_OPENSUSE, FdoDetect("opensuse"))
OsDetect.register_default(OS_ORACLE, FdoDetect("ol"))
OsDetect.register_default(OS_CONDA, Conda())
OsDetect.register_default(OS_TIZEN, FdoDetect("tizen"))
OsDetect.register_default(OS_SAILFISHOS, FdoDetect("sailfishos"))
OsDetect.register_default(OS_OSX, OSX())
OsDetect.register_default(OS_POP, LsbDetect("Pop"))
OsDetect.register_default(OS_QNX, QNX())
OsDetect.register_default(OS_RASPBIAN, FdoDetect("raspbian"))
OsDetect.register_default(OS_RHEL, FdoDetect("rhel"))
OsDetect.register_default(OS_ROCKY, FdoDetect("rocky"))
OsDetect.register_default(OS_SLACKWARE, Slackware())
OsDetect.register_default(OS_UBUNTU, LsbDetect("Ubuntu"))
OsDetect.register_default(OS_CLEARLINUX, FdoDetect("clear-linux-os"))
OsDetect.register_default(OS_NIXOS, FdoDetect("nixos"))
OsDetect.register_default(OS_WINDOWS, Windows())
OsDetect.register_default(OS_ZORIN, LsbDetect("Zorin"))


if __name__ == '__main__':
    detect = OsDetect()
    print("OS Name:     %s" % detect.get_name())
    print("OS Version:  %s" % detect.get_version())
    print("OS Codename: %s" % detect.get_codename())
