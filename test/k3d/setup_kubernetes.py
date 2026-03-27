import platform
import sys
import urllib.request
import os
import stat
from utils import run_cmd


def install_k3d():
    """Install k3d."""
    print("Installing k3d...")
    run_cmd("curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash")


def get_arch():
    """Check if the platform is x86 or arm64."""
    arch = platform.machine()
    if arch == "x86_64":
        print("amd64")
        return "amd64"
    elif arch in ("aarch64", "arm64"):
        print("arm64")
        return "arm64"
    else:
        print(f"Unsupported architecture: {arch}")
        sys.exit(1)


def install_kubectl(c_arch):
    """Download kubectl."""
    print("Installing kubectl...")

    # Get latest stable version
    with urllib.request.urlopen(
        "https://storage.googleapis.com/kubernetes-release/release/stable.txt"
        ) as response:
        version = response.read().decode().strip()

    url = f"https://storage.googleapis.com/kubernetes-release/release/{version}/bin/linux/{c_arch}/kubectl"
    filename = "kubectl"

    print(f"Downloading kubectl {version}...")
    urllib.request.urlretrieve(url, filename)

    # Make executable
    st = os.stat(filename)
    os.chmod(filename, st.st_mode | stat.S_IEXEC)

    # Move to /usr/local/bin (requires sudo)
    print("Moving kubectl to /usr/local/bin (may require sudo)...")
    run_cmd(f"sudo mv {filename} /usr/local/bin/")


def main():
    """Download k3d and kubectl."""
    install_k3d()
    c_arch = get_arch()
    install_kubectl(c_arch)
    print("Done!")


if __name__ == "__main__":
    main()
