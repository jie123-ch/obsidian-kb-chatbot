; 知识库助手 · PC 客户端安装脚本（Inno Setup 7）
; 编译： "C:\Program Files\Inno Setup 7\ISCC.exe" installer.iss
; 产物： dist-installer\KBChat-Setup.exe

[Setup]
AppId={{A9F4C2E1-7B3D-4E5F-9C8A-1B2C3D4E5F60}
AppName=知识库助手
AppVersion=1.0
AppPublisher=KBChat
DefaultDirName={autopf}\KBChat
DefaultGroupName=知识库助手
OutputDir=dist-installer
OutputBaseFilename=KBChat-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern
UninstallDisplayName=知识库助手
DisableProgramGroupPage=no

[Languages]
Name: "chinese"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Files]
Source: "dist\KBChat\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\知识库助手"; Filename: "{app}\KBChat.exe"
Name: "{autodesktop}\知识库助手"; Filename: "{app}\KBChat.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务"; Flags: unchecked

[Run]
Filename: "{app}\KBChat.exe"; Description: "立即启动知识库助手"; Flags: nowait postinstall

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
