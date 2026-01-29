# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

from urllib.parse import parse_qsl

from binstar_client.errors import UserError


class PackageSpec:
    def __init__(   # pylint: disable=too-many-arguments
            self,
            user,
            package=None,
            version=None,
            basename=None,
            attrs=None,
            spec_str=None
    ):

        self._user = user
        self._package = package
        self._version = version
        self._basename = basename
        self.attrs = attrs
        if spec_str:
            self.spec_str = spec_str
        else:
            spec_str = str(user)
            if package:
                spec_str = f'{spec_str}/{package}'
            if version:
                spec_str = f'{spec_str}/{version}'
            if basename:
                spec_str = f'{spec_str}/{basename}'
            self.spec_str = spec_str

    def __str__(self):
        return self.spec_str

    def __repr__(self):
        return f'<PackageSpec {self.spec_str!r}>'

    @property
    def user(self):
        if self._user is None:
            raise UserError(f'user not given (got {self.spec_str!r} expected <username>)')
        return self._user

    @property
    def name(self):
        if self._package is None:
            raise UserError(f'package not given in spec (got {self.spec_str!r} expected <username>/<package>)')
        return self._package

    @property
    def package(self):
        if self._package is None:
            raise UserError(f'package not given in spec (got {self.spec_str!r} expected <username>/<package>)')
        return self._package

    @property
    def version(self):
        if self._version is None:
            raise UserError(
                f'version not given in spec (got {self.spec_str!r} expected <username>/<package>/<version>)'
            )
        return self._version

    @property
    def basename(self):
        if self._basename is None:
            raise UserError(
                f'basename not given in spec (got {self.spec_str!r} expected <username>/<package>/<version>/<filename>)'
            )
        return self._basename


def package_specs(spec):
    user = spec
    package = None
    attrs = {}
    if '/' in user:
        user, package = user.split('/', 1)
    if '/' in package:
        raise TypeError('invalid package spec')

    return PackageSpec(user, package, None, None, attrs, spec)


def parse_specs(spec):
    user = spec
    package = version = basename = None
    attrs = {}
    if '/' in user:
        user, package = user.split('/', 1)
    if package and '/' in package:
        package, version = package.split('/', 1)

    if version and '/' in version:
        version, basename = version.split('/', 1)

    if basename and '?' in basename:
        basename, qsl = basename.rsplit('?', 1)
        attrs = dict(parse_qsl(qsl))

    return PackageSpec(user, package, version, basename, attrs, spec)


class GroupSpec:
    def __init__(self, org, group_name=None, member=None, spec_str=None):
        self._org = org
        self._group_name = group_name
        self._member = member

        if not spec_str:
            spec_str = str(org)
            if group_name:
                spec_str = f'{spec_str}/{group_name}'
            if member:
                spec_str = f'{spec_str}/{member}'
        self.spec_str = spec_str

    def __str__(self):
        return self.spec_str

    def __repr__(self):
        return f'<GroupSpec {self.spec_str!r}>'

    @property
    def org(self):
        if self._org is None:
            raise UserError(f'Organization not given (got {self.spec_str!r} expected <organization>)')
        return self._org

    @property
    def group_name(self):
        if self._group_name is None:
            raise UserError(f'Group name not given (got {self.spec_str!r} expected <organization>/<group_name>)')
        return self._group_name

    @property
    def member(self):
        if self._member is None:
            raise UserError(
                f'Member name not given (got {self.spec_str!r} expected <organization>/<group_name>/<member>)'
            )
        return self._member


def group_spec(spec):
    """<organization>/<group_name>/<member>"""
    org = spec
    group = member = None
    if '/' in org:
        org, group = org.split('/', 1)
    if group and '/' in group:
        group, member = group.split('/', 1)
    if member and '/' in member:
        raise UserError(f'Invalid group specification "{member}" (unexpected "/")')

    return GroupSpec(org, group, member, spec)
