import base64
import io
import json
import time

import mss
import pyautogui
from PIL import Image
from openai import OpenAI


SERVER = "http://10.0.2.2:8080/v1"
MODEL = "Qwen3.8-27B"
MAX_RECENT_ACTIONS = 100


client = OpenAI(
    base_url=SERVER,
    api_key="none",
)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": (
                "Left-click a visible point on the computer screen. "
                "Coordinates use normalized screen coordinates from 0 to 1000. "
                "Top-left is (0, 0), bottom-right is (1000, 1000)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 1000,
                        "description": (
                            "Normalized horizontal coordinate from 0 to 1000."
                        ),
                    },
                    "y": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 1000,
                        "description": (
                            "Normalized vertical coordinate from 0 to 1000."
                        ),
                    },
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": (
                "Type text into the currently focused text field."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The exact text to type.",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": (
                "Press a keyboard key such as enter, escape, tab, "
                "backspace, delete, up, down, left, or right."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Name of the key to press.",
                    },
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": (
                "Call this only when the requested task is visibly complete."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


SYSTEM_PROMPT = (
    "You control the computer shown in screenshots. "
    "Complete the user's task using the provided tools. "
    "\n\n"
    "IMPORTANT COORDINATE SYSTEM:\n"
    "All click coordinates are normalized from 0 to 1000.\n"
    "Top-left corner = (0, 0).\n"
    "Center of screen = (500, 500).\n"
    "Bottom-right corner = (1000, 1000).\n"
    "\n"
    "Do NOT return screenshot pixel coordinates. "
    "Use normalized 0-1000 coordinates for click(). "
    "\n\n"
    "AVAILABLE INTERACTIONS:\n"
    "- click(x, y): click something visible\n"
    "- type_text(text): type into the currently focused field\n"
    "- press_key(key): press keys such as enter, escape, or tab\n"
    "- done(): finish the task\n"
    "\n\n"
    "Before every tool call, give a brief activity description "
    "in one or two short sentences. "
    "Describe the relevant visible state and what you are about to do. "
    "Do not provide lengthy reasoning. "
    "\n\n"
    "IMPORTANT ACTION VERIFICATION:\n"
    "After every action you will receive a new screenshot. "
    "Compare the new screenshot to the previous state and verify that "
    "the action had the intended effect. "
    "Do not assume an action succeeded merely because the tool executed. "
    "If the expected change is not visible, recognize that the attempt "
    "failed and try a different action. "
    "Do not repeatedly perform the exact same unsuccessful action. "
    "If a text field is already focused, use type_text instead of "
    "clicking the field repeatedly. "
    "If text has been entered and needs to be submitted, use press_key "
    "with enter when appropriate. "
    "\n\n"
    "Call done only when the requested result is visibly complete."
)


def capture_screen():
    with mss.mss() as sct:
        monitor = sct.monitors[1]

        shot = sct.grab(monitor)

        image = Image.frombytes(
            "RGB",
            shot.size,
            shot.rgb,
        )

        width, height = image.size

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        encoded = base64.b64encode(
            buffer.getvalue()
        ).decode("ascii")

        return (
            f"data:image/png;base64,{encoded}",
            width,
            height,
        )


def normalized_to_screen(x, y):
    screen_width, screen_height = pyautogui.size()

    pixel_x = round(
        (x / 1000.0) * (screen_width - 1)
    )

    pixel_y = round(
        (y / 1000.0) * (screen_height - 1)
    )

    return pixel_x, pixel_y


