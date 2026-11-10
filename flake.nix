{
  description = "Carter Spreen Data 3301";

  inputs = {
    # Official "nixpkgs" flake for NixOS 26.05
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-26.05";
  };

  outputs =
    {
      self,
      nixpkgs,
    }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };

      projectName = "data-science";

      # this is super important. the nixpkgs version of micromamba is broken.
      # TODO: submit a PR to nixpkgs to fix this, then remove this override.
      micromambaFixed = pkgs.micromamba.overrideAttrs (_previous: {
        installPhase = ''
          mkdir -p "$out/bin"

          cp \
            ${pkgs.mamba-cpp}/bin/.mamba-wrapped \
            "$out/bin/micromamba"
        '';
      });
    in
    {
      # formatter for Nix files
      formatter.${system} = pkgs.nixfmt;

      # development shells for data science
      devShells.${system} = {
        # main development shell for data science, with micromamba
        default = pkgs.mkShell {
          name = "devShell";

          packages = with pkgs; [
            git
            neovim
            bashInteractive
            micromambaFixed
          ];

          shellHook = ''
            # determine the project 
            project_root="$(git rev-parse --show-toplevel)"
            project_name="${projectName}"

            # set the micromamba root prefix to a hidden directory in the project root
            export MAMBA_ROOT_PREFIX="$project_root/.mamba"

            # confine strict mode to setup so it does not affect the interactive shell
            (
              set -euo pipefail

              # create the micromamba environment if it doesn't exist
              if ! micromamba run --name ${projectName} true >/dev/null 2>&1; then
                micromamba create --yes --file "$project_root/environment.yml"
              fi

            )

            # activate the micromamba environment
            export MAMBA_CHANGEPS1=false
            eval "$(micromamba shell hook --shell bash)"
            micromamba activate ${projectName}

            # unset local variables before dropping into the development shell
            unset project_root
          '';
        };
      };
    };
}
