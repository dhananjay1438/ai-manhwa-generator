# AI Manhwa Generator

An automated pipeline for generating Manhwa-style videos using AI. It integrates various services for script processing, asset generation (images/audio), and video assembly.

## Prerequisites

- [uv](https://github.com/astral-sh/uv) installed.
- [FFmpeg](https://ffmpeg.org/) installed and available in your PATH.
    - **Note:** For subtitle support, FFmpeg must be built with `--enable-libass`.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd ai-manhwa-generator
    ```

2.  **Install dependencies:**
    ```bash
    uv sync
    ```

3.  **Configure environment variables:**
    Copy `.env.example` to `.env` and fill in your API keys.
    ```bash
    cp .env.example .env
    ```

## Usage

### Running the API Server

Start the FastAPI server using `uv`:
```bash
uv run uvicorn main:app --reload
```
Alternatively, if you've added the script to `pyproject.toml`:
```bash
uv run start
```

### Running Tests

To run the pipeline test script:
```bash
uv run python test_pipeline.py
```

## Development

### Linting and Formatting

This project uses `ruff` for linting and formatting.

- **Check linting:**
  ```bash
  uv run ruff check .
  ```

- **Format code:**
  ```bash
  uv run ruff format .
  ```
