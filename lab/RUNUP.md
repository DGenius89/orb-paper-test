# FDA run-up: vooraf vastgelegd (11 nov 2026, vóór de eerste test)

**Hypothese.** Kleine en middelgrote biotechaandelen stijgen in de weken vóór een
FDA-beslissing (run-up), onder meer doordat particulieren vooraf kopen. Je verkoopt
de dag vóór de beslissing en loopt het binaire risico niet.

## Data (gratis, officieel)
- **Drugs@FDA (openFDA bulk):** originele NDA/BLA-aanvragen met status AP (goedgekeurd) en
  datum. Geen generieken (ANDA).
- **openFDA Complete Response Letters:** afwijzingen met datum (gedeeltelijke dekking).
- **Sponsor → ticker:** exacte match op genormaliseerde bedrijfsnaam met de SEC-tickerlijst.
  Het matchpercentage wordt gerapporteerd.

## Regel (één variant)
- **Beslisdag T** = eerste handelsdag op of na de beslisdatum.
- **Instap:** open van handelsdag T−30 (~6 weken vooraf). **Uitstap:** slot van T−1.
- **Filters op instap:** vorige slot ≥ $3, gemiddelde dagomzet (20 dagen) tussen $1 mln en
  $200 mln (sluit grote farma uit, waar één besluit de koers niet beweegt).
- Per bedrijf hooguit één event per 60 dagen.
- **Kosten:** 30 bps per kant (biotech-spreads).
- **Benchmark:** XBI (biotech-ETF) en SPY over exact dezelfde dagen.

## Perioden
- **Ontwikkeling:** beslissingen 2016-04-01 t/m 2023-12-31.
- **Hold-out op slot:** 2024-01-01 t/m heden.

## Criterium
- **Dev PASS:** gemiddeld netto rendement > 0 **én** gemiddeld rendement boven XBI > 0 met
  t-stat ≥ 2.
- **Eindtoets (één keer):** op de hold-out gemiddeld netto rendement > 0 **én** gemiddeld
  boven XBI > 0. Anders: stoppen.

## Bekende zwaktes (maken het resultaat eerder te mooi dan te slecht)
- De beslisdatum is een benadering van de vooraf aangekondigde PDUFA-datum. Komt een
  goedkeuring eerder dan de PDUFA-datum, dan "wist" de test iets wat je vooraf niet wist.
- Afwijzingen zijn onvolledig gedekt; de events zijn dus oververtegenwoordigd met goedkeuringen.
- Sponsornamen die niet matchen (dochterbedrijven, namen die veranderden) vallen weg.
