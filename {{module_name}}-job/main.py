import asyncio

import httpx


EXAMPLE_URL = "https://jsonplaceholder.typicode.com/todos/1"


async def run() -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(EXAMPLE_URL)
        response.raise_for_status()
        print(response.json())


if __name__ == "__main__":
    asyncio.run(run())
