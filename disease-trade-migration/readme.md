# disease-trade-migration

This directory contains all data and code necessary to fit non-spatial and 
dynamic spatial regression models with 1, 2, or 3 simultaneous connectivity 
matrices to explore how PEPFAR health aid allocations diffuse through trade
networks to produce spillover reductions in HIV incidence rates in non-PEPFAR
recipients who trade with PEPFAR recipients.

## Estimated models

For ease of producing these results in a non-R environment, the main analysis
data used in regression models (data that drops unused variables and cases with 
missing observations) is located in a `csv` format at:
  - `10-data/03-analysis/01-analysis-data.csv`

The full data with no dropped variables or observations (that contains missing 
values) is located at:
  - `10-data/02-tidy/04-merge.csv`

All analysis conducted by scripts in this directory utilize the `.Rdata` files
which are functionally identical to these `.csv` files.

The models estimated are as follows:

- base model:
  - `ihme_hiv100kFd ~ ihme_hiv100kFdLag + pepfarPc + analysis_tradePepfarPercent + 
    analysis_tradePepfarPercent2 + cname + year + pepfarPc:analysis_tradePepfarPercent + 
    pepfarPc:analysis_tradePepfarPercent2 + pepfarPc:analysis_tradePepfarPercent:analysis_tradePepfarPercent2 - 
    1`

- base model + controls:
  - `ihme_hiv100kFd ~ ihme_hiv100kFdLag + pepfarPc + analysis_tradePepfarPercent + 
    analysis_tradePepfarPercent2 + oecd_disStdhivAid2020usdPc + 
    oecd_basicAid2020usdPc + oecd_reproductiveAid2020usdPc + 
    oecd_disInfectiousAid2020usdPc + ihme_gov2oop + un_popDensSqkm + 
    un_gdpUSDPc + un_e2i + wb_internetPercent + wb_lifeExpecYrs + 
    wb_mortalityInfant100k + cname + year + pepfarPc:analysis_tradePepfarPercent + 
    pepfarPc:analysis_tradePepfarPercent2 + pepfarPc:analysis_tradePepfarPercent:analysis_tradePepfarPercent2 - 
    1`


## Top-level directory organization:

- disease-trade-migration.Rproj
  - entry point for this project. open this file to launch an R-Studio session
    with proper working directory paths.

- flake.{lock, nix}
  - see reproducibility note below

- 10-data
  - contains all data for this analysis. 
  - 01-source   ~ contains untouched source data along with urls or citations
  - 02-tidy     ~ source data after processing using scripts in 
                  `20-scripts/01-tidy`
  - 03-analysis ~ model results and effects estimates computed using scripts in 
                  `20-scripts/02-analysis`

- 20-scripts
  - contains all scripts used to perform the analysis in this directory
  - 01-tidy     ~ all scripts used for processing untouched source data as well as 
                  producing spatial weights
  - 02-analysis ~ all analysis scripts from substting full merged data for 
                  variables and observations used in regression models, computing
                  descriptive statistics, fitting models, computing marginal 
                  effects, and producing tables and figures

- 30-results
  - stores all tables and figures output from `20-scripts/02-analysis`
  - 01-tables  ~ all tables in tex format
  - 02-figures ~ all figures in png format

- 40-draft
  - an initial sparse draft with initial tables and figures produced by scripts
    in this directory in addition to slides and notes for a talk on this project
    presented at APSA 2023

- 50-miscellaneous
  - assortment of papers related to Bayesian and/or spatial regression modeling

## Estimating results

Note that each script contains detailed header information on the script's 
purpose, what the script imports and exports as well as what other scripts
produced those imports if applicable.

The proper script execution order of files in `20-scripts` is denoted by number:
  - First, execute all scripts in `20-scripts/01-tidy` beginning with 
    `00-panel/default.R` and iterating up to `05-weights/default.R`.

  - After executing all scripts in `20-scripts/01-tidy`, execute all scripts in 
   `20-scripts/02-analysis`, again doing so in order based on number.

  - Note - some scripts are stored in their own folder and named `default.R`, 
    for example, `20-scripts/01-tidy/00-panel/default.R`. This is done purely 
    for organizational purposes as these `default.R` scripts contain axillary 
    functions that are stored in the same folder. Therefore, for all scripts
    in a folder, `default.R` is the main execution script while all other scripts
    are helper functions usually denoted with a `fn-` prefix in the file name.


## Reproducibility

Two additional files are included in the top-level of this directory:
  - flake.lock
  - flake.nix
  
These files are not necessary to run the scripts located in `20-scripts`. 
However, they should never be deleted as the combination of these two files can 
be used to guarantee reproducibility of any results from the scripts in this
directory in the future.

- `flake.nix`  ~ describes all packages used to conduct this analysis
- `flake.lock` ~ describes exact versions of all R packages and system packages
                 as well as all dependencies used to conduct this analysis

Instructions on downloading `nix` - the declarative programming language and 
package manager employed by these flake files can be found here:
  - https://nixos.org/download/

Detailed instructions on using flakes is available here:
  - https://nixos.wiki/wiki/flakes
  
After successfully installing nix, the `flake.nix` file can be used as follows:

1. from a terminal on Mac of Linux navigate to the directory containing this 
   `readme.md` file
2. note system used: if using a linux x86_64 system proceed to step 3, if using
   Mac, open `flake.nix` and uncomment line 9 (remove the hash #) and comment out
   (place a hash # at the start of) line 8 so the file is as follows:
   `
    # system    = "x86_64-linux";
      system    = "x86_64-darwin"; # if running on macosx
   `
3. execute the following command: `nix develop`
