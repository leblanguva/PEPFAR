{
  description = "PEPFAR disease - trade analysis";

  inputs  = { nixpkgs.url = "github:nixos/nixpkgs/nixos-24.11"; };
  outputs = { self, nixpkgs }:
  let 
    # System
    system    = "x86_64-linux";
#    system    = "x86_64-darwin"; # if running on macosx

    pkgs      = import nixpkgs { inherit system; config.allowUnfree = true; };
    rinla     = false;
    r-profile = ./.Rprofile;

    # r-packages
    rpacks = with pkgs.rPackages; [
      biscale
      countrycode
      cowplot
      cshapes
      here
      imputeTS
      janitor
      kableExtra
      lmtest
      loo
      magic
      marginaleffects
      raster
      readxl
      rstan
      sf
      spatialreg
      spdep
      stars
      tidyverse
      texreg
    ];
    rstudio = pkgs.rstudioWrapper.override { packages = [ rpacks ]; }; 
  in
  {
    # nb - activate with `nix develop` 
    devShells.${system}.default = pkgs.mkShell {
      packages    = [ rstudio ];
      shellHook   = ''rstudio'';
      R_PROFILE   = r-profile;
    };
  };
}
