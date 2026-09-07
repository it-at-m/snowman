from truststore import inject_into_ssl

from src.config.settings import IndexerSettings, SnowSettings
from src.indexer.pipeline import IndexingPipeline
from src.loaders.snow_loader import SnowLoader
from src.utils.logtools import getLogger

inject_into_ssl()
logger = getLogger()


def main() -> None:
    settings = IndexerSettings()
    source = SnowLoader(SnowSettings())
    indexer = IndexingPipeline(settings)
    result = indexer.run(source)
    logger.info(
        "Indexer finished",
        extra={
            "run_id": result.run_id,
            "source_documents": result.source_documents,
            "chunks_upserted": result.chunks_upserted,
            "stale_points_deleted": result.stale_points_deleted,
        },
    )


if __name__ == "__main__":
    main()
