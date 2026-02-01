{
  description = "BTCMAP Admin page";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
    in {
      devShells.${system}.default = pkgs.mkShell {
        name = "btcmap-admin";

        buildInputs = with pkgs; [
          python310
          python310Packages.virtualenv
          geos
        ];
        shellHook = ''
          export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath [ pkgs.stdenv.cc.cc.lib pkgs.geos ]}:$LD_LIBRARY_PATH"
          echo "Environment loaded with C++ libraries for Shapely"
        '';
      };
    };
}

