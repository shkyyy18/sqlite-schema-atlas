from . import core
from .common import main


def cli():
    return main(core, "sqlite-schema-atlas")


if __name__ == "__main__":
    raise SystemExit(cli())
