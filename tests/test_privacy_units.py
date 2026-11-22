"""
Regression tests for MTAI's privacy mode that need no administrator rights and change nothing
in Windows. Run after every update:

    py -3.13 -m unittest tests.test_privacy_units -v        (from the MTAI folder, about 20 s)

What they cover:
  - loopback detection used by the audit hook and the gate
  - the Windows Firewall rule template: the remote ranges leave out exactly 127.0.0.0/8 and ::1
    and cover every other address; the helper script uses the same ranges and name checks
  - the rule ledger: MTAI only ever asks Windows to remove names it wrote down, writes names down
    before asking, refuses Windows' own programs and paths discovery did not find
  - local AI program discovery returns real files only; Windows components are never selectable
  - the connection watcher's scan works
  - the status levels: green only when every required check passed and nothing is unprotected
  - the image worker's guard refuses new programs
  - the code sandbox's file, registry, process and privilege limits (privacy mode, real runs)

The real firewall test (rules added with a UAC prompt, real connection attempts from the
restricted programs, then removed again) is in tests/privacy_suite.py --firewall.
"""
import ipaddress
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
import local_ai_chat as L          # noqa: E402  (installs the audit hook, privacy off)
import netguard as NG              # noqa: E402
import firewall as FW              # noqa: E402
import backends as BK              # noqa: E402
import privacy_check as PC         # noqa: E402


def _ranges(spec):
    out = []
    for r in spec:
        if "-" in r:
            a, b = r.split("-")
            out.append((ipaddress.ip_address(a), ipaddress.ip_address(b)))
        else:
            a = ipaddress.ip_address(r)
            out.append((a, a))
    return out


def _covered(ip, spec):
    ip = ipaddress.ip_address(ip)
    return any(a.version == ip.version and a <= ip <= b for a, b in _ranges(spec))


class Loopback(unittest.TestCase):
    def test_loopback_hosts(self):
        for h in ("127.0.0.1", "127.8.9.10", "::1", "localhost", "[::1]"):
            self.assertTrue(NG.is_loopback_host(h), h)

    def test_outside_hosts(self):
        for h in ("1.1.1.1", "10.0.0.1", "192.168.1.1", "::2", "2606:4700:4700::1111", "example.com", "0.0.0.0"):
            self.assertFalse(NG.is_loopback_host(h), h)

    def test_watcher_outside(self):
        self.assertFalse(BK._outside("127.0.0.1"))
        self.assertFalse(BK._outside("::1"))
        self.assertTrue(BK._outside("1.1.1.1"))
        self.assertTrue(BK._outside("2606:4700:4700::1111"))


class RuleTemplate(unittest.TestCase):
    def test_loopback_left_out(self):
        for ip in ("127.0.0.1", "127.0.0.0", "127.255.255.255", "::1"):
            self.assertFalse(_covered(ip, FW.REMOTE), ip)

    def test_everything_else_covered(self):
        for ip in ("0.0.0.0", "1.1.1.1", "10.0.0.1", "126.255.255.255", "128.0.0.0", "192.168.1.1", "255.255.255.255",
                   "::", "::2", "::ffff:1.1.1.1", "fe80::1", "2606:4700:4700::1111", "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff"):
            self.assertTrue(_covered(ip, FW.REMOTE), ip)

    def test_counts(self):
        v4 = sum(int(b) - int(a) + 1 for a, b in _ranges(FW.REMOTE) if a.version == 4)
        v6 = sum(int(b) - int(a) + 1 for a, b in _ranges(FW.REMOTE) if a.version == 6)
        self.assertEqual(v4, 2 ** 32 - 2 ** 24)
        self.assertEqual(v6, 2 ** 128 - 1)

    def test_helper_matches(self):
        ps = (APP / "fwhelper.ps1").read_text("utf-8")
        m = re.search(r"^\$Remote = @\((.*)\)$", ps, re.M)
        self.assertEqual(re.findall(r"'([^']+)'", m.group(1)), FW.REMOTE)
        self.assertIn("$G = '" + FW.GROUP + "'", ps)
        # remove: the name pattern AND the group are checked before anything is deleted
        rem = ps[ps.index("'remove'"):]
        self.assertLess(rem.index("Test-OurName"), rem.index("Remove-NetFirewallRule"))
        self.assertLess(rem.index("$have.Group -ne $G"), rem.index("Remove-NetFirewallRule"))
        # apply: an existing rule of another group is left alone
        app = ps[ps.index("'apply'"):ps.index("'remove'")]
        self.assertLess(app.index("$have.Group -ne $G"), app.index("Set-NetFirewallRule"))
        self.assertNotIn("Set-NetFirewallProfile", ps)

    def test_rule_names(self):
        a = FW.rule_name(r"C:\Programs\Ollama\ollama.exe")
        self.assertEqual(a, FW.rule_name(r"c:\programs\ollama\OLLAMA.EXE"))
        self.assertRegex(a, r"^MTAI-Privacy-[0-9a-f]{12,32}$")
        self.assertNotEqual(a, FW.rule_name(r"C:\Programs\Ollama\llama-server.exe"))

    def test_rule_ok(self):
        prog = r"C:\x\ollama.exe"
        good = {"enabled": "True", "action": "Block", "direction": "Outbound", "program": prog,
                "remote": ["0.0.0.0-126.255.255.255", "128.0.0.0-255.255.255.255", "::", "::2-ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff"]}
        self.assertTrue(FW._rule_ok(good, prog))
        for change in ({"enabled": "False"}, {"action": "Allow"}, {"direction": "Inbound"}, {"program": r"C:\y.exe"},
                       {"remote": ["Any"]}, {"remote": ["127.0.0.1", "1.1.1.1", "::"]}, {"remote": []}):
            self.assertFalse(FW._rule_ok({**good, **change}, prog), change)