def run_task(task):
    recent_actions = []
    step = 1

    while True:
        print()
        print(f"--- Step {step} ---")

        image_url, image_width, image_height = capture_screen()

        control_width, control_height = pyautogui.size()

        print(
            f"Screenshot: "
            f"{image_width}x{image_height}"
        )

        print(
            f"Mouse coordinate space: "
            f"{control_width}x{control_height}"
        )

        print("Sending screenshot to model...")

        recent_actions_text = "\n".join(
            f"{index}. {action}"
            for index, action in enumerate(recent_actions, start=1)
        ) or "None yet."

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]

        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Task: {task}\n\n"
                            f"Recent actions:\n{recent_actions_text}\n\n"
                            "Examine the current screenshot. "
                            "Verify the result of the previous action, if any. "
                            "Briefly describe the relevant state and your next "
                            "action, then use exactly one appropriate tool. "
                            "Remember that click coordinates use the normalized "
                            "0-1000 coordinate system."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        },
                    },
                ],
            }
        )

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0,
        )

        message = response.choices[0].message

        if message.content:
            print()
            print("Model:")
            print(message.content)

        assistant_message = {
            "role": "assistant",
            "content": message.content or "",
        }

        if message.tool_calls:
            assistant_message["tool_calls"] = [
                call.model_dump()
                for call in message.tool_calls
            ]

        messages.append(assistant_message)

        if not message.tool_calls:
            print()
            print("Model did not call a tool.")
            return

        # For this MVP, execute only the first tool call.
        call = message.tool_calls[0]

        tool_name = call.function.name

        try:
            arguments = json.loads(
                call.function.arguments or "{}"
            )

        except json.JSONDecodeError:
            print()
            print("Invalid tool arguments:")
            print(call.function.arguments)
            return

        print()
        print(
            f"Tool call: "
            f"{tool_name} {arguments}"
        )

        if tool_name == "done":
            print()
            print("Task complete.")
            return

        elif tool_name == "click":
            normalized_x = int(arguments["x"])
            normalized_y = int(arguments["y"])

            pixel_x, pixel_y = normalized_to_screen(
                normalized_x,
                normalized_y,
            )

            print(
                "Qwen coordinate: "
                f"({normalized_x}, {normalized_y})"
            )

            print(
                "Actual mouse click: "
                f"({pixel_x}, {pixel_y})"
            )

            pyautogui.click(
                pixel_x,
                pixel_y,
            )

            result = (
                f"Click command executed at normalized coordinate "
                f"({normalized_x}, {normalized_y}). "
                "Verify its effect visually in the next screenshot."
            )

        elif tool_name == "type_text":
            text = arguments["text"]

            print(
                f"Typing: {text!r}"
            )

            pyautogui.write(
                text,
                interval=0.03,
            )

            result = (
                f"Typing command executed for text {text!r}. "
                "Verify that the text actually appears in the "
                "next screenshot."
            )

        elif tool_name == "press_key":
            key = arguments["key"].lower()

            print(
                f"Pressing key: {key}"
            )

            pyautogui.press(key)

            result = (
                f"Key press command executed for {key!r}. "
                "Verify its effect visually in the next screenshot."
            )

        else:
            print()
            print(
                f"Unknown tool: "
                f"{tool_name}"
            )
            return

        messages.append(
            {
                "role": "tool",
                "tool_call_id": call.id,
                "content": result,
            }
        )

        recent_actions.append(result)
        recent_actions = recent_actions[-MAX_RECENT_ACTIONS:]

        time.sleep(1)

        step += 1


def main():
    print(f"Using model: {MODEL}")

    screen_width, screen_height = pyautogui.size()

    print(
        f"Mouse coordinate space: "
        f"{screen_width}x{screen_height}"
    )

    print()
    print("Computer agent ready.")
    print("Enter a task, or type 'exit' to quit.")

    while True:
        print()

        task = input("Task: ").strip()

        if not task:
            continue

        if task.lower() in {
            "exit",
            "quit",
            "q",
        }:
            print("Exiting.")
            break

        print()
        print(f"Starting task: {task}")

        try:
            run_task(task)

        except KeyboardInterrupt:
            print()
            print("Task interrupted.")

        except Exception as error:
            print()
            print(f"Task failed: {error}")

        print()
        print("Ready for next task.")


if __name__ == "__main__":
    main()
