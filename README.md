# kcpr

DATA 3301 KCPR final project respository.

## Setup

### 1. Create a virtual environment

This project was developed with **Python 3.14.4**. Other versions may work, but there are no guarantees.

```sh
python3 -m venv .venv
```

Activate the virtual environment:

```sh
# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

With the virtual environment activated:

```sh
pip install -r requirements.txt
```

### 3. Create a `.env` file

The script reads API keys from a `.env` file in the project root. Copy the provided example:

```sh
cp .env.example .env
```

Then replace the placeholder values with keys (ask Remi for keys):

```sh
OPENWEATHER_API_KEY=your_openweather_api_key
SOUNDNET_API_KEY=your_rapidapi_key
```

`.env` is listed in `.gitignore`, so don't commit the keys.

## Running

With the virtual environment activated:

```sh
python main.py
```