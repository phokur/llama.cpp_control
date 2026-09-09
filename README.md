# llama.cpp control

A small Python script that uses a local llama.cpp vision model to see the screen and control the mouse and keyboard.

The Python script captures the desktop, sends the screenshot and task to llama-server, executes the returned tool call, then repeats until the model reports that the task is complete.

## Features

- Completely local, runs entirely on your computer
- Cross-platform, Windows and Linux/X11 out-of-the-box
- Can separate the llama-server and the agent to sandbox (such as a separate PC or VM)

## Requirements

- Python 3
- llama.cpp for llama-server
- A vision-capable GGUF model and its multimodal projector
- Highly recommend running the agent in a sandbox/VM

Install the Python dependencies:

```bash
pip install openai pyautogui mss pillow
```

On Linux, PyAutoGUI may also require:

```bash
sudo apt install python3-xlib
```

## llama.cpp

Start llama-server with a multimodal model.

Example (may need to tweak based on your hardware/model used):

```bash
llama-server \
  --models-dir "models" \
  --models-max 1 \
  -ngl all \
  --jinja \
  --host 127.0.0.1 \
  --port 8080
```

On Linux, you may need to bind to this instead:

```bash
--host 0.0.0.0
```

## Configuration

At the top of llama.cpp_control, set the llama.cpp server alias:

```python
SERVER = "http://127.0.0.1:8080/v1"
```

If running the agent within a Virtualbox VM:

```python
SERVER = "http://10.0.2.2:8080/v1"
```

For a remote llama.cpp server, use the host PC's IP:

```python
SERVER = "http://192.168.1.X:8080/v1"
```

Next, set the model alias:

```python
MODEL = "Qwen3VL-8B"
```

I have had good luck with:

- Qwen/Qwen3-VL-8B-Instruct-GGUF
- unsloth/Qwen3.8-27B-GGUF

The model name must match the alias exposed by your llama.cpp router. Make sure you grab the associated mmproj multimodal with your model.

## Run

```bash
python llama.cpp_control.py
```

Then enter a task:

```text
Task: Open Notepad and type "Hello World"
```

The agent will repeatedly:

1. Capture the current screen.
2. Send the screenshot and task to the model.
3. Receive one tool call.
4. Execute the click, typing, or key press.
5. Capture a new screenshot and verify the result.
6. Continue until the model determines the task is complete.

Type `exit`, `quit`, or `q` at the task prompt to close the agent.

## Available Tools

The current agent exposes:

- `click(x, y)` — click a normalized screen coordinate
- `type_text(text)` — type into the focused field
- `press_key(key)` — press a keyboard key
- `done()` — report that the task is complete

Click coordinates are normalized from `0` to `1000`:

```text
(0, 0)       = top-left
(500, 500)   = center
(1000, 1000) = bottom-right
```

The Python script converts these values into the actual display resolution.
