"""Conversion lots → volume protocole cTrader (pur, sans dépendance protobuf).

cTrader exprime le volume « en centièmes d'unité » (docs officielles) : le champ
`volume` = unités du sous-jacent × 100. Le `lotSize` du symbole est déjà à cette
échelle (EURUSD : 1 lot = 100 000 EUR → lotSize = 10 000 000).

Isolé ici pour être testable sans le package `ctrader-open-api`.
"""

from __future__ import annotations


def lots_to_volume(
    lots: float,
    *,
    lot_size: int,
    min_volume: int = 0,
    max_volume: int = 0,
    step_volume: int = 1,
) -> int:
    """Convertit un nombre de lots en volume protocole, borné et aligné sur le pas.

    - `lots × lot_size` puis arrondi.
    - relevé au `min_volume` si trop petit ;
    - erreur si > `max_volume` (quand défini) ;
    - aligné vers le bas sur `step_volume` à partir de `min_volume`.
    """
    if lots <= 0:
        raise ValueError("lots doit être > 0")
    volume = round(lots * lot_size)
    if volume < min_volume:
        volume = min_volume
    if max_volume and volume > max_volume:
        raise ValueError(f"volume {volume} > max {max_volume}")
    step = step_volume or 1
    volume -= (volume - min_volume) % step
    return volume
