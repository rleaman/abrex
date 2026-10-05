# Start here for Codex

This is the active navigation entry point. The superseded bootstrap handoff is
[archived](docs/archive/planning/START_HERE_FOR_CODEX.md).

1. Read [AGENTS.md](AGENTS.md) for permanent engineering and delivery rules.
2. Read [current work](docs/CURRENT_WORK.md) for active scope and verified progress.
3. Follow the [campaign work order](docs/experiment-campaign-2026-10.md), reading
   specific code, contracts and evidence only as needed.
4. Complete the authorized outcome through verification and usable delivery.
   Keep current work updated; historical task boundaries are not stopping points.

For runtime work use [baseline prerequisites](docs/baseline-runtimes.md) and
[Linux server provisioning](docs/linux-server-runtimes.md). Historical WSL paths
are not defaults for another host.

Run the repository fast gate with the existing Windows environment:

```powershell
.\env313\Scripts\python.exe scripts/quality_gate.py --python .\env313\Scripts\python.exe
```

[Archived plans](docs/archive/README.md) and numbered task records explain past
work. They do not override the user's current request, AGENTS.md, or the active
campaign. Read results as evidence, never as permission to restart an old task.
