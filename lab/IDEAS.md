# Strategie-lab: vooraf vastgelegd (11 nov 2026, vóór de eerste test)

Doel: een voorzichtige strategie vinden die na kosten **risico-gecorrigeerd** beter is dan
SPY kopen-en-houden. Lage frequentie (dagelijks/maandelijks), alleen long, alleen ETF's.
Geen FX, geen hefboom, geen short.

## Protocol
- Data: Alpaca dagbars, SIP, gecorrigeerd voor splits én dividenden (total return).
- Signaal op de slotkoers van dag t, uitvoering op de **open van dag t+1**. Geen vooruitkijken.
- Kosten: 5 bps per kant over de omgezette waarde.
- **Ontwikkelperiode:** 2017-01 t/m 2025-11-10 (eerste jaar data is opwarmtijd).
- **Hold-out op slot:** 2025-11-11 t/m heden. De dev-run kan deze data technisch niet zien.
- Maximaal deze 5 ideeën. Geen nieuwe ideeën toevoegen na het zien van resultaten
  zonder een nieuw protocol met een nieuwe, nog ongeziene hold-out.

## Criterium
1. **Dev-fase:** een idee gaat door als het over de ontwikkelperiode een **hogere Sharpe**
   heeft dan SPY **én** een **kleinere maximale daling**. Maximaal 2 ideeën gaan door
   (de 2 hoogste Sharpe die aan beide eisen voldoen).
2. **Eindtoets (één keer):** op de hold-out moet het idee een **positief netto rendement**
   hebben **én** een maximale daling ≤ die van SPY. Haalt geen idee dit: stoppen.
3. Pas na PASS: paper-traden, daarna eventueel een klein echt bedrag.

## De 5 ideeën en waarom ze zouden kunnen werken
1. **trend_spy**: SPY boven het 200-daags gemiddelde → SPY, anders → BIL (kortlopende
   staatsobligaties). Maandelijks. *Reden:* trendfilters op indexen verlagen al tientallen
   jaren de diepe dalingen (Faber 2007), ten koste van wat rendement.
2. **dual_momentum**: maandelijks het sterkste van SPY en EFA op 12-maands rendement;
   is dat rendement lager dan dat van BIL → AGG. *Reden:* relatief + absoluut momentum
   (Antonacci 2014).
3. **sector_momentum**: de 3 sterkste van de 11 SPDR-sector-ETF's op 12-1-maands
   rendement, gelijk gewogen, maandelijks; SPY onder 200-daags → BIL. *Reden:*
   industriemomentum (Moskowitz & Grinblatt 1999).
4. **tsmom_multi**: uit SPY, EFA, EEM, IEF, TLT, GLD, DBC, VNQ alleen de ETF's met positief
   12-maands rendement, gewogen naar 1/volatiliteit (63 dagen), maandelijks; geen enkele
   positief → BIL. *Reden:* time-series momentum over asset classes (Moskowitz, Ooi &
   Pedersen 2012), spreiding verlaagt dalingen.
5. **rsi2_spy**: koop SPY als SPY boven het 200-daags gemiddelde staat en RSI(2) < 10;
   verkoop (→ BIL) zodra de slotkoers boven het 5-daags gemiddelde sluit. *Reden:*
   kortetermijn-mean-reversion in indexen (Connors). Waarschijnlijk afgezwakt; dient ook
   als controle of het raamwerk "te mooie" resultaten geeft.
