Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class WinMenu {
  [DllImport("user32.dll")] public static extern IntPtr GetMenu(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetSubMenu(IntPtr m, int i);
  [DllImport("user32.dll")] public static extern int GetMenuItemCount(IntPtr m);
  [DllImport("user32.dll")] public static extern uint GetMenuStringA(IntPtr m, uint id, StringBuilder s, uint max);
  [DllImport("user32.dll")] public static extern int GetMenuItemID(IntPtr m, int i);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern IntPtr PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  public static string ItemName(IntPtr m, int i) {
    var sb = new StringBuilder(256);
    GetMenuStringA(m, (uint)i, sb, 256);
    return sb.ToString();
  }
}
'@
$h = (Get-Process mgba | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1).MainWindowHandle
$hmenu = [WinMenu]::GetMenu($h)
Write-Output ("hmenu=" + $hmenu.ToInt64())
$total = [WinMenu]::GetMenuItemCount($hmenu)
$toolsIdx = -1
for ($i = 0; $i -lt $total; $i++) {
  $t = [WinMenu]::ItemName($hmenu, $i)
  Write-Output ("TOP[$i]='$t'")
  if ($t -match 'Tools') { $toolsIdx = $i }
}
if ($toolsIdx -lt 0) { Write-Output "NO_TOOLS_MENU"; exit 1 }
$hsub = [WinMenu]::GetSubMenu($hmenu, $toolsIdx)
Write-Output ("TOOLS_SUB=" + $hsub.ToInt64())
$count = [WinMenu]::GetMenuItemCount($hsub)
$target = -1
for ($i = 0; $i -lt $count; $i++) {
  $t = [WinMenu]::ItemName($hsub, $i)
  $id = [WinMenu]::GetMenuItemID($hsub, $i)
  Write-Output ("TOOL[$i]='$t' id=$id")
  if ($t -match 'script|lua|console') { $target = $id }
}
Write-Output ("TARGET_ID=" + $target)
if ($target -ge 0) {
  [WinMenu]::SendMessage($h, 0x0111, [IntPtr]$target, [IntPtr]0) | Out-Null
  Start-Sleep -Milliseconds 800
  Write-Output "SENT_WM_COMMAND"
}
