"""beamd: CAN health monitor and read-only web dashboard."""

from __future__ import annotations

import argparse
import logging
import sys

import uvicorn

from .config import BeamControlConfig
from .monitor import BeamControlMonitor
from .web.server import create_app


def run(config_path: str) -> int:
    cfg = BeamControlConfig.from_file(config_path)
    # python-can logs every failed SocketCAN open. The monitor records state
    # transitions itself, so suppress repeated library messages in journald.
    logging.getLogger("can").setLevel(logging.CRITICAL)
    monitor = BeamControlMonitor(cfg)
    app = create_app(monitor)
    uvicorn.run(
        app,
        host=cfg.web_host,
        port=cfg.web_port,
        log_level="info",
        access_log=False,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="beamd", description="BeamControl CAN monitor and web dashboard"
    )
    parser.add_argument("--config", required=True, help="path to beamcontrol.toml")
    args = parser.parse_args(argv)
    try:
        return run(args.config)
    except Exception as error:  # noqa: BLE001
        print(f"beamd: fatal: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
