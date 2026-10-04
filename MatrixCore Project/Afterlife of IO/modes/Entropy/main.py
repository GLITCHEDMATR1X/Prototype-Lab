from __future__ import annotations

import sys


def _dependency_message() -> str:
    return (
        "Entropy requires pygame-ce 2.5.x.\n"
        "Install the source dependency with:\n"
        "    python -m pip install -r requirements.txt\n"
        "Packaged itch builds should bundle this runtime through the external launcher."
    )


try:
    from space_core import main
except ModuleNotFoundError as exc:
    if exc.name == "pygame":
        print(_dependency_message(), file=sys.stderr)
        raise SystemExit(2) from None
    raise


if __name__ == "__main__":
    raise SystemExit(main())
