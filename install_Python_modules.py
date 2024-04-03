import importlib.util
import subprocess

required_modules = [
    "ssl", "csv", "socket", "pyVim", "pyVmomi", "requests",
    "kubernetes", "termcolor", "kubernetes.client", "csvkit", "json", "os", "ast"
]

missing_modules = []

for module_name in required_modules:
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        missing_modules.append(module_name)
    else:
        print(f"{module_name} is already installed.")

if missing_modules:
    print("Some modules are missing:", ", ".join(missing_modules))
    print("Installing missing modules...")

    for module_name in missing_modules:
        result = subprocess.run(["pip", "install", module_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            print(f"{module_name} has been successfully installed.")
        else:
            print(f"Failed to install {module_name}:")
            print(result.stderr)
else:
    print("All required modules are already installed.")