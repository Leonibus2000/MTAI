# MTAI privacy mode: Windows Firewall helper. firewall.py starts this with administrator
# rights (a UAC prompt the user must accept) and only after the user agreed in MTAI.
#
# It only ever touches rules that MTAI made: the name must look like MTAI-Privacy-<hex>
# AND the rule group must be "MTAI Privacy". Other firewall rules are never read for
# changes, changed or removed. Firewall profiles and settings are not changed.
#
#   apply : one outbound Block rule per program, for every remote address except
#           127.0.0.0/8 and ::1 (so the program can still talk to MTAI on this PC),
#           then close the program's open IPv4 connections to outside addresses.
#   remove: delete the named rules (only if they are MTAI's).
param([Parameter(Mandatory = $true)][string]$Job)

$ErrorActionPreference = 'Stop'
$G = 'MTAI Privacy'
$Remote = @('0.0.0.0-126.255.255.255', '128.0.0.0-255.255.255.255', '::', '::2-ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff')
$out = [ordered]@{ ok = $true; action = $null; created = @(); existed = @(); removed = @(); missing = @(); closed = @(); left = @(); errors = @() }

function Test-OurName([string]$n) { return $n -match '^MTAI-Privacy-[0-9a-f]{12,32}$' }

try {
  $j = Get-Content -Raw -LiteralPath $Job | ConvertFrom-Json
  $out.action = $j.action
  if ($j.action -eq 'apply') {
    foreach ($r in $j.rules) {
      try {
        if (-not (Test-OurName $r.name)) { $out.errors += "not an MTAI rule name: $($r.name)"; continue }
        if (-not (Test-Path -LiteralPath $r.program -PathType Leaf)) { $out.errors += "missing program: $($r.program)"; continue }
        $have = Get-NetFirewallRule -Name $r.name -ErrorAction SilentlyContinue
        if ($have) {
          if ($have.Group -ne $G) { $out.errors += "a rule named $($r.name) exists but is not MTAI's: left alone"; continue }
          Set-NetFirewallRule -Name $r.name -Enabled True -Action Block -Direction Outbound -RemoteAddress $Remote -Profile Any
          $out.existed += $r.name
          continue
        }
        $leaf = Split-Path -Leaf $r.program
        New-NetFirewallRule -Name $r.name -DisplayName "MTAI Privacy: block $leaf" -Group $G `
          -Description ("Made by MTAI privacy mode on " + (Get-Date -Format 's') + ". Blocks internet access of this program while privacy mode is on; 127.0.0.1 and ::1 stay open. MTAI removes it when privacy mode turns off.") `
          -Direction Outbound -Action Block -Program $r.program -RemoteAddress $Remote -Profile Any -Enabled True | Out-Null
        $out.created += $r.name
      } catch { $out.errors += "$($r.name): $($_.Exception.Message)" }
    }
    if ($j.close) {
      # open connections are not affected by a new rule: close the IPv4 ones (Windows has no call for IPv6)
      Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
public static class MtaiTcp {
  [StructLayout(LayoutKind.Sequential)] public struct ROW { public uint state, localAddr, localPort, remoteAddr, remotePort; }
  [DllImport("iphlpapi.dll")] public static extern int SetTcpEntry(ref ROW row);
}
'@
      $progs = @($j.rules | ForEach-Object { $_.program.ToLower() })
      $pids = @(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and ($progs -contains $_.ExecutablePath.ToLower()) } | ForEach-Object { [int]$_.ProcessId })
      foreach ($c in @(Get-NetTCPConnection -ErrorAction SilentlyContinue | Where-Object { $pids -contains [int]$_.OwningProcess -and ($_.State -eq 'Established' -or $_.State -eq 'SynSent') })) {
        $ra = [Net.IPAddress]::Parse($c.RemoteAddress)
        $txt = "$($c.OwningProcess) $($c.RemoteAddress):$($c.RemotePort)"
        if ($ra.IsIPv4MappedToIPv6) { $ra = $ra.MapToIPv4() }
        if ([Net.IPAddress]::IsLoopback($ra)) { continue }
        if ($ra.AddressFamily -ne 'InterNetwork') { $out.left += "$txt (IPv6)"; continue }
        $la = [Net.IPAddress]::Parse($c.LocalAddress); if ($la.IsIPv4MappedToIPv6) { $la = $la.MapToIPv4() }
        $row = New-Object MtaiTcp+ROW
        $row.state = 12
        $row.localAddr = [BitConverter]::ToUInt32($la.GetAddressBytes(), 0)
        $row.localPort = [uint32]((($c.LocalPort -band 0xFF) -shl 8) -bor ($c.LocalPort -shr 8))
        $row.remoteAddr = [BitConverter]::ToUInt32($ra.GetAddressBytes(), 0)
        $row.remotePort = [uint32]((($c.RemotePort -band 0xFF) -shl 8) -bor ($c.RemotePort -shr 8))
        $rc = [MtaiTcp]::SetTcpEntry([ref]$row)
        if ($rc -eq 0) { $out.closed += $txt } else { $out.left += "$txt (error $rc)" }
      }
    }
  } elseif ($j.action -eq 'remove') {
    foreach ($n in $j.names) {
      try {
        if (-not (Test-OurName $n)) { $out.errors += "not an MTAI rule name: $n"; continue }
        $have = Get-NetFirewallRule -Name $n -ErrorAction SilentlyContinue
        if (-not $have) { $out.missing += $n; continue }
        if ($have.Group -ne $G) { $out.errors += "$n is not in the MTAI Privacy group: left alone"; continue }
        Remove-NetFirewallRule -Name $n
        $out.removed += $n
      } catch { $out.errors += "${n}: $($_.Exception.Message)" }
    }
  } else { $out.errors += "unknown action" }
} catch { $out.errors += $_.Exception.Message }

$out.ok = ($out.errors.Count -eq 0)
$out | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath ($Job + '.result.json') -Encoding UTF8
