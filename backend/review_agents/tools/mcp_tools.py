"""
外部 MCP 工具接入模块
用于连接外部 MCP 服务，扩展 Agent 能力
"""

import httpx
from typing import Optional
from agents import function_tool
from backend.config import MCP_SERVER_URLS


@function_tool
async def call_external_mcp_tool(
    server_url: str,
    tool_name: str,
    arguments: dict
) -> str:
    """
    调用外部 MCP 服务器提供的工具。

    Args:
        server_url: MCP 服务器地址
        tool_name: 工具名称
        arguments: 工具参数

    Returns:
        工具执行结果
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{server_url}/tools/call",
                json={
                    "name": tool_name,
                    "arguments": arguments
                }
            )
            response.raise_for_status()
            result = response.json()
            return str(result.get("content", result))
    except httpx.TimeoutException:
        return f"调用 MCP 工具超时：{server_url}"
    except httpx.HTTPStatusError as e:
        return f"MCP 工具调用失败：HTTP {e.response.status_code}"
    except Exception as e:
        return f"MCP 工具调用异常：{str(e)}"


@function_tool
def list_available_mcp_servers() -> str:
    """
    列出已配置的外部 MCP 服务器。

    Returns:
        可用的 MCP 服务器列表
    """
    if not MCP_SERVER_URLS:
        return "未配置外部 MCP 服务器。可在 .env 文件中通过 MCP_SERVER_URLS 配置。"

    result_parts = ["已配置的外部 MCP 服务器：\n"]
    for i, url in enumerate(MCP_SERVER_URLS, 1):
        result_parts.append(f"{i}. {url}")

    return "\n".join(result_parts)
