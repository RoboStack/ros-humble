# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

class BinstarError(Exception):

    def __init__(self, *args):
        super().__init__(*args)

        if not hasattr(self, 'message'):
            try:
                self.message = str(args[0])
            except IndexError:
                self.message = None


class Unauthorized(BinstarError):
    pass


class Conflict(BinstarError):
    pass


class NotFound(BinstarError, IndexError):

    def __init__(self, *args):
        super().__init__(*args)
        self.msg = self.message


class UserError(BinstarError):
    pass


class ServerError(BinstarError):
    pass


class ShowHelp(BinstarError):
    pass


class NoMetadataError(BinstarError):
    pass


class DestinationPathExists(BinstarError):

    def __init__(self, location):
        self.msg = "destination path '{}' already exists.".format(location)
        self.location = location
        super().__init__(self.msg)


class PillowNotInstalled(BinstarError):

    def __init__(self):
        self.msg = 'pillow is not installed. Install it with:\n\tconda install pillow'
        super().__init__(self.msg)
