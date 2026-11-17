# Running the registry as a service on Windows

`systemd/ard-registry.service` is the reference deployment on Linux. Windows
has no equivalent built in, so there are three lanes here, in the order worth
trying them: foreground (prove it works), Task Scheduler (no dependencies),
NSSM (restarts on crash).

**If the catalog lives in WSL, decide first where the registry should run.**
A registry started inside WSL under the systemd unit needs no Windows service
at all — Windows reaches it on `127.0.0.1:<port>` through WSL's localhost
forwarding, and that is the deployment the station itself uses. Install a
Windows service only when the registry has to survive without the distro
running, or when the catalog is a Windows file.

All three lanes share the same four facts:

- **Interpreter:** `python`, not `python3`. If `python` opens the Microsoft
  Store it is a stub; use the real path (`C:\Python314\python.exe`). A pip/pipx
  install removes the question — `ard-registry.exe` is on PATH and needs
  neither `PYTHONPATH` nor a working directory.
- **Module form needs a working directory.** `python -m ard_kit.registry`
  imports `ard_kit` from the cwd or from `PYTHONPATH`, so point one of them at
  the plugin/checkout root. Task Scheduler sets neither from `schtasks`; use
  the XML `<WorkingDirectory>` or a `.cmd` wrapper.
- **Catalog path:** Windows-visible. A POSIX path resolves against the current
  drive instead of failing (`C:\Program Files\Git\home\...`), so pass
  `D:\work\ai-catalog.json`, or `\\wsl.localhost\<distro>\home\...\catalog.json`
  for a file that stays in WSL (readable, but slower per request, and dead
  while the distro is down — copy it out for a service).
- **Token:** environment only, never argv — the command line is world-readable
  in the process list. A loopback registry may run without one; anything
  reachable off-box should not.

## 1. Foreground — the lane that proves the others

```bat
cd /d C:\path\to\ard-kit
set PYTHONPATH=%CD%
python -m ard_kit.registry --catalog D:\work\ai-catalog.json --host 127.0.0.1 --port 8390
```

Git Bash, same thing:

```bash
cd "/c/path/to/ard-kit" && PYTHONPATH="$PWD" python -m ard_kit.registry \
  --catalog "D:/work/ai-catalog.json" --host 127.0.0.1 --port 8390
```

The registry does not daemonize: this console *is* the service, and Ctrl-C
stops it. Check it from a second shell before scheduling anything —
`curl -s http://127.0.0.1:8390/health` (no token needed), then the preflight
against the same URL:

```bat
python -m ard_kit.doctor --catalog D:\work\ai-catalog.json --url http://127.0.0.1:8390
```

Port already taken: `netstat -ano | findstr :8390`, last column is the PID.

## 2. Task Scheduler — no third-party dependency

Wrap the foreground form in `ard-registry-run.cmd` next to the checkout, so
the working directory, `PYTHONPATH` and log redirection all live in one file
the task can point at:

```bat
@echo off
cd /d C:\path\to\ard-kit
set PYTHONPATH=%CD%
python -m ard_kit.registry --catalog D:\work\ai-catalog.json --host 127.0.0.1 --port 8390 >> D:\work\ard-registry.log 2>&1
```

Register it at logon:

```bat
schtasks /Create /TN ard-registry /SC ONLOGON /RL LIMITED ^
  /TR "C:\path\to\ard-registry-run.cmd"
schtasks /Run /TN ard-registry      & rem start it now, without a re-login
schtasks /Query /TN ard-registry /V /FO LIST
```

For restart-on-failure and a non-interactive principal, import XML instead
(`schtasks /Create /TN ard-registry /XML ard-registry.xml`):

```xml
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>ARD registry - local resource catalog for agent discovery</Description>
  </RegistrationInfo>
  <Triggers><LogonTrigger><Enabled>true</Enabled></LogonTrigger></Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <StartWhenAvailable>true</StartWhenAvailable>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <RestartOnFailure><Interval>PT10S</Interval><Count>3</Count></RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>C:\path\to\ard-registry-run.cmd</Command>
      <WorkingDirectory>C:\path\to\ard-kit</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
```

Two settings matter and both are wrong by default. `ExecutionTimeLimit` is 72
hours unless set, which stops a healthy long-running registry on the third
day — `PT0S` means no limit. And `RestartOnFailure` fires when the task
*exits* non-zero; Task Scheduler does not watch a running process, so a
registry killed by an exception is restarted, one that hangs is not. Hang
coverage is what NSSM is for.

## 3. NSSM — a real service, with supervision

[NSSM](https://nssm.cc) runs the same command as a Windows service and
restarts it on exit or hang:

```bat
nssm install ard-registry C:\Python314\python.exe "-m ard_kit.registry --catalog D:\work\ai-catalog.json --host 127.0.0.1 --port 8390"
nssm set ard-registry AppDirectory C:\path\to\ard-kit
nssm set ard-registry AppEnvironmentExtra PYTHONPATH=C:\path\to\ard-kit
nssm set ard-registry AppStdout D:\work\ard-registry.log
nssm set ard-registry AppStderr D:\work\ard-registry.err.log
nssm set ard-registry AppRestartDelay 10000
nssm start ard-registry
```

Add the token the same way (`AppEnvironmentExtra` takes more than one line)
rather than in `Arguments`. It is stored in the service's registry key —
readable by administrators, exactly like a systemd unit file, and no worse
than argv, which is readable by every local user.

`nssm remove ard-registry confirm` undoes it.

## After any of the three

```bat
curl -s http://127.0.0.1:8390/health
python -m ard_kit.doctor --catalog D:\work\ai-catalog.json --url http://127.0.0.1:8390
```

`/health` answers without a token and reports `version`, `auth`, `entries` and
`catalogGeneratedAt`, which separates "the service is down" from "the service
is up and serving the wrong catalog" — the second one is the failure that
otherwise costs an afternoon. `ard-doctor` then walks the whole chain and
exits 0 only when a real search against that catalog returns rows.
