import os
import json
from openai import AsyncOpenAI
from dotenv import load_dotenv
import bot_tools

load_dotenv()

client = AsyncOpenAI(
    base_url="https://llm.adityaberry.me/v1",
    api_key=os.getenv("OPENAI_API_KEY", "dummy-key")
)

MODEL_NAME = "Qwen3-Coder-Next-UD-Q4_K_XL.gguf"

async def get_chat_response(messages: list) -> str:
    """
    Sends messages to the custom LLM, handles any tool calls it requests, 
    and returns the final text response.
    """
    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=bot_tools.llm_tools,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=1000
        )
        
        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        # Step 2: check if the model wanted to call a function
        if tool_calls:
            # Append the assistant's request to call tools to the history
            messages.append(response_message)
            
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_to_call = bot_tools.available_functions.get(function_name)
                
                if function_to_call:
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Call the python function
                    function_response = function_to_call(**function_args)
                    
                    # Step 3: send the info back to the model
                    messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": str(function_response),
                        }
                    )
                else:
                    # Failsafe if the model hallucinated a tool
                    messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": "Error: Unknown function requested.",
                        }
                    )

            # Step 4: get a new response from the model with the tool output included
            second_response = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
            )
            return second_response.choices[0].message.content
        
        # If no tools were called, just return the text
        return response_message.content

    except Exception as e:
        return f"Error communicating with LLM: {str(e)}"

