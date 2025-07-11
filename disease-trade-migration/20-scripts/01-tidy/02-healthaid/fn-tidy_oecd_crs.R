tidy_oecd_crs <- function(path){
  # Takes oecd crs zip file path, ids the embeded file name, and reads
  # the deliminated file and tidies data

  fn <- unzip(path, list = TRUE)$Name
  x  <- read_delim(file      = unz(path, fn),
                   delim     = "|",
                   col_names = TRUE,
                   locale    = locale(encoding = "UTF-16LE"),
                   progress  = FALSE,
                   show_col_types = FALSE)

  x <- x %>%
    janitor::clean_names() %>%
    filter(flow_name == "ODA Grants") %>%
    mutate(
      oecd_class = case_when(
        purpose_code %in% c(12110, 12181, 12182, 12191, 12281) ~ "admin",
        purpose_code %in% c(12220, 12230, 12240, 12261)   ~ "basic",
        purpose_code %in% c(12250)                        ~ "disInfectious",
        purpose_code %in% c(12262)                        ~ "disMalaria",
        purpose_code %in% c(12263)                        ~ "disTb",
        purpose_code %in% c(13040)                        ~ "disStdhiv",
        purpose_code %in% c(12310, 12320, 12330,
                            12340, 12350, 12382)          ~ "disNoncomm",
        purpose_code %in% c(13020, 13030, 13081)          ~ "reproductive",
        purpose_code %in% c(72010)                        ~ "emergency",
        purpose_code %in% c(93013)                        ~ "refugee",
        .default = NA_character_),
      aid2020usd = usd_disbursement_defl * 1e6) %>%
    drop_na(oecd_class) %>%
    filter(aid2020usd >= 0) %>%
    rename(cname = recipient_name) %>%
    select(cname, year, oecd_class, aid2020usd)

  return(x)
}
