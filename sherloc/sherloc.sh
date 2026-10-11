#!/bin/bash
#
# Run: ./sherloc.sh [--install] [--nosudo]
#
# Sets up the environment for Sherloc to run.
# Creates a new virtual environment, activates, and installs requirements.
# Then, runs Sherloc.
# Deactivates afterward.

PYTHON=python${PYTHON_VERSION:='3.12'}
: ${VENV:='sherloc-venv'}
NORMAL_USER=$USER

# Intel Macs are not supported (Pango, which the PDF report needs, has to be
# built from source there). Say so up front instead of failing later.
if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "x86_64" ]; then
    echo "⚠️  Intel Macs are not supported. Sherloc supports Apple Silicon Macs (M1 or newer) and Linux."
fi

# sudo clears the environment. Pass Sherloc's own settings through, above all
# SHERLOC_DATA_DIR: without it client data would go to the default folders.
SHERLOC_ENV=()
for var in SHERLOC_DATA_DIR SHERLOC_HOST SHERLOC_ALLOWED_HOSTS SHERLOC_ADB ANDROID_HOME SHERLOC_SQL_ECHO DEBUG TEST; do
    if [ -n "${!var+x}" ]; then
        SHERLOC_ENV+=("$var=${!var}")
    fi
done

# Check for --install and --notsudo arguments
INSTALL_REQS=false
USE_SUDO=true
for arg in "$@"; do
    if [[ "$arg" == "--install" ]]; then
        INSTALL_REQS=true
        break
    elif  [[ "$arg" == "--nosudo" ]]; then
        USE_SUDO=false
        # Folders an earlier run with sudo may have left owned by root.
        DATA="${SHERLOC_DATA_DIR:-.}"
        for d in reports logs data phone_dumps tmp-consult-data webstatic/images/screenshots; do
            [ -e "$DATA/$d" ] && sudo chown -R "$NORMAL_USER" "$DATA/$d"
        done
        break
    fi
done

# Create virtual environment if not exists
if [ ! -d $VENV ]; then
    echo "🐍 Creating virtual environment ($VENV)..."
    $PYTHON -m venv $VENV
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        echo "Oops, Python distribution is missing the venv module"
    fi
fi

# Activate the virtual environment
source $VENV/bin/activate
echo "✅ Activated $VENV"

# Install requirements if requested
if $INSTALL_REQS; then
    echo "📦 Installing requirements..."
    $PYTHON -m pip install -r requirements.txt
fi

# Create log folder if needed
if [ ! -d "../logs" ]; then
    echo "📁 Creating log folder..."
    mkdir ../logs
fi

# Create data folder if needed
if [ ! -d "./data" ]; then
    echo "📁 Creating data folder..."
    mkdir ./data
fi

# Create screenshots folder if needed
if [ ! -d "./webstatic/images/screenshots" ]; then
    echo "📁 Creating screenshots folder..."
    mkdir ./webstatic/images/screenshots
fi

if $USE_SUDO; then
    echo "🚀 Launching Sherloc with sudo..."
    sudo env ${SHERLOC_ENV[@]+"${SHERLOC_ENV[@]}"} $PYTHON main.py
    EXIT_CODE=$?
    echo "=================================================="
else
    echo "🚀 Launching Sherloc..."
    echo "=================================================="
    $PYTHON main.py
    EXIT_CODE=$?
fi

# If it failed due to missing packages, try installing requirements
if [ $EXIT_CODE -ne 0 ]; then
    echo "=================================================="
    echo "⚠️ Sherloc failed to launch. Attempting to install missing requirements..."
    $PYTHON -m pip install -r requirements.txt
    echo "🔁 Retrying launch..."
    if $USE_SUDO; then
        sudo env ${SHERLOC_ENV[@]+"${SHERLOC_ENV[@]}"} $PYTHON main.py
        EXIT_CODE=$?
        echo "=================================================="
    else
        $PYTHON main.py
        EXIT_CODE=$?
        echo "=================================================="
    fi
fi

echo "=================================================="

deactivate
echo "👋 Deactivated $VENV"

