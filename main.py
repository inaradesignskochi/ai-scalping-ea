import asyncio
from data_ingestion.data_aggregator import DataAggregator
from ai_pipeline.ai_orchestrator import AIOrchestrator

async def main():
    # Initialize the components
    data_aggregator = DataAggregator()
    ai_orchestrator = AIOrchestrator()

    # Start the data aggregator
    asyncio.create_task(data_aggregator.start())

    # Load the AI models
    ai_orchestrator.load_active_models()

    # TODO: Add logic to process data from the aggregator and feed it to the orchestrator

if __name__ == "__main__":
    asyncio.run(main())