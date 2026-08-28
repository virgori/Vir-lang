import platform
import os
import subprocess

def get_system_info():
    uname = platform.uname()
    cpu_brand = "Unknown CPU"
    
    if platform.system() == "Darwin":
        try:
            res = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                cpu_brand = res.stdout.strip()
            else:
                res2 = subprocess.run(["sysctl", "-n", "hw.model"], capture_output=True, text=True)
                cpu_brand = res2.stdout.strip()
        except Exception:
            pass
    elif platform.system() == "Linux":
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        cpu_brand = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass

    # Compiler versions
    clang_ver = "Not installed"
    try:
        res = subprocess.run(["clang", "--version"], capture_output=True, text=True)
        if res.returncode == 0:
            clang_ver = res.stdout.splitlines()[0].strip()
    except Exception:
        pass

    return {
        "os": f"{uname.system} {uname.release} ({uname.machine})",
        "cpu": cpu_brand,
        "cores": os.cpu_count() or 1,
        "clang": clang_ver,
        "vir": "Vir V2.0 (Self-Hosted Native Compiler)"
    }

if __name__ == "__main__":
    import pprint
    pprint.pprint(get_system_info())
