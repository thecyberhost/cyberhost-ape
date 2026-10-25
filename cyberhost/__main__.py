"""Entry point.

No arguments  → launch the interactive console (primary UX).
With arguments → run a single command and exit (scripting / CI mode), e.g.
    python -m cyberhost install mobsf
    python -m cyberhost list core
"""

from __future__ import annotations

import sys

from .banner import err
from .context import Session


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        from .shell import run_shell
        return run_shell()

    # One-off mode: join argv into a single command line and dispatch once.
    from .commands import dispatch
    session = Session()
    rc = dispatch(session, " ".join(argv))
    return 0 if rc == -1 else rc


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        err("interrupted")
        sys.exit(130)
