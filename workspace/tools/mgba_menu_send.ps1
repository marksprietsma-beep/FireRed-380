Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class Mnu {
  [DllImport("user32.dll")] public static extern IntPtr GetWindowLongPtrA(IntPtr h, int i);
  [DllImport("user32.dll")] public static extern IntPtr GetMenu(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetMenuItemCount(IntPtr m);
  [DllImport("user32.dll")] public static extern IntPtr GetSubMenu(IntPtr m, int i);
  [DllImport("user32.dll")] public static extern int GetMenuItemID(IntPtr m, int i);
  [DllImport("user32.dll", CharSet=CharSet.Ansi)] public static extern uint GetMenuStringA(IntPtr m, uint id, StringBuilder s, uint max);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  public static string ItemName(IntPtr m, int i) {
    var sb = new StringBuilder(256);
    GetMenuStringA(m, (uint)i, sb, 256);
    return sb.ToString();
  }
}
'@
$proc = Get-Process mgba | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
$h = $proc.MainWindowHandle
$hmenu = [Mnu]::GetMenu($h)
Write-Output ("hmenu=" + $hmenu)
$total = [Mnu]::GetMenuItemCount($hmenu)
$toolsIdx = -1
for ($i = 0; $i -lt $total; $i++) {
  $t = [Mnu]::ItemName($hmenu, $i)
  Write-Output ("TOP[$i]='$t'")
  if ($t -match 'Tools') { $toolsIdx = $i }
}
if ($toolsIdx -lt 0) { Write-Output "NO_TOOLS_MENU"; exit 1 }
$hsub = [Mnu]::GetSubMenu($hmenu, $toolsIdx)
$count = [Mnu]::GetMenuItemCount($hsub)
$targetID = -1
for ($i = 0; $i -lt $count; $i++) {
  $t = [Mnu]::ItemName($hsub, $i)
  $id = [Mnu]::GetMenuItemID($hsub, $i)
  Write-Output ("TOOLS[$i]='$t' id=$id")
  if ($t -match 'script') { $targetID = $id }
}
Write-Output ("TARGET=" + $targetID)
if ($targetID -gt 0) {
  [Mnu]::SendMessage($h, 0x0111, [IntPtr]$targetID, [IntPtr]0) | Out-Null
  Start-Sleep -Milliseconds 1200
  Write-Output "SENT_WM_COMMAND"
}
