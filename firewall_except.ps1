New-NetFirewallRule -DisplayName "STU3 WSL-Windows 55556" `
  -Direction Inbound -Action Allow -Protocol TCP -LocalPort 55556 `
  -Profile Domain,Private,Public
