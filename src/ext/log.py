from nonebot.utils import logger_wrapper as logger_wrapper_nb


class logger_wrapper:

    def __init__(self, logger_name: str) -> None:
        self.logger = logger_wrapper_nb(logger_name)

    def error(self, message: str, exception: Exception | None = None) -> None:
        self.logger("ERROR", message, exception)

    def warning(self,
                message: str,
                exception: Exception | None = None) -> None:
        self.logger("WARNING", message, exception)

    def info(self, message: str, exception: Exception | None = None) -> None:
        self.logger("INFO", message, exception)

    def debug(self, message: str, exception: Exception | None = None) -> None:
        self.logger("DEBUG", message, exception)
