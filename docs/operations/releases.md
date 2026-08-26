# Releases

Tagged releases publish the ARM64 Raspberry Pi bundle. STM32 images are built separately because each board needs a unique CAN node ID.

## Create

1. Update `pi/pyproject.toml`.
2. Run:

   ```bash
   .tools/bin/uv lock --project pi
   make check
   ```

3. Commit and push a matching tag:

   ```bash
   git tag -a v0.1.0 -m "BeamControl v0.1.0"
   git push origin v0.1.0
   ```

The workflow verifies the version, runs checks, builds and offline-smoke-tests the Pi bundle, creates checksums, and publishes the release.

## Contents

- `beamcontrol-pi-<revision>.tar.gz` — offline ARM64 bundle containing pinned `uv`, uv-managed CPython 3.11, wheelhouse, installer, configuration, and systemd units
- `beamcontrol-pi-SHA256SUMS.txt`

Build board firmware explicitly:

```bash
make firmware NODE=<1..30>
```

## CI artifacts

Every push/PR produces a temporary ARM64 bundle for branch testing. Use tagged releases for deployment.

CI does not test physical CAN, MCP2515 overlays, systemd on the flight Pi, or RF hardware. See [Pi verification](pi-provisioning.md#verify).
