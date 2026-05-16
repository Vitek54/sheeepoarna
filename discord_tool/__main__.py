"""Entry point: python -m discord_tool"""

import asyncio

from discord_tool.app import main

if __name__ == "__main__":
    asyncio.run(main())
