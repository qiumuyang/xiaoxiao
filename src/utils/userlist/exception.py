class UserListError(Exception):
    pass


class TooManyListsError(UserListError):
    pass


class TooManyItemsError(UserListError):
    pass


class ListPermissionError(UserListError):
    pass
