class ChoiceError(Exception):

    def __str__(self) -> str:
        return self.args[0]


class ListNotExistsError(ChoiceError):

    def __init__(self, name: str):
        super().__init__(f"列表 [{name}] 不存在")


class ListExistsError(ChoiceError):

    def __init__(self, name: str):
        super().__init__(f"列表 [{name}] 已存在")


class NonPlainTextError(ChoiceError):

    def __init__(self, where: str):
        super().__init__(f"{where}仅允许包含文本")


class InvalidIndexError(ChoiceError):

    def __init__(self, index: str = "", name: str = "索引"):
        super().__init__(f"无效的{name}: {index}")


class InvalidListNameError(ChoiceError):

    def __init__(self, reason: str):
        super().__init__(reason)


class InvalidItemOpError(ChoiceError):

    def __init__(self):
        super().__init__("列表项目仅可使用增删操作")
