let
  pkgs = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/007fabe5bdc9285121cc6ed011c07b7af56c43fb.tar.gz") {};
in pkgs.mkShell {
  packages = [
    pkgs.act
    pkgs.uv
    pkgs.hatch
    pkgs.python311
    pkgs.kubectl
    pkgs.kind
    pkgs.trivy
    pkgs.kompose
  ];
  
 shellHook = ''
 export PYTHONPATH=$(pwd)/src

 # Create venv if it doesn't exist
 if [ ! -d .venv ]; then
   uv venv --python=${pkgs.python311}/bin/python3 .venv
 fi

 # Activate venv
 source .venv/bin/activate

 # Install optional deps
 uv pip install ".[dev]"

 # Start fish shell
 exec fish
 '';
}
