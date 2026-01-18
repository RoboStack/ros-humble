# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

from binstar_client.utils import jencode


class OrgMixin:

    def user_orgs(self, username=None):

        if username:
            url = '%s/users/%s/orgs' % (self.domain, username)
        else:
            url = '%s/user/orgs' % (self.domain)

        res = self.session.get(url)
        self._check_response(res)

        return res.json()

    def groups(self, owner=None):
        if owner:
            url = '%s/groups/%s' % (self.domain, owner)
        else:
            url = '%s/groups' % (self.domain,)

        res = self.session.get(url)
        self._check_response(res)

        return res.json()

    def group(self, owner, group_name):
        url = '%s/group/%s/%s' % (self.domain, owner, group_name)
        res = self.session.get(url)
        self._check_response(res)
        return res.json()

    def group_members(self, org, name):
        url = '%s/group/%s/%s/members' % (self.domain, org, name)
        res = self.session.get(url)
        self._check_response(res)

        return res.json()

    def is_group_member(self, org, name, member):
        url = '%s/group/%s/%s/members/%s' % (self.domain, org, name, member)
        res = self.session.get(url)
        self._check_response(res, [204, 404])
        return res.status_code == 204

    def add_group_member(self, org, name, member):
        url = '%s/group/%s/%s/members/%s' % (self.domain, org, name, member)
        res = self.session.put(url)
        self._check_response(res, [204])

    def remove_group_member(self, org, name, member):
        url = '%s/group/%s/%s/members/%s' % (self.domain, org, name, member)
        res = self.session.delete(url)
        self._check_response(res, [204])

    def remove_group_package(self, org, name, package):
        url = '%s/group/%s/%s/packages/%s' % (self.domain, org, name, package)
        res = self.session.delete(url)
        self._check_response(res, [204])

    def group_packages(self, org, name):
        url = '%s/group/%s/%s/packages' % (self.domain, org, name)
        res = self.session.get(url)
        self._check_response(res, [200])
        return res.json()

    def add_group_package(self, org, name, package):
        url = '%s/group/%s/%s/packages/%s' % (self.domain, org, name, package)
        res = self.session.put(url)
        self._check_response(res, [204])

    def add_group(self, org, name, perms='read'):
        url = '%s/group/%s/%s' % (self.domain, org, name)

        payload = {'perms': perms}
        data, headers = jencode(payload)

        res = self.session.post(url, data=data, headers=headers)
        self._check_response(res, [204])
