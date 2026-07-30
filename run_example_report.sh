#!/usr/bin/env bash
set -euo pipefail
python3 -u run_matchup_plan.py \
  --our-team "Los Angeles Dodgers" \
  --our-pitcher "Yoshinobu Yamamoto" \
  --our-lineup "Shohei Ohtani,Mookie Betts,Freddie Freeman,Teoscar Hernández,Max Muncy,Will Smith,Tommy Edman,Andy Pages,Dalton Rushing" \
  --opponent-team "Detroit Tigers" \
  --opposing-pitcher "Tarik Skubal" \
  --opponent-lineup "Gleyber Torres,Kerry Carpenter,Riley Greene,Spencer Torkelson,Colt Keith,Wenceel Pérez,Parker Meadows,Dillon Dingler,Javier Báez" \
  --no-use-ml \
  --output output/dodgers_vs_tigers.html
