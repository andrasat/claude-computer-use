import platform
from datetime import datetime
from typing import Any, cast

from anthropic import (
  Anthropic,
  APIError,
  APIResponseValidationError,
  APIStatusError,
)
from anthropic.types.beta import (
  BetaCacheControlEphemeralParam,
  BetaImageBlockParam,
  BetaMessage,
  BetaMessageParam,
  BetaTextBlock,
  BetaTextBlockParam,
  BetaToolResultBlockParam,
  BetaToolUseBlockParam,
)

from tools import BashTool, ComputerTool, EditTool, ToolCollection, ToolResult

SYSTEM_PROMPT = f"""
<SYSTEM_CAPABILITY>
* You are utilising an Ubuntu virtual machine using {platform.machine()} architecture with internet access.
* This environment does not have GUI setup.
* You must not install any packages with your bash tool, only use defined tools by the user, if user did not define any tools, ask the user to confirm.
* Use curl instead of wget.
* When using your bash tool with commands that are expected to output very large quantities of text, redirect into a tmp file and use str_replace_editor or `grep -n -B <lines before> -A <lines after> <query> <filename>` to confirm output.
* When using your computer function calls, they take a while to run and send back to you.  Where possible/feasible, try to chain multiple of these calls all into one function calls request.
* The current date is {datetime.today().strftime('%A, %B %-d, %Y')}.
</SYSTEM_CAPABILITY>
"""
COMPUTER_USE_BETA_FLAG = "computer-use-2024-10-22"
PROMPT_CACHING_BETA_FLAG = "prompt-caching-2024-07-31"
MODEL = "claude-3-5-sonnet-20241022"

tool_collection = ToolCollection(
  ComputerTool(),
  BashTool(),
  EditTool(),
)

system_prompt = BetaTextBlockParam(
  type="text",
  text=f"{SYSTEM_PROMPT}",
  cache_control=BetaCacheControlEphemeralParam(type="ephemeral")
)


def _inject_prompt_caching(messages: list[BetaMessageParam]):
  breakpoints_remaining = 3
  for message in reversed(messages):
    if message["role"] == "user" and isinstance(content := message["content"], list):
      if breakpoints_remaining:
        breakpoints_remaining -= 1
        content[-1]["cache_control"] = BetaCacheControlEphemeralParam({"type": "ephemeral"})
      else:
        content[-1].pop("cache_control", None)
        # we'll only every have one extra turn per loop
        break

def _maybe_prepend_system_tool_result(result: ToolResult, result_text: str):
    if result.system:
        result_text = f"<system>{result.system}</system>\n{result_text}"
    return result_text

def _response_to_params(response: BetaMessage) -> list[BetaTextBlockParam | BetaToolUseBlockParam]:
  blocks: list[BetaTextBlockParam | BetaToolUseBlockParam] = []
  for block in response.content:
    if isinstance(block, BetaTextBlock):
      blocks.append({"type": "text", "text": block.text})
      print(f"Assistant: {block.text}\n---")
    else:
      tool_use_block = cast(BetaToolUseBlockParam, block.model_dump())
      blocks.append(tool_use_block)
      print(f"Tool Use: {tool_use_block['name']}")
      print(f"Input: {tool_use_block['input']}\n---")
  return blocks

def _make_api_tool_result(result: ToolResult, tool_use_id: str) -> BetaToolResultBlockParam:
  tool_result_content: list[BetaTextBlockParam | BetaImageBlockParam] | str = []
  is_error = False

  if result.error:
    is_error = True
    tool_result_content = _maybe_prepend_system_tool_result(result, result.error)
  else:
    if result.output:
      tool_text_content = _maybe_prepend_system_tool_result(result, result.output)
      tool_result_content.append(
        {
          "type": "text",
          "text": tool_text_content,
        }
      )
      print(f"Tool Result Output: {tool_text_content}\n---")
    if result.base64_image:
      tool_result_content.append(
        {
          "type": "image",
          "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": result.base64_image,
          },
        }
      )
      print(f"Tool Result Image: {result.base64_image}\n---")
  return {
    "type": "tool_result",
    "content": tool_result_content,
    "tool_use_id": tool_use_id,
    "is_error": is_error,
  }

async def agent_loop(client: Anthropic, messages: list[BetaMessageParam]):
  while True:
    _inject_prompt_caching(messages)

    try:
      response = client.beta.messages.create(
        max_tokens=4096,
        messages=messages,
        model=MODEL,
        system=[system_prompt],
        tools=tool_collection.to_params(),
        betas=[COMPUTER_USE_BETA_FLAG, PROMPT_CACHING_BETA_FLAG],
      )
    except (APIStatusError, APIResponseValidationError) as e:
      raise e
    except APIError as e:
      raise e

    response_params = _response_to_params(response)
    messages.append(BetaMessageParam(
      role="assistant",
      content=response_params,
    ))

    tool_result_content: list[BetaToolResultBlockParam] = []
    for content_block in response_params:
      if content_block["type"] == "tool_use":
        result = await tool_collection.run(
          name=content_block["name"],
          tool_input=cast(dict[str, Any], content_block["input"]),
        )
        tool_result = _make_api_tool_result(result, content_block["id"])
        tool_result_content.append(tool_result)

    if not tool_result_content:
      return messages

    messages.append(BetaMessageParam(
      role="user",
      content=tool_result_content,
    ))
