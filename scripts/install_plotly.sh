#!/usr/bin/env bash
set -euo pipefail
cd /mnt/d/ZELLO/IGES/fila-eletiva
source .venv/bin/activate
python -m pip install -q plotly
python -c "from app.agent.skills.chart import to_plotly_dict; import plotly; print('plotly', plotly.__version__, '+ chart skill OK')"
