#!/usr/bin/env python3
import uuid
import subprocess
from pathlib import Path
from typing import Dict, Any

def build_wix_installer(config: Dict[str, Any]) -> None:
    """Build the WiX installer if enabled in config."""
    if not config.get('installer', {}).get('enabled', False):
        return
    
    installer = config['installer']
    build = config['build']
    
    # Ensure required directories exist
    output_dir = Path(installer['output']['directory'])
    output_dir.mkdir(exist_ok=True)
    
    # Check if the executable exists
    exe_path = Path(build['output']['directory']) / build['output']['filename']
    if not exe_path.exists():
        print(f"Error: Executable not found at {exe_path}")
        print("Please build the executable first.")
        return
    
    # Generate WiX source file
    wxs_content = generate_wix_source(config)
    wxs_path = output_dir / "installer.wxs"
    with open(wxs_path, 'w') as f:
        f.write(wxs_content)
    
    try:
        # Build MSI using WiX
        cmd = [
            "wix",
            "build",
            str(wxs_path),
            "-bindpath", f"BinDir={build['output']['directory']}",
            "-bindpath", f"UiImagesDir={Path('rsrc/images')}",
            "-bindpath", f"InstallerDir={Path('rsrc')}",
            "-ext", "WixToolset.UI.wixext",
            "-o", str(output_dir / installer['output']['filename'])
        ]
            
        subprocess.run(cmd, check=True)
        print("WiX installer built successfully!")
        
    except subprocess.CalledProcessError as e:
        print(f"Error building installer: {e}")
        raise

def generate_wix_source(config: Dict[str, Any]) -> str:
    """Generate WiX source file content."""
    installer = config['installer']
    project = config['project']
    build = config['build']
    
    # Only include URL properties if they are set
    url_properties = ""
    if project.get('url'):
        url_properties = f'''
        <Property Id="ARPURLINFOABOUT" Value="{project['url']}" />
        <Property Id="ARPHELPLINK" Value="{project['url']}" />'''
    
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs"
     xmlns:ui="http://wixtoolset.org/schemas/v4/wxs/ui"
     xmlns:util="http://wixtoolset.org/schemas/v4/wxs/util">
    <Package
        Name="{installer['metadata']['product_name']}"
        Manufacturer="{installer['metadata']['manufacturer']}"
        Version="{project['version']}"
        UpgradeCode="{installer['metadata']['upgrade_code']}"
        Scope="perMachine">
        
        <MajorUpgrade DowngradeErrorMessage="A newer version of [ProductName] is already installed." />
        <MediaTemplate EmbedCab="yes" />
        
        <!-- Application Icon -->
        {f'<Icon Id="app.ico" SourceFile="{project["icon"]}" />' if project.get('icon') else ''}
        {f'<Property Id="ARPPRODUCTICON" Value="app.ico" />' if project.get('icon') else ''}
        
        <!-- Add/Remove Programs Information -->{url_properties}
        <Property Id="ARPCOMMENTS" Value="{project['description']}" />
        <Property Id="ARPCONTACT" Value="{installer['metadata']['manufacturer']}" />
        <Property Id="ARPNOREPAIR" Value="1" />
        
        <!-- Directory Structure -->
        <StandardDirectory Id="ProgramFiles64Folder">
            <Directory Id="INSTALLFOLDER" Name="{installer['metadata']['product_name']}">
                <Component Id="MainExecutable" Guid="{str(uuid.uuid4())}">
                    <File Id="MainEXE"
                          Name="{build['output']['filename']}"
                          Source="!(bindpath.BinDir)\\{build['output']['filename']}"
                          KeyPath="yes">
                        <!-- Grant read and execute permissions to all users -->
                        <Permission User="Everyone" GenericAll="yes" />
                    </File>
                    
                    <!-- Register application -->
                    <RegistryValue Root="HKLM"
                                 Key="Software\\{installer['metadata']['product_name']}"
                                 Name="InstallPath"
                                 Type="string"
                                 Value="[INSTALLFOLDER]" />
                </Component>
            </Directory>
        </StandardDirectory>
        
        <!-- Start Menu -->
        <StandardDirectory Id="ProgramMenuFolder">
            <Directory Id="ApplicationProgramsFolder" Name="{installer['metadata']['product_name']}">
                <Component Id="ApplicationShortcuts" Guid="{str(uuid.uuid4())}">
                    <Shortcut Id="ApplicationShortcut"
                             Name="{installer['metadata']['product_name']}"
                             Description="{project['description']}"
                             Target="[INSTALLFOLDER]{build['output']['filename']}"
                             WorkingDirectory="INSTALLFOLDER"
                             Icon="app.ico" />
                    <RemoveFolder Id="CleanUpShortCut" Directory="ApplicationProgramsFolder" On="uninstall" />
                    <RegistryValue Root="HKCU"
                                 Key="Software\\{installer['metadata']['manufacturer']}\\{installer['metadata']['product_name']}"
                                 Name="installed"
                                 Type="integer"
                                 Value="1"
                                 KeyPath="yes" />
                </Component>
            </Directory>
        </StandardDirectory>
        
        <!-- Features -->
        <Feature Id="ProductFeature" Title="{installer['metadata']['product_name']}" Level="1">
            <ComponentRef Id="MainExecutable" />
            <ComponentRef Id="ApplicationShortcuts" />
        </Feature>
        
        <!-- UI -->
        <Property Id="WIXUI_INSTALLDIR" Value="INSTALLFOLDER" />
        <Property Id="WIXUI_EXITDIALOGOPTIONALTEXT" Value="Thank you for installing TomeFlow." />
        
        <!-- Custom UI Images -->
        <WixVariable Id="WixUIDialogBmp" Value="!(bindpath.UiImagesDir)\\wix_background.bmp" />
        <WixVariable Id="WixUIBannerBmp" Value="!(bindpath.UiImagesDir)\\wix_banner_wide.bmp" />

        <!-- License -->
        <WixVariable Id="WixUILicenseRtf" Value="!(bindpath.InstallerDir)\\license.rtf" />
        
        <ui:WixUI Id="WixUI_InstallDir" />
        
    </Package>
</Wix>'''

if __name__ == "__main__":
    import yaml
    
    # Load config and build installer when run directly
    with open('build_config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    build_wix_installer(config)