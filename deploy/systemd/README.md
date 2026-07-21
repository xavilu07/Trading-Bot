# QIC systemd templates

These templates target the current VPS layout at `/root/bot`. They run only QIC offline/DEV workloads and never start or restart the trading scheduler.

Use `scripts/install_qic_services.sh` to copy units without enabling or starting them. Pass `--enable` only after review. Review `Planning/qic-autonomous-operations.md` before starting any unit.

Validate on Linux:

```bash
systemd-analyze verify deploy/systemd/qic-*.service deploy/systemd/qic-*.timer
```
