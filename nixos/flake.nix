{
  description = "Network Music Mesh - NixOS ISO x86_64 (Intel/AMD)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
  };

  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };

    mesh-scripts = pkgs.runCommand "mesh-scripts" { } ''
      mkdir -p $out/bin
      cp ${./scripts/mesh_agent.py} $out/bin/mesh_agent.py
      cp ${./scripts/mesh_tui.py} $out/bin/mesh_tui.py
      cp ${./scripts/webui.py} $out/bin/webui.py
      chmod +x $out/bin/*.py
    '';
  in {
    nixosConfigurations.mesh-iso = nixpkgs.lib.nixosSystem {
      inherit system;
      specialArgs = { inherit mesh-scripts; };
      modules = [
        "${nixpkgs}/nixos/modules/installer/cd-dvd/installation-cd-minimal.nix"
        ./configuration.nix
      ];
    };

    packages.x86_64-linux.default = mesh-scripts;
  };
}
