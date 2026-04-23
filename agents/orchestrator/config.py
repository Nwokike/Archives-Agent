# agents/orchestrator/config.py

# --- CENTRALIZED DATASET REGISTRY ---
# To add a new dataset in the future, simply add "ds9": "username/new-dataset" to this dictionary.
DATASETS = {
    "ds1": "nwokikeonyeka/maa-cambridge-william-henry-crosse",
    "ds2": "nwokikeonyeka/maa-cambridge-south-eastern-nigeria",
    "ds3": "nwokikeonyeka/pitt-rivers-igbo-collection",
    "ds4": "nwokikeonyeka/british-museum-igbo-collection",
    "ds5": "nwokikeonyeka/re-entanglements-audio",
    "ds6": "nwokikeonyeka/re-entanglements-documents",
    "ds7": "nwokikeonyeka/ukpuru_blog_dataset",
    "ds8": "nwokikeonyeka/gi_jones_archive_dataset"
}

# --- DEFAULT FALLBACK ---
# This is the default dataset key used by the Orchestrator if it is run in isolation 
# (e.g., tested via Google ADK Web UI) where the Telegram system directive is not present.
DEFAULT_DS_KEY = "ds2"

# Evaluates to "nwokikeonyeka/maa-cambridge-south-eastern-nigeria" based on the key above
DEFAULT_DATASET = DATASETS[DEFAULT_DS_KEY]
