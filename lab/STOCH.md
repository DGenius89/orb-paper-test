# "LongShort PRO v2" (stochastic-scalp): vooraf vastgelegd (16 nov 2026, vóór de eerste test)

Bron: Instagram-reel "Trading on autopilot" (hertradethesis). Gesloten, betaald TradingView-script
(invite-only, slotje): de echte code is niet in te zien. Getest wordt de **zichtbare** logica:
een stochastic-level-cross met vaste stop en doel in procenten op Nasdaq-100, 1 minuut.

## Markt en data
- **QQQ** als vervanging voor de NAS100-CFD (Alpaca heeft geen CFD's). Alpaca 1-minuutbars,
  SIP, New Yorkse tijd, alleen de reguliere sessie 09:30–16:00.
- **Afwijking van de bron:** de filters op 30 s en 45 s zijn niet na te bouwen (Alpaca heeft
  niets kleiner dan 1 minuut). Getest wordt alleen het 1-minuutsignaal (TF 4 in de video,
  gelijk aan de grafiek). Is het kernsignaal waardeloos, dan kan een filter erop dat
  niet rechttrekken; een filter haalt alleen trades weg.

## Regel
1. Stochastic %K(14), TradingView-standaard (%K-smoothing 1), per dag berekend op
   sessiebars (dus pas signalen vanaf de 14e bar, ~09:43). Hoog = laag over 14 bars: %K = 50.
2. **Long:** %K sluit boven 30 terwijl het vorige slot onder 30 lag ("Start Level 30").
   **Short:** spiegelbeeld door 70.
3. **Instap:** open van de volgende bar. Signaalbars tot en met 15:49; daarna geen nieuwe trades.
4. **Stop 0,3 %, doel 0,5 %** van de instapprijs (instellingen uit de video). De "Stop
   Condition: Cross Down 50" beëindigt in het script de signaalzone; met SL/TP aan speelt die
   hier geen rol en wordt niet als exit gebruikt.
5. Geen van beide geraakt om 15:55: sluiten op de open van de 15:55-bar.
6. Raakt één bar stop én doel: de stop telt. Gapt de koers door de stop: uitstap op de open.
7. Eén positie tegelijk. Een nieuw signaal telt pas als de bar na de uitstapbar komt.

## Kosten, perioden, criterium
- 1 basispunt per kant (QQQ). Dat is 0,067 R per trade bij een stop van 0,3 %.
- **Ontwikkeling:** 2018-01-01 t/m 2024-12-31. **Hold-out op slot:** 2025-01-01 t/m heden.
- **Dev PASS:** ≥ 100 trades, gemiddelde netto R > 0 met t-stat ≥ 2.
- **Eindtoets (één keer, alleen na dev PASS):** gemiddelde netto R > 0 op de hold-out.
- Break-even zonder kosten bij 1:1,67: winrate ≥ 37,5 % (exits op tijd uitgezonderd).
