import logging

from rich.logging import RichHandler


def setup_logging(verbose: bool = False, level: str = "info") -> None:
    resolved_level = (
        logging.DEBUG if verbose else getattr(logging, level.upper(), logging.INFO)
    )
    logging.basicConfig(
        level=resolved_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, markup=True)],
        force=True,
    )