class Ledger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = (FW.DATA, FW.APP, FW.state, FW.run_elevated)
        FW.init(Path(self.tmp.name), APP)
        self.jobs = []
        self.windows = {}                       # name -> rule, what the fake Windows has

        def fake_state():
            return {"rules": list(self.windows.values()), "profiles": [], "categories": ["Private"], "active_profiles_on": True}

        def fake_elevated(job, timeout=240):
            self.jobs.append(job)
            self.assertTrue(FW.ledger()["rules"] or job["action"] == "remove")   # written down before Windows is asked
            if job["action"] == "apply":
                for r in job["rules"]:
                    self.windows[r["name"]] = {"name": r["name"], "program": r["program"], "enabled": "True",
                                               "action": "Block", "direction": "Outbound", "remote": FW.REMOTE}
            else:
                for n in job["names"]:
                    self.windows.pop(n, None)
            return {"ok": True}
        FW.state, FW.run_elevated = fake_state, fake_elevated

    def tearDown(self):
        FW.DATA, FW.APP, FW.state, FW.run_elevated = self.old
        self.tmp.cleanup()

    def test_refuses_windows_and_missing(self):
        with self.assertRaises(FW.FwError):
            FW.apply([str(Path(os.environ["SystemRoot"]) / "System32" / "curl.exe")], with_probe=False)
        with self.assertRaises(FW.FwError):
            FW.apply([str(Path(self.tmp.name) / "nope.exe")], with_probe=False)
        self.assertEqual(self.jobs, [])

    def test_apply_remove_roundtrip(self):
        exe = Path(self.tmp.name) / "fake-backend.exe"
        exe.write_bytes(b"MZ")
        FW.apply([str(exe)], with_probe=False)
        self.assertEqual(len(FW.ledger()["rules"]), 1)
        self.assertNotIn("pending", FW.ledger())
        self.windows["Some-Other-App-Rule"] = {"name": "Some-Other-App-Rule", "program": "x"}
        out = FW.remove(["Some-Other-App-Rule"])            # not MTAI's: never sent to Windows
        self.assertEqual(out["removed"], [])
        self.assertEqual(len(self.jobs), 1)
        FW.remove()
        self.assertEqual(self.jobs[-1]["names"], [FW.rule_name(str(exe))])
        self.assertIn("Some-Other-App-Rule", self.windows)
        self.assertEqual(FW.ledger()["rules"], [])

    def test_reconcile_after_crash(self):
        led = {"rules": [{"name": FW.rule_name(r"C:\a.exe"), "program": r"C:\a.exe"},
                         {"name": FW.rule_name(r"C:\b.exe"), "program": r"C:\b.exe"}], "pending": {"action": "apply"}}
        FW._save(led)
        self.windows[led["rules"][0]["name"]] = {"name": led["rules"][0]["name"]}
        FW._reconcile()
        self.assertEqual([e["name"] for e in FW.ledger()["rules"]], [led["rules"][0]["name"]])
        self.assertNotIn("pending", FW.ledger())

    def test_app_refuses_undiscovered(self):
        self.assertIn("error", L.firewall_apply({"programs": ["x"]}))           # no consent flag
        r = L.firewall_apply({"confirm": True, "programs": [str(Path(os.environ["SystemRoot"]) / "System32" / "curl.exe")]})
        self.assertIn("did not find", r.get("error", ""))
        self.assertEqual(self.jobs, [])


