#!/usr/bin/env bash
# Setup + smoke test do engine via WSL.
set -euo pipefail

cd /mnt/d/ZELLO/IGES/fila-eletiva

# 1. venv
if [ ! -d .venv ]; then
    echo "[1/4] criando venv..."
    python3 -m venv .venv
else
    echo "[1/4] venv ja existe, reaproveitando"
fi

# 2. ativa
source .venv/bin/activate
echo "[2/4] venv ativo: $(which python)"

# 3. install
echo "[3/4] instalando dependencias..."
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt
echo "    deps OK"

# 4. smoke test - so imports
echo "[4/4] verificando imports..."
python -c "from app.engine import ask; print('    imports OK')"

echo "===SETUP_DONE==="
