# ICT "Silver Bullet": vooraf vastgelegd (12 nov 2026, vóór de eerste test)

Bron: korte video ("1 hour a day..."). Verwant aan lab/TRAP.md, maar met 5-minutenbars, twee
vensters, instap midden in de gap en zonder 4-uurs-bias.

## Markten en data
- SPY en QQQ, Alpaca 5-minutenbars (SIP), New Yorkse tijd.
- **London-venster (03:00–04:00) valt af:** Amerikaanse aandelen handelen dan niet (pre-market
  begint om 04:00). Dat venster is voor futures/forex en wordt hier niet getest.

## Vensters en liquiditeit
| venster | referentie-range (de "liquiditeit") |
|---|---|
| NY 10:00–11:00 | hoog/laag 09:30–10:00 (het ochtend-hoog/laag) |
| Middag 14:00–15:00 | hoog/laag 12:00–14:00 (de lunch-range) |

## Regel (long; short is het exacte spiegelbeeld, de eerste setup in het venster telt)
1. **Sweep:** een 5-min bar in het venster zakt onder het referentie-laag. Sweep-low = laagste
   punt sinds die bar.
2. **Eerste fair value gap na de sweep:** de eerste drie-candle-gap omhoog (low candle 3 > high
   candle 1), met candle 1 op of na de sweep-bar, gevormd binnen het venster. Slot van candle 3
   moet weer boven het referentie-laag liggen; zo niet, dan geen trade (het is "de eerste").
3. **Instap:** limiet op het midden van de gap, geldig tot het einde van het venster.
4. **Stop:** 1 cent onder de sweep-low. **Doel:** het referentie-hoog ("buy side liquidity above
   the high"). Ligt het doel niet boven de instap: geen trade.
5. Niet geraakt om 15:55: sluiten op de open van de 15:55-bar.
6. Raakt één bar stop én doel (of instap én stop): de stop telt.
7. Hooguit één trade per venster per symbool (dus max 2 per symbool per dag).

## Kosten, perioden, criterium
- 1 basispunt per kant.
- **Ontwikkeling:** 2018-01-01 t/m 2024-12-31. **Hold-out op slot:** 2025-01-01 t/m heden.
- **Dev PASS:** ≥ 100 trades, gemiddelde netto R > 0 met t-stat ≥ 2.
- **Eindtoets (één keer, alleen na dev PASS):** gemiddelde netto R > 0 op de hold-out.
