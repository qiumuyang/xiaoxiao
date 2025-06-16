import os
from pathlib import Path
from typing import Any, get_args, get_origin

import dotenv
from watchdog.events import (DirModifiedEvent, FileModifiedEvent,
                             FileSystemEventHandler)
from watchdog.observers import Observer

from .log import logger_wrapper


def _construct_parser(type):
    if get_origin(type) is list:
        vt = get_args(type)[0]
        return lambda v: [vt(_) for _ in v.split(",")]
    if get_origin(type) is dict:
        kt, vt = get_args(type)
        return lambda v: {
            kt(k): vt(v)
            for k, v in (pair.split(":") for pair in v.split(","))
        }
    return type


def set_class_var_by_env(cls) -> dict[str, Any]:
    injected = {}
    for key, value_type in cls.__annotations__.items():
        if key.startswith("_"):
            continue
        env_value = os.getenv(key.upper(), None)
        if env_value is None:
            # check if value is set
            # if not, set None
            if not hasattr(cls, key):
                setattr(cls, key, None)
                injected[key] = None
            continue
        value_type = _construct_parser(value_type)
        setattr(
            cls, key,
            value_type(env_value)
            if value_type is not bool else env_value.lower() in {"true", "1"})
        injected[key] = getattr(cls, key)
    return injected


class EnvFileWatcher(FileSystemEventHandler):

    def __init__(self):
        self.logger = logger_wrapper("env")
        self.injected_cls = set()
        if os.getenv("ENVIRONMENT") == "dev":
            self.env_file = Path(".env.dev")
        else:
            self.env_file = Path(".env.prod")
        dotenv.load_dotenv(self.env_file)

        self.history = {}

    def register(self, cls):
        self.injected_cls.add(cls)
        updated = set_class_var_by_env(cls)
        self.history.update(updated)

    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent):
        if isinstance(event, DirModifiedEvent):
            return
        if isinstance(event.src_path, bytes):
            src_path = Path(event.src_path.decode())
        elif isinstance(event.src_path, str):
            src_path = Path(event.src_path)
        else:
            raise TypeError(f"Unknown type {type(event.src_path)}")
        if src_path.name == self.env_file.name:
            dotenv.load_dotenv(self.env_file, override=True)
            new_inject = {}
            for cls in self.injected_cls:
                updated = set_class_var_by_env(cls)
                new_inject.update(updated)
            diff = {}
            for key, value in new_inject.items():
                prev_value = self.history.get(key, None)
                if prev_value != value:
                    diff[key] = (prev_value, value)
            if not diff:
                return
            self.history = new_inject
            self.logger.info(f"Update from {src_path.name}: \n" +
                             ("\n".join(f"{k}: {v[0]} -> {v[1]}"
                                        for k, v in diff.items())))


watcher = EnvFileWatcher()
observer = Observer()
observer.schedule(watcher, path=".", recursive=False)
observer.start()


def inject_env():

    def decorator(cls):
        watcher.register(cls)
        return cls

    return decorator


if __name__ == "__main__":

    @inject_env()
    class Config:
        host: str = "localhost"
        ports: dict[int, int]
        names: list[str]
        RECENT_MIN_INTERVAL_MUTE: int

    while 1:
        print(Config.host, Config.ports, Config.names,
              Config.RECENT_MIN_INTERVAL_MUTE)
        from time import sleep
        sleep(3)
