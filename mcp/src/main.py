from logging import Logger

from truststore import inject_into_ssl

from src.config.settings import McpSettings
from src.server import create_server
from src.utils.logtools import getLogger

inject_into_ssl()  # add system CA certs to Python's SSL context
logger: Logger = getLogger()


def main() -> None:
    settings = McpSettings()
    server = create_server(settings)
    logger.info(settings)

    logger.info(
        "Starting MCP server",
        extra={
            "transport": settings.transport,
            "host": settings.host,
            "port": settings.port,
            "path": settings.path,
        },
    )
    server.run(transport=settings.transport)


if __name__ == "__main__":
    main()
