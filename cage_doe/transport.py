"""Where ``ntopcl`` runs: on this machine, or on another Windows PC over SSH.

    ############################################################################
    #  UNTESTED CODE.  Written by a cloud session that could not reach either  #
    #  machine.  It encodes the recipes the user verified by hand (see         #
    #  HANDOFF.md section 3) but not one line of it has executed against a     #
    #  real remote host.  Treat it as a starting point, verify every step,     #
    #  and expect to fix things.  In particular: quoting of the space in the   #
    #  login name, whether ``scp -O`` reaches paths containing spaces, and     #
    #  whether an SSH session surviving a 2-minute ntopcl run is reliable.     #
    ############################################################################

The SSH transport follows the verified recipes of the user's connection guide:

* ``ssh <alias> <command>`` - the remote default shell is ``cmd.exe``;
* ``scp -O`` (legacy protocol) for file transfer, the remote SFTP subsystem is broken;
* an SSH config host alias (``Host remote-ntop``) so the login name with a space
  never has to be quoted;
* a remote working folder **without spaces** (``C:/ntop_sweep``) for everything
  that scp touches; notebooks that live in a folder with spaces are copied
  remote-to-remote with ``cmd /c copy`` (no scp involved);
* PowerShell on the remote only via its full path and ``-EncodedCommand``.

Every ``ntopcl`` call is one short synchronous SSH session (a run takes about
1-3 minutes), so nothing depends on a long-lived connection surviving.
"""
from __future__ import annotations

import base64
import logging
import os
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

log = logging.getLogger(__name__)

# ntopcl exit codes as observed with nTop Automate 5.49 / 5.50
NTOPCL_EXIT_CODES = {
    0: "ok",
    1: "argument error (flags or paths)",
    2: "unsupported input type in the JSON",
    72: "build error (geometry or simulation failed)",
    81: "JSON parse error",
}
# codes that mean the *campaign* is misconfigured, not that the *design* is infeasible
CONFIG_ERROR_CODES = {1, 2, 81}

REMOTE_POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"


@dataclass
class ExecResult:
    returncode: int
    stdout: str
    stderr: str
    command: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def describe_exit(code: int) -> str:
    return NTOPCL_EXIT_CODES.get(code, f"exit code {code}")


def _win(p: str | PureWindowsPath) -> str:
    """Backslash form for cmd.exe."""
    return str(PureWindowsPath(str(p)))


def _fwd(p: str | PureWindowsPath) -> str:
    """Forward-slash form for scp destinations."""
    return str(PureWindowsPath(str(p))).replace("\\", "/")


# --------------------------------------------------------------------------- #
class LocalTransport:
    """ntopcl.exe on this machine."""

    name = "local"

    def __init__(self, exe: Path):
        self.exe = Path(exe)

    def command(self, input_json: Path, output_json: Path, ntop: Path, extra_args: list[str]) -> list[str]:
        exe = str(self.exe)
        cmd = [sys.executable, exe] if exe.lower().endswith(".py") else [exe]
        return cmd + ["-j", str(input_json), "-o", str(output_json)] + list(extra_args) + [str(ntop)]

    def run_ntopcl(self, variant_name: str, run_id: str, input_json: Path, output_json: Path,
                   ntop: Path, extra_args: list[str], timeout: float) -> ExecResult:
        cmd = self.command(input_json, output_json, ntop, extra_args)
        proc = subprocess.run(cmd, cwd=str(ntop.parent), capture_output=True, text=True,
                              errors="replace", timeout=timeout)
        return ExecResult(proc.returncode, proc.stdout or "", proc.stderr or "", subprocess.list2cmdline(cmd))

    def generate_templates(self, variant_name: str, ntop: Path, dest: Path) -> list[Path]:
        """``ntopcl -t model.ntop`` writes template JSON files into the cwd."""
        dest.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as td:
            exe = str(self.exe)
            cmd = ([sys.executable, exe] if exe.lower().endswith(".py") else [exe]) + ["-t", str(ntop)]
            proc = subprocess.run(cmd, cwd=td, capture_output=True, text=True, errors="replace", timeout=600)
            (dest / "ntopcl_template.log").write_text(
                subprocess.list2cmdline(cmd) + "\n\n" + (proc.stdout or "") + "\n" + (proc.stderr or ""), encoding="utf-8")
            out = []
            for p in sorted(Path(td).glob("*.json")):
                target = dest / p.name
                target.write_bytes(p.read_bytes())
                out.append(target)
            return out


