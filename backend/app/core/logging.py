import logging


def configure_logging() -> None:
    # Log categories, not credentials or database URLs.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
