let
  pkgs = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/1dab772dd4a68a7bba5d9460685547ff8e17d899.tar.gz") {};
in pkgs.mkShell {
  packages = [
    pkgs.act
    pkgs.uv
    pkgs.python311
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