# --------------------------------------------------------------------------- #
class SSHTransport:
    """ntopcl.exe on another Windows PC, driven over OpenSSH."""

    name = "ssh"

    def __init__(self, host: str = "remote-ntop", work_dir: str = "C:/ntop_sweep",
                 ssh_config: str | None = None, ntopcl: str = "ntopcl",
                 source_root: str | None = None, ssh_exe: str = "ssh", scp_exe: str = "scp",
                 connect_timeout: int = 10, extra_ssh_args: list[str] | None = None):
        self.host = host
        self.work = PureWindowsPath(work_dir)
        self.ssh_config = ssh_config
        self.ntopcl = ntopcl
        self.source_root = PureWindowsPath(source_root) if source_root else None
        self.ssh_exe, self.scp_exe = ssh_exe, scp_exe
        self.connect_timeout = connect_timeout
        self.extra_ssh_args = list(extra_ssh_args or [])
        self._notebooks: dict[str, PureWindowsPath] = {}

    # ---- primitives ------------------------------------------------------ #
    def _base(self, exe: str) -> list[str]:
        args = [exe]
        if self.ssh_config:
            args += ["-F", self.ssh_config]
        if exe == self.scp_exe:
            args += ["-O"]
        args += ["-o", "BatchMode=yes", "-o", f"ConnectTimeout={self.connect_timeout}"] + self.extra_ssh_args
        return args

    def exec(self, remote_cmd: str, timeout: float | None = None) -> ExecResult:
        """Run one command on the remote (cmd.exe semantics)."""
        cmd = self._base(self.ssh_exe) + [self.host, remote_cmd]
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
        return ExecResult(proc.returncode, proc.stdout or "", proc.stderr or "", subprocess.list2cmdline(cmd))

    def powershell(self, script: str, timeout: float | None = None) -> ExecResult:
        enc = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        return self.exec(f"{REMOTE_POWERSHELL} -NoProfile -NonInteractive -EncodedCommand {enc}", timeout)

    def put(self, local: Path, remote: str | PureWindowsPath, timeout: float = 600) -> ExecResult:
        cmd = self._base(self.scp_exe) + [str(local), f"{self.host}:{_fwd(remote)}"]
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
        return ExecResult(proc.returncode, proc.stdout or "", proc.stderr or "", subprocess.list2cmdline(cmd))

    def get(self, remote: str | PureWindowsPath, local: Path, timeout: float = 600) -> ExecResult:
        local.parent.mkdir(parents=True, exist_ok=True)
        cmd = self._base(self.scp_exe) + [f"{self.host}:{_fwd(remote)}", str(local)]
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
        return ExecResult(proc.returncode, proc.stdout or "", proc.stderr or "", subprocess.list2cmdline(cmd))

    def mkdir(self, remote_dir: str | PureWindowsPath) -> ExecResult:
        w = _win(remote_dir)
        return self.exec(f'cmd /c if not exist "{w}" mkdir "{w}"')

    def exists(self, remote_path: str | PureWindowsPath) -> bool:
        w = _win(remote_path)
        r = self.exec(f'cmd /c if exist "{w}" (echo __YES__) else (echo __NO__)')
        return "__YES__" in r.stdout

    def copy_remote(self, src: str | PureWindowsPath, dst: str | PureWindowsPath) -> ExecResult:
        return self.exec(f'cmd /c copy /Y "{_win(src)}" "{_win(dst)}"')

    def list_json(self, remote_dir: str | PureWindowsPath) -> list[str]:
        r = self.exec(f'cmd /c dir /b "{_win(remote_dir)}\\*.json"')
        if not r.ok:
            return []
        return [ln.strip() for ln in r.stdout.splitlines() if ln.strip().lower().endswith(".json")]

    def check(self) -> ExecResult:
        """whoami + ntopcl --version in one call; use before a campaign."""
        return self.exec(f'cmd /c whoami && "{self.ntopcl}" --version', timeout=60)

    # ---- notebooks -------------------------------------------------------- #
    def variant_dir(self, variant_name: str) -> PureWindowsPath:
        return self.work / variant_name

    def ensure_notebook(self, variant_name: str, local_ntop: Path, local_root: Path | None = None,
                        extra_files: list[str] | None = None) -> PureWindowsPath:
        """Make sure the notebook (and listed side files) exist in the no-space work folder.

        If ``source_root`` is configured, the files are copied remote-to-remote from the
        user's own folder (same relative path as in the local mirror); otherwise they are
        uploaded with scp.
        """
        if variant_name in self._notebooks:
            return self._notebooks[variant_name]
        vdir = self.variant_dir(variant_name)
        r = self.mkdir(vdir)
        if not r.ok:
            raise RuntimeError(f"cannot create {vdir} on {self.host}: {r.stderr or r.stdout}")
        names = [local_ntop.name] + list(extra_files or [])
        for name in names:
            target = vdir / name
            if self.exists(target):
                continue
            if self.source_root is not None and local_root is not None:
                rel = local_ntop.parent.relative_to(local_root)
                src = self.source_root.joinpath(*rel.parts) / name
                r = self.copy_remote(src, target)
            else:
                r = self.put(local_ntop.parent / name, target)
            if not r.ok:
                raise RuntimeError(f"cannot place {name} in {vdir} on {self.host}: {r.stderr or r.stdout}")
        self._notebooks[variant_name] = vdir / local_ntop.name
        return self._notebooks[variant_name]

    # ---- ntopcl ----------------------------------------------------------- #
    def run_ntopcl(self, variant_name: str, run_id: str, input_json: Path, output_json: Path,
                   ntop: Path, extra_args: list[str], timeout: float,
                   local_root: Path | None = None, extra_files: list[str] | None = None) -> ExecResult:
        remote_ntop = self.ensure_notebook(variant_name, ntop, local_root, extra_files)
        rdir = self.variant_dir(variant_name) / run_id
        self.mkdir(rdir)
        r_in, r_out = rdir / "input.json", rdir / "output.json"
        up = self.put(input_json, r_in)
        if not up.ok:
            return ExecResult(up.returncode, up.stdout, "scp upload failed: " + up.stderr, up.command)
        self.exec(f'cmd /c if exist "{_win(r_out)}" del /q "{_win(r_out)}"')
        extra = " ".join(extra_args)
        remote_cmd = (f'cd /d "{_win(remote_ntop.parent)}" && "{self.ntopcl}" -j "{_win(r_in)}" '
                      f'-o "{_win(r_out)}" {extra} "{remote_ntop.name}"').replace("  ", " ")
        t0 = time.time()
        res = self.exec(remote_cmd, timeout=timeout)
        if self.exists(r_out):
            dl = self.get(r_out, output_json)
            if not dl.ok:
                res = ExecResult(res.returncode or 1, res.stdout, res.stderr + "\nscp download failed: " + dl.stderr, res.command)
        res.stdout += f"\n[transport] remote run {rdir} took {time.time() - t0:.1f} s\n"
        return res

    def generate_templates(self, variant_name: str, ntop: Path, dest: Path, local_root: Path | None = None) -> list[Path]:
        """Run ``ntopcl -t`` in the remote variant folder and fetch the JSON files it writes."""
        remote_ntop = self.ensure_notebook(variant_name, ntop, local_root)
        vdir = remote_ntop.parent
        before = set(self.list_json(vdir))
        r = self.exec(f'cd /d "{_win(vdir)}" && "{self.ntopcl}" -t "{remote_ntop.name}"', timeout=600)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "ntopcl_template.log").write_text(r.command + "\n\n" + r.stdout + "\n" + r.stderr, encoding="utf-8")
        new = [n for n in self.list_json(vdir) if n not in before] or sorted(self.list_json(vdir))
        out = []
        for name in new:
            local = dest / name
            if self.get(vdir / name, local).ok:
                out.append(local)
        return out

    # ---- results ---------------------------------------------------------- #
    def push_tree(self, local_dir: Path, remote_dest: str | PureWindowsPath, timeout: float = 1800) -> ExecResult:
        """Zip a local folder, upload it, expand it on the remote into ``remote_dest``."""
        local_dir = Path(local_dir)
        zpath = Path(tempfile.gettempdir()) / f"cage_doe_sync_{int(time.time())}.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for p in local_dir.rglob("*"):
                if p.is_file():
                    z.write(p, p.relative_to(local_dir.parent))
        remote_zip = self.work / zpath.name
        self.mkdir(self.work)
        up = self.put(zpath, remote_zip, timeout=timeout)
        if not up.ok:
            return up
        dest = _win(remote_dest)
        script = (f"New-Item -ItemType Directory -Force -Path '{dest}' | Out-Null\n"
                  f"Expand-Archive -Force -Path '{_win(remote_zip)}' -DestinationPath '{dest}'\n"
                  f"Remove-Item -Force '{_win(remote_zip)}'\n"
                  f"Write-Output ('synced to ' + '{dest}')")
        r = self.powershell(script, timeout=timeout)
        try:
            zpath.unlink()
        except OSError:
            pass
        return r


def build_transport(cfg: dict, exe: Path | None, remote: bool | None = None):
    """Choose the transport from config / flags."""
    rc = cfg["project"].get("remote", {}) or {}
    use_remote = rc.get("enabled", False) if remote is None else remote
    if use_remote:
        return SSHTransport(host=rc.get("host", "remote-ntop"), work_dir=rc.get("work_dir", "C:/ntop_sweep"),
                            ssh_config=rc.get("ssh_config"), ntopcl=rc.get("ntopcl", "ntopcl"),
                            source_root=rc.get("source_root"), ssh_exe=rc.get("ssh_exe", "ssh"),
                            scp_exe=rc.get("scp_exe", "scp"), connect_timeout=int(rc.get("connect_timeout", 10)),
                            extra_ssh_args=rc.get("extra_ssh_args"))
    if exe is None:
        raise FileNotFoundError("ntopcl.exe not found for the local transport")
    return LocalTransport(exe)
