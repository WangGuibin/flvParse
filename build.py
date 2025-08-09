import os
import platform
import subprocess

def run_command(command):
    """执行一个 shell 命令并打印输出"""
    print(f"Executing: {command}")
    try:
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
        rc = process.poll()
        if rc != 0:
            print(f"Error: Command returned non-zero exit code {rc}")
        return rc
    except Exception as e:
        print(f"Failed to execute command: {e}")
        return -1

def build():
    """根据操作系统执行打包流程"""
    system = platform.system()
    
    # 第一步: 使用 PyInstaller 创建应用
    pyinstaller_command = "pyinstaller --clean --noconfirm flv_parser.spec"
    if system == "Darwin": # macOS
        pyinstaller_command = "pyinstaller --clean --noconfirm flv_parser.spec"
    
    print(f"--- Running PyInstaller on {system} ---")
    if run_command(pyinstaller_command) != 0:
        print("PyInstaller build failed.")
        return

    print("--- PyInstaller build successful ---")

    # 第二步: 如果是 macOS，创建 DMG
    if system == "Darwin":
        print("\n--- Creating DMG for macOS ---")
        app_path = "dist/FLVParser.app"
        dmg_path = "dist/FLVParser-Installer.dmg"
        icon_path = "app_icon.icns" # 假设图标在根目录

        if not os.path.exists(app_path):
            print(f"Error: {app_path} not found. Cannot create DMG.")
            return
            
        if not os.path.exists(icon_path):
            print(f"Warning: App icon not found at {icon_path}. DMG will not have a custom icon.")
            icon_path = "" # 如果找不到图标则不使用

        create_dmg_command = (
            f'create-dmg '
            f'--volname "FLV Parser Installer" '
            f'--volicon "{icon_path}" '
            f'--window-pos 200 120 '
            f'--window-size 800 400 '
            f'--icon-size 100 '
            f'--icon "FLVParser.app" 200 190 '
            f'--hide-extension "FLVParser.app" '
            f'--app-drop-link 600 185 '
            f'"{dmg_path}" '
            f'"{app_path}"'
        )
        
        if run_command(create_dmg_command) != 0:
            print("DMG creation failed.")
            return
        
        print(f"--- DMG created successfully at {dmg_path} ---")

    elif system == "Windows":
        print("\n--- Windows build complete ---")
        print("The distributable application is in the 'dist/FLVParser' folder.")

    else:
        print(f"\n--- Build complete for {system} ---")
        print("The distributable application is in the 'dist' folder.")

if __name__ == "__main__":
    build()