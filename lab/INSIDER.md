# Insider cluster buys: vooraf vastgelegd (11 nov 2026, vóór de eerste test)

**Hypothese.** Bestuurders kennen hun bedrijf het best. Als meerdere van hen kort na
elkaar met eigen geld aandelen kopen op de open markt, is dat een signaal. Dit is legaal:
we gebruiken alleen de openbare SEC Form 4-meldingen, en handelen pas ná de melding.

## Regel (één variant, geen alternatieven)
- **Telt mee:** Form 4, transactiecode **P** (open-market aankoop), door een **director of
  officer** (niet alleen een 10%-aandeelhouder), waarde ≥ $25.000.
- **Cluster:** ≥ 2 verschillende insiders van hetzelfde bedrijf kopen binnen 30 dagen.
  Signaaldatum = de meldingsdatum (filing date) van de aankoop die het cluster compleet maakt.
  Daarna 90 dagen geen nieuw signaal voor dat bedrijf.
- **Instap:** open van de eerste handelsdag **ná** de meldingsdatum.
- **Filters bij instap:** vorige slot ≥ $5, gemiddelde dagomzet (20 dagen) ≥ $1 mln.
- **Uitstap:** slot van de 63e handelsdag (~3 maanden). Delisting: laatste beschikbare koers.
- **Kosten:** 20 bps per kant (kleinere aandelen hebben grotere spreads).
- **Portefeuille:** max 20 posities, elk 5% van de equity bij instap; rest in BIL.

## Perioden
- **Ontwikkeling:** signalen 2016-03 t/m 2023-09-15 (zodat alle uitstappen vóór 2024 vallen).
- **Hold-out op slot:** 2024-01-01 t/m heden. De dev-run laadt geen meldingen of koersen uit
  die periode.

## Criterium
- **Dev PASS:** gemiddeld netto rendement boven SPY per trade > 0 met t-stat ≥ 2, **én**
  Sharpe van de portefeuille > Sharpe SPY over dezelfde periode.
- **Eindtoets (één keer):** hold-out gemiddeld netto rendement boven SPY per trade > 0,
  **én** totaal portefeuillerendement ≥ SPY over de hold-out. Anders: stoppen.

## Bekende zwakte
Koersdata van bedrijven die van de beurs verdwenen zijn kan ontbreken (survivorship bias,
maakt het resultaat te mooi). Het aantal signalen zonder koersdata wordt gerapporteerd.
