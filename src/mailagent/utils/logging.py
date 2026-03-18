import logging


def setup_logging(verbose: bool = False, level: str = "info") -> None:
    resolved_level = (
        logging.DEBUG if verbose else getattr(logging, level.upper(), logging.INFO)
    )
    logging.basicConfig(
        level=resolved_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )
