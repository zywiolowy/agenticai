# Run in PowerShell as Administrator.
# Lets the Raspberry Pi (and other machines on your home network) reach vLLM and Langfuse.
# Only the "Private" network profile – make sure your home Wi-Fi/Ethernet is set to Private.

New-NetFirewallRule -DisplayName "AI Lab - vLLM 8000"    -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "AI Lab - Langfuse 3000" -Direction Inbound -Protocol TCP -LocalPort 3000 -Action Allow -Profile Private

# Check the network profile:
Get-NetConnectionProfile | Select-Object Name, InterfaceAlias, NetworkCategory
# If it says Public, change it (replace the alias):
# Set-NetConnectionProfile -InterfaceAlias "Ethernet" -NetworkCategory Private

# To remove the rules later:
# Remove-NetFirewallRule -DisplayName "AI Lab - vLLM 8000"
# Remove-NetFirewallRule -DisplayName "AI Lab - Langfuse 3000"
