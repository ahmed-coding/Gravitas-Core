import uvicorn
import anyio
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import Response
from mcp.server.sse import SseServerTransport
from gravitas_mcp.server import app as mcp_app

# Create SSE Transport with correct path
sse = SseServerTransport("/messages/")


async def handle_sse(request):
    """
    SSE endpoint for MCP connections.
    """
    print("New SSE connection established.")
    try:
        async with sse.connect_sse(
            request.scope, 
            request.receive, 
            request._send
        ) as (read_stream, write_stream):
            # Run the MCP app in a task group to handle the session
            async with anyio.create_task_group() as tg:
                tg.start_soon(mcp_app.run, read_stream, write_stream, mcp_app.create_initialization_options())
                # Keep the task group alive while connection is active
                await anyio.sleep_forever()
    except anyio.get_cancelled_exc():
        # Clean shutdown when client disconnects
        pass
    return Response(status_code=200)


# Create Starlette app with SSE and message endpoints
starlette_app = Starlette(
    debug=True,
    routes=[
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ]
)


if __name__ == "__main__":
    uvicorn.run(starlette_app, host="127.0.0.1", port=8000, log_level="info")
