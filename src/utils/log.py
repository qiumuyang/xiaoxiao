from nonebot.utils import logger_wrapper as _logger_wrapper


class logger_wrapper:

    def __init__(self, logger_name: str) -> None:
        self._logger = _logger_wrapper(logger_name)

    def critical(self,
                 message: str,
                 exception: Exception | None = None) -> None:
        self._logger("CRITICAL", message, exception)

    def error(self, message: str, exception: Exception | None = None) -> None:
        self._logger("ERROR", message, exception)

    def warning(self,
                message: str,
                exception: Exception | None = None) -> None:
        self._logger("WARNING", message, exception)

    def success(self,
                message: str,
                exception: Exception | None = None) -> None:
        self._logger("SUCCESS", message, exception)

    def info(self, message: str, exception: Exception | None = None) -> None:
        self._logger("INFO", message, exception)

    def debug(self, message: str, exception: Exception | None = None) -> None:
        self._logger("DEBUG", message, exception)

    def trace(self, message: str, exception: Exception | None = None) -> None:
        self._logger("TRACE", message, exception)


debug_logger = logger_wrapper("Debug")