class Discovery(unittest.TestCase):
    def test_real_files_only(self):
        win = os.environ.get("SystemRoot", r"C:\Windows").lower() + os.sep
        for b in BK.discover():
            self.assertTrue(b["exes"])
            for e in b["exes"]:
                self.assertTrue(Path(e["path"]).is_file(), e["path"])
                self.assertTrue(e["sources"], e["path"])
                if e["path"].lower().startswith(win):
                    self.assertFalse(e["selectable"], e["path"])
                if e["default"]:
                    self.assertTrue(e["selectable"])

    def test_scan(self):
        r = BK.scan([])
        self.assertGreaterEqual(r["mtai"], 1)
        for c in r["conns"]:
            self.assertTrue(BK._outside(c["remote"].rsplit(":", 1)[0].strip("[]")))


class StatusLevels(unittest.TestCase):
    GROUPS = ["Python in MTAI", "Other programs", "Connection watcher", "Browser", "Code runs", "Code sandbox",
              "Cloud and downloads"]

    def setUp(self):
        self.saved = (L.PRIVACY["on"], NG.STATE.get("changed"), PC.LAST["run"])
        L.PRIVACY["on"] = True
        NG.STATE["changed"] = time.time() - 10

    def tearDown(self):
        L.PRIVACY["on"], NG.STATE["changed"], PC.LAST["run"] = self.saved

    def _run(self, extra=(), probes=True):
        rows = [PC.R(g, g, g, "PASS", "") for g in self.GROUPS] + [PC.R("Local models", "engine-guard", "e", "PASS", "")]
        rows += [PC.R(*x) for x in extra]
        counts = {k: sum(1 for r in rows if r["result"] == k) for k in PC.RESULTS}
        PC.LAST["run"] = {"t": time.time(), "privacy": True, "browser_probes": probes, "counts": counts, "results": rows}
        return PC.status()

    def test_green_only_when_all_pass(self):
        self.assertEqual(self._run()["level"], "verified")
        self.assertEqual(self._run([("Native code", "n", "n", "INFO", "")])["level"], "verified")
        self.assertEqual(self._run(probes=False)["level"], "partly")
        self.assertEqual(self._run([("Ollama (Windows Firewall)", "b", "b", "UNPROTECTED", "")])["level"], "partly")
        self.assertEqual(self._run([("Browser", "x", "x", "UNVERIFIED", "")])["level"], "partly")
        self.assertEqual(self._run([("Browser", "x", "x", "FAIL", "")])["level"], "failed")
        st = self._run([("Ollama (Windows Firewall)", "b", "b", "UNPROTECTED", "")])
        self.assertEqual([c["state"] for c in st["components"] if c.get("backend")], ["unprotected"])

    def test_missing_component_rows_not_green(self):
        PC.LAST["run"] = {"t": time.time(), "privacy": True, "browser_probes": True,
                          "counts": {"PASS": 1}, "results": [PC.R("Browser", "b", "b", "PASS", "")]}
        self.assertEqual(PC.status()["level"], "partly")

    def test_stale_run(self):
        self._run()
        NG.STATE["changed"] = time.time() + 1
        self.assertEqual(PC.status()["level"], "unchecked")


class WorkerGuard(unittest.TestCase):
    def test_worker_cannot_start_programs_or_connect(self):
        code = ("import sys, socket, subprocess; sys.path.insert(0, sys.argv[1]); import netguard; "
                "netguard.install(always=True, component_name='test')\n"
                "try:\n subprocess.run(['cmd', '/c', 'exit']); print('PROC-RAN')\n"
                "except PermissionError: print('PROC-BLOCKED')\n"
                "try:\n socket.create_connection(('1.1.1.1', 443), timeout=3); print('NET-OPEN')\n"
                "except PermissionError: print('NET-BLOCKED')\n")
        with NG.allow("unit test child"):
            r = subprocess.run([sys.executable, "-c", code, str(APP)], capture_output=True, text=True, timeout=60)
        self.assertIn("PROC-BLOCKED", r.stdout, r.stderr)
        self.assertIn("NET-BLOCKED", r.stdout, r.stderr)


@unittest.skipUnless(PC.SB_ok(), "AppContainer sandbox not available")
class SandboxBounds(unittest.TestCase):
    def test_bounds(self):
        L.set_privacy(True)
        try:
            rows = PC.sandbox_bounds()
        finally:
            L.set_privacy(False)
        self.assertTrue(rows)
        bad = [r for r in rows if r["result"] != "PASS" and not (r["id"] == "sb-loop" and r["result"] == "UNVERIFIED")]
        self.assertEqual(bad, [], json.dumps(bad, indent=1))
        ids = {r["id"] for r in rows}
        for want in ("sb-docs", "sb-settings", "sb-other", "sb-pywrite", "sb-reg", "sb-proc", "sb-ac", "sb-priv", "sb-il", "sb-env"):
            self.assertIn(want, ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)
