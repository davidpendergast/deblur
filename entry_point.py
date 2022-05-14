
try:
    import pyi_splash  # special pyinstaller thing - import will not resolve in dev
    pyi_splash.close()
except Exception:
    pass  # this is expected to throw an exception in non-splash launch contexts.

import ui

ui.launch_app()