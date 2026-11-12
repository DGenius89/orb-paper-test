# "10 AM trap" (ICT / fair value gap): vooraf vastgelegd (12 nov 2026, vóór de eerste test)

Bron: korte video die eindigt met "Join the Candle Decoder Academy". Regels zo letterlijk
mogelijk vertaald; waar de video vaag is, staat hier de keuze, en die ligt vóór de test vast.

## Markten en data
- **SPY en QQQ** (volgen de S&P 500- en Nasdaq-futures waar deze methode meestal op wordt gedaan).
- Alpaca 1-minuutbars, SIP, inclusief pre-market, alle tijden in New Yorkse tijd.

## Regel (één variant; short is het exacte spiegelbeeld)
1. **Bias:** de 4-uurscandle 06:00–10:00 ET. Slot > open → alleen long, slot < open → alleen
   short. Minder dan 60 minuutbars in die candle → geen trade.
2. **Setup (zijwaarts):** range = hoog/laag van 10:00–10:15.
3. **Trap:** tussen 10:15 en 11:30 zakt de koers onder de range-low (bij short: boven de high).
   Trap-low = laagste punt sinds de doorbraak.
4. **Echte beweging:** daarna een bullish gap van drie candles (low van candle 3 > high van
   candle 1), met slot van candle 3 weer boven de range-low, uiterlijk 11:30.
5. **Instap:** limietorder op de bovenkant van de gap (low van candle 3), geldig tot 12:00.
6. **Stop:** 1 cent onder de trap-low. **Doel:** het ochtendhoog (hoogste koers 09:30 tot de gap).
   Ligt het doel niet boven de instap: geen trade.
7. Niet geraakt om 15:55: sluiten op de open van de 15:55-bar.
8. Raakt één bar stop én doel (of instap én stop), dan telt de stop (conservatief).
9. Hooguit één trade per symbool per dag. Geen trap → geen trade.

## Kosten
1 basispunt per kant. Dat is gunstig: SPY/QQQ zijn de meest liquide fondsen ter wereld.

## Perioden
- **Ontwikkeling:** 2018-01-01 t/m 2024-12-31.
- **Hold-out op slot:** 2025-01-01 t/m heden.

## Criterium
- **Dev PASS:** ≥ 100 trades, gemiddelde netto R > 0 met t-stat ≥ 2.
- **Eindtoets (één keer):** gemiddelde netto R > 0 op de hold-out. Anders: stoppen.
- Ter info: equity met 1 % risico per trade (max 4× hefboom) naast SPY kopen-en-houden.
