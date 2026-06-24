[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=NO
HideExtractAnimation=YES
UseLongFileName=YES
InsideCompressed=YES
CAB_FixedSize=NO
Compress=HIGH
KeepCompressed=YES
[SourceFiles]
SourceFiles=.\
[SourceFiles0]
%FILE0%=CLIENT\EPMS_Agent.exe
%FILE1%=CLIENT\EPMS_Gateway.exe
%FILE2%=CLIENT\agent.json
%FILE3%=CLIENT\Scripts\install-agent-service.ps1
%FILE4%=CLIENT\Scripts\uninstall-agent-service.ps1
[DestinationLocations]
BasePath=%ProgramFiles%\EPMS\Agent
[Strings]
InstallProgram= powershell.exe -ExecutionPolicy Bypass -File ".\install-agent-service.ps1" -Silent
InstallUninstallProgram= powershell.exe -ExecutionPolicy Bypass -File ".\uninstall-agent-service.ps1" -Silent
DisplayLicense=
DisplayFinished=
