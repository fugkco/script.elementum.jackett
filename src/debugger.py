# coding=utf-8

def load():
    from utils import get_setting

    if get_setting("enable_debugger", bool):
        from logger import log
        import pkgutil
        import re
        from os import path
        import sys

        additional_libraries = get_setting("debugger_additional_libraries")
        if additional_libraries != "":
            if not path.exists(additional_libraries):
                log.error("Debugger has been enabled but additional libraries directory, skipping loading of debugger")
                return
            sys.path.append(additional_libraries)

        if pkgutil.find_loader("pydevd_pycharm") is None:
            log.error("Debugger currently only supports IntelliJ IDEA and derivatives. If you need additional ")
            return

        host = get_setting("debugger_host")
        valid_host_regex = re.compile(r'''
                    ^
                      (?:
                        (?:(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]))
                      |
                        (?:(?:(?:[a-zA-Z]|[a-zA-Z][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)+(?:[A-Za-z|[A-Za-z][A-Za-z0-9\‌-]*[A-Za-z0-9]))
                      )
                    $
        ''', re.VERBOSE)
        if not valid_host_regex.match(host):
            log.error("debugger: invalid host detected.. Skipping")
            return False

        try:
            port = get_setting("debugger_port", int)
        except ValueError:
            log.exception("debugger: invalid port detected")
            return

        if not (0 < int(port) <= 65535):
            log.exception("debugger: port must be between 0 and 65535")
            return

        import pydevd_pycharm
        pydevd_pycharm.settrace(host, port=port, stdoutToServer=True, stderrToServer=True)
        log.info("pycharm debugger successfully loaded")
