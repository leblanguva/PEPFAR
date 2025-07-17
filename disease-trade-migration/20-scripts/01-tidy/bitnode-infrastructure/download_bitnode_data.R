library(rvest)
library(stringr)
library(lubridate)
library(dplyr)
library(jsonlite)

# Base URL
base_url <- "https://www.dsn.kastel.kit.edu/bitcoin/snapshots/"

# Get the list of files
page <- read_html(base_url)
files <- html_attr(html_nodes(page, "a"), "href")
files <- files[str_detect(files, "dossier.json")]

# Create a data frame with filenames and dates
files_df <- data.frame(
  filename = files,
  date = ymd_hms(str_extract(files, "\\d{8}_\\d{6}"), tz = "UTC")
)

# Group by year and month and take the first file of each group
files_to_download <- files_df %>%
  filter(year(date) >= 2023 & year(date) <= 2024) %>%
  group_by(year = year(date), month = month(date)) %>%
  slice(1) %>%
  ungroup() %>%
  select(filename) %>%
  pull()

# Create an empty list to store the data
all_data <- list()

# Download and process the files
for (file in files_to_download) {
  tryCatch({
    # Download the file
    temp_file <- tempfile()
    download.file(paste0(base_url, file), destfile = temp_file)

    # Process the file
    content <- readLines(temp_file, warn = FALSE)
    if (length(content) > 0) {
      data <- fromJSON(content)
    } else {
      next
    }

    # Extract the relevant information
    num_nodes <- length(data)
    total_hash_rate <- sum(sapply(data, function(x) {
      if (!is.null(x$inv) && !is.null(x$inv$blockperhour)) {
        x$inv$blockperhour
      } else {
        0
      }
    }), na.rm = TRUE)

    # Add the data to the list
    all_data[[file]] <- data.frame(
      date = files_df$date[files_df$filename == file],
      num_nodes = num_nodes,
      total_hash_rate = total_hash_rate
    )

    # Remove the temporary file
    unlink(temp_file)
  }, error = function(e) {
    message(paste("Error processing file:", file))
    message(e)
  })
}

# Combine all the data into a single data frame
final_data <- do.call(rbind, all_data)

# Save the tidy dataset to a CSV file
write.csv(final_data, "disease-trade-migration/10-data/02-tidy/bitnode_monthly.csv", row.names = FALSE)
