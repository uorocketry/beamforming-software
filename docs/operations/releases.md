# Releases

GitHub Releases publish the Raspberry Pi 5 deployment bundle. STM32 firmware is not
pre-addressed or attached because every physical receiver board needs an explicitly chosen,
unique CAN node ID.

## Create a release

1. Update the package version in `pi/pyproject.toml`.
2. Regenerate the lockfile:

   ```bash
   .tools/bin/uv lock --project pi
   ```

3. Run the local gate:

   ```bash
   make check
   ```

4. Commit the release changes and push a matching tag. For version `0.1.0`:

   ```bash
   git tag -a v0.1.0 -m "BeamControl v0.1.0"
   git push origin v0.1.0
   ```

The release workflow verifies that the tag matches the package version, runs the full test and
representative firmware-build gate, builds the ARM64 Pi bundle, smoke-tests its offline
installation, creates a checksum, and publishes the GitHub Release.

## Release contents

A tagged release contains:

- `beamcontrol-pi-<revision>.tar.gz`
- `beamcontrol-pi-SHA256SUMS.txt`

Build STM32 firmware separately for each board:

```bash
make firmware NODE=<1..30>
```

Do not flash two boards with the same node ID on the same CAN bus.

## CI artifacts

Every push and pull request builds and smoke-tests the Pi bundle on an ARM64 GitHub runner.
That temporary artifact is useful for testing a branch. Tagged GitHub Releases are the stable
deployment source.

GitHub CI cannot test physical CAN wiring, MCP2515 hardware, device-tree overlays, or systemd
startup on the flight Pi. Complete those checks using the
[Pi deployment guide](pi-provisioning.md#verify-the-installation).
