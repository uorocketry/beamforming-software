"""beamctl: operator and diagnostic CLI for the BeamControl CAN controller."""

from __future__ import annotations

import argparse
import sys

from .client import BeamControlClient, BeamControlError
from .transport import SocketCanTransport


def _client(args: argparse.Namespace) -> BeamControlClient:
    return BeamControlClient(
        SocketCanTransport(args.iface),
        source_node=args.source,
        timeout=args.timeout,
        retries=args.retries,
    )


def _add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--iface", default="can0", help="CAN interface (default can0)")
    p.add_argument("--source", type=int, default=0, help="controller node id (default 0)")
    p.add_argument("--timeout", type=float, default=0.02, help="response timeout (s)")
    p.add_argument("--retries", type=int, default=2, help="retries per command")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="beamctl", description="uORocketry BeamControl CAN controller CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser(
        "discover", help="scan receiver-board nodes 1-30 for presence + protocol info"
    )
    _add_common_args(p)

    p = sub.add_parser("ping", help="query one receiver board")
    p.add_argument("node", type=int, help="receiver-board CAN node 1-30")
    _add_common_args(p)

    p = sub.add_parser("set-phase", help="set one receiver-board RF channel phase")
    p.add_argument("node", type=int, help="receiver-board CAN node 1-30")
    p.add_argument("--channel", type=int, required=True, help="RF channel 0-3")
    p.add_argument("--state", type=int, required=True, help="phase state 0-255")
    _add_common_args(p)

    p = sub.add_parser("set-vga", help="set receiver-board DVGA attenuation (dB)")
    p.add_argument("node", type=int, help="receiver-board CAN node 1-30")
    p.add_argument("--attenuation", type=int, required=True, help="dB 0-23")
    _add_common_args(p)

    p = sub.add_parser("enter-safe", help="enter safe state on one RF channel")
    p.add_argument("node", type=int, help="receiver-board CAN node 1-30")
    p.add_argument("--channel", type=int, required=True, help="RF channel 0-3")
    _add_common_args(p)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    c = _client(args)
    try:
        if args.command == "discover":
            for node in range(1, 31):
                try:
                    _, info = c.discover(node)
                    if info is not None:
                        print(
                            f"node {node:2d}: v{info.major}.{info.minor}.{info.patch} "
                            f"flags=0x{info.feature_flags:04x} node_id={info.node_id}"
                        )
                    else:
                        print(f"node {node:2d}: legacy v1.0")
                except BeamControlError:
                    pass
        elif args.command == "ping":
            _, info = c.discover(args.node)
            print("PROTOCOL_INFO:", info)
        elif args.command == "set-phase":
            print("ACK", c.set_phase(args.node, args.state, args.channel).hex())
        elif args.command == "set-vga":
            print("ACK", c.set_vga(args.node, args.attenuation).hex())
        elif args.command == "enter-safe":
            print("ACK", c.enter_safe(args.node, args.channel).hex())
        return 0
    except BeamControlError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
