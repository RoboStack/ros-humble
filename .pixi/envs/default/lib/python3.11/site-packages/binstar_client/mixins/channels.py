# pylint: disable=missing-class-docstring

"""
Created on May 2, 2014

@author: sean
"""

from binstar_client.utils import jencode


class ChannelsMixin:

    def list_channels(self, owner):
        """
        List the channels for owner.

        If owner is none, the currently logged in user is used.
        """
        url = '%s/channels/%s' % (self.domain, owner)

        res = self.session.get(url)
        self._check_response(res, [200])
        return res.json()

    def show_channel(self, channel, owner):
        """
        List the channels for owner.

        If owner is none, the currently logged in user is used.
        """
        url = '%s/channels/%s/%s' % (self.domain, owner, channel)

        res = self.session.get(url)
        self._check_response(res, [200])
        return res.json()

    def add_channel(  # pylint: disable=too-many-arguments
            self, channel, owner, package=None, version=None, filename=None):
        """
        Add a channel to the specified files

        :param channel: channel to add
        :param owner: The user to add the channel to (all files of all packages for this user)
        :param package: The package to add the channel to (all files in this package)
        :param version: The version to add the channel to (all files in this version of the package)
        :param filename: The exact file to add the channel to
        """
        url = '%s/channels/%s/%s' % (self.domain, owner, channel)
        data, headers = jencode(package=package, version=version, basename=filename)

        res = self.session.post(url, data=data, headers=headers)
        self._check_response(res, [201])

    def remove_channel(  # pylint: disable=too-many-arguments
            self, channel, owner, package=None, version=None, filename=None):
        """
        Remove a channel from the specified files.

        :param channel: channel to remove
        :param owner: The user to remove the channel from (all files of all packages for this user)
        :param package: The package to remove the channel from (all files in this package)
        :param version: The version to remove the channel to (all files in this version of the package)
        :param filename: The exact file to remove the channel from
        """
        url = '%s/channels/%s/%s' % (self.domain, owner, channel)
        data, headers = jencode(package=package, version=version, basename=filename)

        res = self.session.delete(url, data=data, headers=headers)
        self._check_response(res, [201])

    def copy_channel(self, channel, owner, to_channel):
        """
        Tag all files in channel <channel> also as channel <to_channel>.

        :param channel: channel to copy
        :param owner: Perform this operation on all packages of this user
        :param to_channel: Destination name (may be a channel that already exists)
        """
        url = '%s/channels/%s/%s/copy/%s' % (self.domain, owner, channel, to_channel)
        res = self.session.post(url)
        self._check_response(res, [201])

    def lock_channel(self, channel, owner):
        """
        Tag all files in channel <channel> also as channel <to_channel>.

        :param channel: channel to copy
        :param owner: Perform this operation on all packages of this user
        :param to_channel: Destination name (may be a channel that already exists)
        """
        url = '%s/channels/%s/%s/lock' % (self.domain, owner, channel)
        res = self.session.post(url)
        self._check_response(res, [201])

    def unlock_channel(self, channel, owner):
        """
        Tag all files in channel <channel> also as channel <to_channel>.

        :param channel: channel to copy
        :param owner: Perform this operation on all packages of this user
        :param to_channel: Destination name (may be a channel that already exists)
        """
        url = '%s/channels/%s/%s/lock' % (self.domain, owner, channel)
        res = self.session.delete(url)
        self._check_response(res, [201])
